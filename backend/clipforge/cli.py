"""ClipForge command-line interface."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__, config, paths, system

app = typer.Typer(
    name="clipforge",
    help="Turn long video into caption-burned 9:16 clips — locally.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

OK = "[green]OK[/green]"
WARN = "[yellow]WARN[/yellow]"
FAIL = "[red]FAIL[/red]"


def _status(passed: bool, warn_only: bool = False) -> str:
    if passed:
        return OK
    return WARN if warn_only else FAIL


@app.command()
def version() -> None:
    """Print the ClipForge version."""
    console.print(f"clipforge {__version__}")


@app.command()
def doctor() -> None:
    """Check that this machine can run the pipeline, and explain anything missing."""
    report = system.refresh()
    settings = config.load()

    console.print()
    console.print(
        Panel.fit(
            Text.from_markup(
                f"[bold]ClipForge {__version__}[/bold]\n{report.platform}\nHome: {paths.root()}"
            ),
            border_style="cyan",
        )
    )

    remediation: list[str] = []

    # --- Runtime -----------------------------------------------------------
    table = Table(title="Runtime", show_header=True, header_style="bold", title_justify="left")
    table.add_column("Check")
    table.add_column("Status", width=6)
    table.add_column("Detail")

    table.add_row("Python", _status(report.python_ok), report.python_version)
    if not report.python_ok:
        remediation.append(
            "Python must be >=3.11,<3.13 — MediaPipe publishes no wheels for 3.13+, "
            "so the reframe stage cannot run. Create the environment with "
            "[cyan]uv venv --python 3.11[/cyan]."
        )

    ff = report.ffmpeg
    table.add_row("ffmpeg", _status(ff.found), ff.version or "not found")
    table.add_row("ffprobe", _status(ff.ffprobe_found), ff.path or "not found")
    if not ff.found or not ff.ffprobe_found:
        remediation.append(
            "Install ffmpeg and make sure both [cyan]ffmpeg[/cyan] and [cyan]ffprobe[/cyan] "
            "are on PATH. Windows: [cyan]winget install Gyan.FFmpeg[/cyan]. "
            "macOS: [cyan]brew install ffmpeg[/cyan]. Debian/Ubuntu: "
            "[cyan]sudo apt install ffmpeg[/cyan]."
        )
    else:
        table.add_row("  libass (captions)", _status(ff.has_libass), "subtitle burn-in")
        table.add_row("  fontconfig", _status(ff.has_fontconfig, warn_only=True), "font resolution")
        table.add_row("  libx264", _status(ff.has_libx264), "software H.264 encode")
        table.add_row(
            "  h264_nvenc",
            _status(ff.has_nvenc, warn_only=True),
            "GPU encode" if ff.has_nvenc else "not available (software encode will be used)",
        )
        missing = ff.missing_filters
        table.add_row(
            "  required filters",
            _status(not missing),
            "all present" if not missing else f"missing: {', '.join(missing)}",
        )
        optional_missing = [f for f in system.OPTIONAL_FILTERS if f not in ff.filters]
        if optional_missing:
            table.add_row(
                "  optional filters",
                WARN,
                f"missing: {', '.join(optional_missing)}",
            )
        if not ff.has_libass:
            remediation.append(
                "This ffmpeg build lacks libass, so captions cannot be burned in. "
                "Install a full build (Windows: [cyan]Gyan.FFmpeg[/cyan] full, not essentials)."
            )

    console.print()
    console.print(table)

    # --- Acceleration ------------------------------------------------------
    gpu = report.gpu
    accel_table = Table(
        title="Acceleration", show_header=True, header_style="bold", title_justify="left"
    )
    accel_table.add_column("Check")
    accel_table.add_column("Status", width=6)
    accel_table.add_column("Detail")

    accel_table.add_row("Mode", OK, gpu.accel.upper())
    if gpu.name:
        vram = f", {gpu.vram_mb} MiB VRAM" if gpu.vram_mb else ""
        cc = f", compute {gpu.compute_capability}" if gpu.compute_capability else ""
        accel_table.add_row("Device", OK, f"{gpu.name}{vram}{cc}")
    if gpu.driver_version:
        accel_table.add_row("Driver", OK, gpu.driver_version)

    if gpu.name and not gpu.ctranslate2_cuda:
        accel_table.add_row("CUDA for Whisper", FAIL, "CTranslate2 cannot see the GPU")
        remediation.append(
            "An NVIDIA GPU is present but CTranslate2 can't use it — usually missing cuDNN. "
            "Install the CUDA runtime libraries with "
            "[cyan]uv pip install 'clipforge[gpu]'[/cyan], then re-run doctor. "
            "Transcription will fall back to CPU until this is fixed."
        )
    elif gpu.ctranslate2_cuda:
        accel_table.add_row("CUDA for Whisper", OK, "CTranslate2 sees the GPU")

    reason = ""
    if gpu.accel == "cuda" and gpu.compute_type == "int8_float16":
        reason = " (no fp16 tensor cores on this GPU — int8 is faster here)"
    accel_table.add_row("Whisper compute type", OK, f"{gpu.compute_type}{reason}")

    if settings.whisper.compute_type:
        accel_table.add_row(
            "  override in config", WARN, f"forced to {settings.whisper.compute_type}"
        )

    console.print()
    console.print(accel_table)

    # --- Python dependencies ----------------------------------------------
    deps = report.deps
    dep_table = Table(
        title="Dependencies", show_header=True, header_style="bold", title_justify="left"
    )
    dep_table.add_column("Package")
    dep_table.add_column("Status", width=6)
    dep_table.add_column("Used for")

    dep_table.add_row("faster-whisper", _status(deps.faster_whisper), "transcription")
    dep_table.add_row("mediapipe", _status(deps.mediapipe), "face detection / reframe")
    dep_table.add_row("scenedetect", _status(deps.scenedetect), "shot boundaries")
    dep_table.add_row(
        "whisperx",
        _status(deps.whisperx, warn_only=True),
        "speaker diarization" + ("" if deps.whisperx else " (optional extra)"),
    )

    if not deps.whisperx and settings.whisper.diarization:
        remediation.append(
            "Diarization is enabled in settings but WhisperX isn't installed. "
            "Run [cyan]uv pip install 'clipforge[diarization]'[/cyan] and set a HuggingFace "
            "token with [cyan]clipforge config set-secret huggingface_token[/cyan]."
        )

    for missing, extra in (
        (not deps.faster_whisper, "faster-whisper"),
        (not deps.mediapipe, "mediapipe"),
        (not deps.scenedetect, "scenedetect"),
    ):
        if missing:
            remediation.append(
                f"[cyan]{extra}[/cyan] is not installed — reinstall ClipForge's core "
                "dependencies with [cyan]uv pip install -e '.[dev]'[/cyan]."
            )

    console.print()
    console.print(dep_table)

    # --- Providers ---------------------------------------------------------
    prov_table = Table(
        title="LLM providers", show_header=True, header_style="bold", title_justify="left"
    )
    prov_table.add_column("Provider")
    prov_table.add_column("Status", width=6)
    prov_table.add_column("Detail")

    for name in config.KEYED_PROVIDERS:
        has_key = config.get_secret(name, settings) is not None
        model = settings.provider(name).model or "no model set"
        active = " [cyan](active)[/cyan]" if settings.active_provider == name else ""
        prov_table.add_row(
            f"{name}{active}",
            _status(has_key, warn_only=True),
            f"{model}" if has_key else "no API key stored",
        )

    ollama_active = " [cyan](active)[/cyan]" if settings.active_provider == "ollama" else ""
    if deps.ollama_running:
        model_list = ", ".join(deps.ollama_models[:4]) or "no models pulled"
        prov_table.add_row(f"ollama{ollama_active}", OK, model_list)
    else:
        prov_table.add_row(
            f"ollama{ollama_active}", WARN, "not running on localhost:11434 (optional)"
        )

    if not any(config.get_secret(n, settings) for n in config.KEYED_PROVIDERS) and not (
        deps.ollama_running
    ):
        remediation.append(
            "No LLM provider is usable yet. Add an API key with "
            "[cyan]clipforge config set-secret anthropic[/cyan] (or openai / gemini), "
            "or install Ollama for a fully local setup."
        )

    console.print()
    console.print(prov_table)

    # --- Storage -----------------------------------------------------------
    store_table = Table(
        title="Storage", show_header=True, header_style="bold", title_justify="left"
    )
    store_table.add_column("Check")
    store_table.add_column("Status", width=6)
    store_table.add_column("Detail")

    store_table.add_row(
        "Secret storage",
        _status(deps.keyring_backend, warn_only=True),
        "OS keyring" if deps.keyring_backend else "no keyring backend — plaintext fallback",
    )
    if not deps.keyring_backend:
        remediation.append(
            "No OS keyring backend is available, so API keys would be written to "
            f"{paths.config_path()} in plaintext. On headless Linux install "
            "[cyan]keyrings.alt[/cyan] or a Secret Service provider."
        )
    if settings.insecure_secret_storage:
        store_table.add_row("Stored secrets", WARN, "one or more secrets are in plaintext")

    store_table.add_row("Home", OK, str(paths.root()))

    console.print()
    console.print(store_table)

    # --- Verdict -----------------------------------------------------------
    console.print()
    if report.ready:
        console.print(
            Panel.fit(
                "[bold green]Ready.[/bold green] The core pipeline can run on this machine.",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel.fit(
                "[bold red]Not ready.[/bold red] Resolve the items below, then re-run "
                "[cyan]clipforge doctor[/cyan].",
                border_style="red",
            )
        )

    if remediation:
        console.print()
        console.print("[bold]What to do:[/bold]")
        for i, item in enumerate(remediation, 1):
            console.print(f"  [bold]{i}.[/bold] {item}")
        console.print()

    raise typer.Exit(0 if report.ready else 1)


config_app = typer.Typer(help="Inspect and modify ClipForge settings.", no_args_is_help=True)
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show() -> None:
    """Print current settings (secrets are never displayed)."""
    settings = config.load()
    console.print_json(settings.model_dump_json(indent=2))


@config_app.command("path")
def config_path_cmd() -> None:
    """Print the path to config.json."""
    console.print(str(paths.config_path()))


@config_app.command("set-secret")
def config_set_secret(
    key: str = typer.Argument(
        ...,
        help="Provider name (anthropic, openai, gemini) or 'huggingface_token'.",
    ),
) -> None:
    """Store an API key or token. The value is prompted for, never passed as an argument.

    Prompting rather than accepting a flag keeps the secret out of your shell
    history and out of the process list.
    """
    valid = (*config.KEYED_PROVIDERS, config.HF_TOKEN_KEY)
    if key not in valid:
        console.print(f"[red]Unknown secret '{key}'.[/red] Expected one of: {', '.join(valid)}")
        raise typer.Exit(2)

    value = typer.prompt(f"Value for {key}", hide_input=True).strip()
    if not value:
        console.print("[yellow]Empty value — nothing stored.[/yellow]")
        raise typer.Exit(1)

    paths.ensure_layout()
    secure = config.set_secret(key, value)
    if secure:
        console.print(f"[green]Stored {key} in the OS keyring.[/green]")
    else:
        console.print(
            f"[yellow]No keyring backend available — {key} was written to "
            f"{paths.config_path()} in plaintext.[/yellow]"
        )


@config_app.command("delete-secret")
def config_delete_secret(key: str = typer.Argument(..., help="Secret to remove.")) -> None:
    """Remove a stored secret."""
    config.delete_secret(key)
    console.print(f"[green]Removed {key}.[/green]")


@app.command()
def init() -> None:
    """Create the ClipForge home directory and initialise the database."""
    from . import db

    version_applied = db.init()
    console.print(f"[green]Initialised[/green] {paths.root()} (schema v{version_applied})")


if __name__ == "__main__":  # pragma: no cover
    app()
