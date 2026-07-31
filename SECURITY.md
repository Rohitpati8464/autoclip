# Security

## Reporting a vulnerability

Please **don't** open a public issue for a security problem. Use GitHub's
[private vulnerability reporting](https://github.com/artbyjazi/autoclip/security/advisories/new)
instead, and I'll respond as quickly as I can.

## What AutoClip does with your data

Worth stating plainly, because "local-first" is easy to claim and easy to get wrong:

- **Media never leaves your machine**, except to whichever LLM provider you configure — and only the *transcript text* goes, never video or audio. Choosing Ollama sends nothing anywhere.
- **API keys live in your OS keyring** (Credential Manager, Keychain, Secret Service), not in `config.json`. If no keyring backend exists, AutoClip falls back to a file **and tells you so** in the UI and in `autoclip doctor`. It will not silently downgrade.
- **No telemetry, no analytics, no phone-home.** There is no code that contacts a server AutoClip's authors control.
- **Everything is under `~/.autoclip/`** — media, transcripts, exports, database, settings. Delete that directory and nothing remains.

## Running it safely

AutoClip **has no authentication**. It binds to `127.0.0.1` by default, and it should stay that way.

Serving it on `0.0.0.0`, or publishing the Docker port beyond loopback, exposes an unauthenticated API that can read any file path the process can reach and execute ffmpeg against it. If you genuinely need remote access, put it behind a reverse proxy that terminates TLS and handles authentication.

## Scope

In scope: anything that lets a third party read your media, exfiltrate your API keys, or execute code through a crafted input file, URL, or API request.

Out of scope: the consequences of deliberately binding to a public interface, and anything requiring an attacker who already has local access to your user account.

## Supported versions

AutoClip is pre-1.0. Fixes land on `main`; there are no backported release branches yet.
