# ClipForge

**Open-source, local-first AI video clipper.** Long video in → ranked, caption-burned, speaker-tracked 9:16 clips out.

Paste a YouTube link or drop a file, and ClipForge transcribes it, uses an LLM to find the moments worth clipping, reframes them to vertical while tracking whoever is speaking, burns in animated captions, and exports platform-ready MP4s.

No accounts. No uploads to anyone's servers. No watermarks. No subscription. MIT licensed.

> **Status: in development.** Phase 0 (foundation) is in place. The pipeline is not yet runnable end to end. See [the build plan](#roadmap) below.

---

## Why

Existing open-source clippers stop at "works on my machine" — no UI, janky reframing, ugly captions. ClipForge ships the full loop: ingest → clips → review/edit → export.

You can run it two ways:

- **Fully local** — Whisper + Ollama. Zero cloud, zero cost.
- **Bring your own key** — Anthropic, OpenAI, Gemini, or any OpenAI-compatible endpoint (OpenRouter, Groq, DeepSeek, LM Studio) for better clip selection.

## Requirements

- **Python 3.11 or 3.12.** Not 3.13 — MediaPipe publishes no wheels for it, and the reframe stage needs MediaPipe.
- **ffmpeg** with `libass` and `libx264` compiled in (a "full" build, not "essentials"). Both `ffmpeg` and `ffprobe` must be on your PATH.
- **Optional:** an NVIDIA GPU or Apple Silicon for faster transcription. CPU-only works, just slower.

Run `clipforge doctor` at any point — it checks all of the above and tells you exactly what to fix.

## Install

```bash
uv venv --python 3.11
uv pip install -e ".[dev]"
```

Then verify your machine:

```bash
clipforge doctor
```

### Optional extras

```bash
uv pip install -e ".[gpu]"
```

CUDA runtime libraries for NVIDIA GPUs. Install these if `doctor` reports that CTranslate2 can't see your GPU — the usual cause is a missing cuDNN.

```bash
uv pip install -e ".[diarization]"
```

Speaker diarization via WhisperX. Needed to track who is speaking in multi-person video. Pulls PyTorch (large) and requires a HuggingFace token plus acceptance of the gated pyannote model licenses.

## Configuration

Settings live in `~/.clipforge/config.json`. API keys are stored in your OS keyring (Credential Manager on Windows, Keychain on macOS, Secret Service on Linux) — never in that file.

```bash
clipforge config set-secret anthropic
clipforge config show
```

The value is prompted for rather than passed as a flag, so it stays out of your shell history.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Foundation — packaging, config, database, `doctor` | In progress |
| 1 | Pipeline core — ingest, transcribe, highlight detection, basic export | Not started |
| 2 | Reframe — scene detection, face tracking, active speaker, smoothed crop path | Not started |
| 3 | Web UI — ingest, progress, clip review, export | Not started |
| 4 | Release — Docker, PyPI, docs | Not started |

## Legal

ClipForge bundles [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube ingestion. **Only download content you own or have the rights to process.** ClipForge contains no workarounds for DRM or paywalled content and never will.

## License

MIT — see [LICENSE](LICENSE).
