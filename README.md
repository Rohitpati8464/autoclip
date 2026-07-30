# ClipForge

**Open-source, local-first AI video clipper.** Long video in → ranked, caption-burned, speaker-tracked 9:16 clips out.

Paste a YouTube link or drop a file. ClipForge transcribes it, uses an LLM to find the moments worth clipping, reframes them to vertical while tracking whoever is speaking, burns in animated captions, and exports platform-ready MP4s.

No accounts. No uploads to anyone's servers. No watermarks. No subscription. MIT licensed.

---

## Why

Existing open-source clippers stop at "works on my machine" — no UI, janky reframing, ugly captions. ClipForge ships the full loop: ingest → clips → review → export.

Two ways to run it:

- **Fully local** — Whisper + Ollama. Zero cloud, zero cost, nothing leaves the machine.
- **Bring your own key** — Anthropic, OpenAI, Gemini, or any OpenAI-compatible endpoint (OpenRouter, Groq, DeepSeek, LM Studio) for better clip selection.

## Requirements

- **Python 3.11 or 3.12.** Not 3.13 — MediaPipe publishes no wheels for it, and the reframe stage needs MediaPipe.
- **ffmpeg** with `libass` and `libx264` compiled in — a "full" build, not "essentials". Both `ffmpeg` and `ffprobe` on your PATH.
- **Optional:** an NVIDIA GPU or Apple Silicon for faster transcription. CPU-only works, just slower.

Run `clipforge doctor` at any point. It checks all of the above and tells you exactly what to fix.

## Install

```bash
uv venv --python 3.11
uv pip install -e ".[dev]"
```

Build the UI:

```bash
cd frontend && npm install && npm run build
```

Check the machine, then start:

```bash
clipforge doctor
```

```bash
clipforge serve
```

That opens `http://localhost:8000`.

### Docker

The guaranteed path — ffmpeg, Python version, and fonts are all pinned:

```bash
docker compose -f docker/compose.yaml up --build
```

```bash
docker compose -f docker/compose.yaml --profile gpu up --build
```

## Use it

Add an API key (or start Ollama), then paste a link:

```bash
clipforge config set-secret anthropic
```

```bash
clipforge clip "https://youtube.com/watch?v=..."
```

Everything the UI does is available from the CLI:

| command                       | does                                          |
| ----------------------------- | --------------------------------------------- |
| `clipforge doctor`            | check this machine and explain what's missing  |
| `clipforge serve`             | start the web app                              |
| `clipforge clip <url\|file>`  | run the whole pipeline and export              |
| `clipforge jobs`              | list recent jobs                               |
| `clipforge providers`         | check which AI providers are reachable         |
| `clipforge styles`            | list caption presets                           |
| `clipforge config show`       | print settings                                 |
| `clipforge update-ytdlp`      | update yt-dlp after a YouTube change           |

### YouTube downloads

As of 2026, YouTube blocks most anonymous downloads with a bot check, and proof-of-origin tokens no longer clear it reliably. Browser cookies do:

Set **Settings → Ingest → YouTube cookies from** to a browser you're signed into, and **close that browser** before downloading — it locks its cookie database while running.

Uploading a file always works and needs none of this.

## Optional extras

```bash
uv pip install -e ".[gpu]"
```

CUDA runtime libraries for NVIDIA GPUs. Install these if `doctor` says CTranslate2 can't see your GPU — the usual cause is a missing cuDNN.

```bash
uv pip install -e ".[diarization]"
```

Speaker diarization via WhisperX, which is what lets the reframe stage cut to whoever is talking. Pulls PyTorch (large) and needs a HuggingFace token plus acceptance of the gated pyannote model licences.

## What to expect

Transcription dominates the runtime. On CPU with the `small` model, budget roughly real-time — a 30-minute video takes about 30 minutes. A GPU cuts that several-fold. Export is fast either way.

Clip quality tracks model quality closely. A 7B local model returns valid JSON full of mediocre picks; a frontier model is noticeably better at spotting a real hook. That is the honest trade for running entirely offline.

## Configuration

Settings live in `~/.clipforge/config.json`. API keys go in your OS keyring — Credential Manager on Windows, Keychain on macOS, Secret Service on Linux — never in that file. If no keyring backend exists, ClipForge falls back to plaintext **and says so**, in the UI and in `doctor`.

All artifacts live under `~/.clipforge/`, relocatable with the `CLIPFORGE_HOME` environment variable.

## Caption styles

| style          | look                                                            |
| -------------- | --------------------------------------------------------------- |
| `bold_pop`     | chunky white, heavy outline, spoken word grows and turns yellow  |
| `karaoke_fill` | words fill with colour exactly as they're spoken                 |
| `clean_lower`  | minimal lower third, no animation                                |
| `boxed`        | high-contrast text on a solid block                              |

Fonts are bundled (SIL Open Font License), so nothing is fetched at runtime.

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — how it works and why
- [CONTRIBUTING.md](docs/CONTRIBUTING.md) — setup, tests, good first contributions

## Status

Working end to end: ingest, transcription, highlight detection across four providers, speaker-tracked reframing, four caption styles, export at three aspect ratios, and the full review UI.

Not yet done: the reframe acceptance bar has unit coverage but has not been validated against a golden three-video set, which is the release gate for tagging v0.1.0. No direct posting to platforms — that stays out of scope.

## Legal

ClipForge bundles [yt-dlp](https://github.com/yt-dlp/yt-dlp). **Only download content you own or have the rights to process.** ClipForge contains no workarounds for DRM or paywalled content and never will.

## License

MIT — see [LICENSE](LICENSE).
