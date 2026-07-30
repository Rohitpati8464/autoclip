"""Filesystem layout for ClipForge artifacts.

Everything ClipForge writes lives under a single root (``~/.clipforge`` by
default). The root is resolved through ``CLIPFORGE_HOME`` so tests — and users
who keep media on another drive — can relocate it without touching code.

Layout::

    <root>/
      media/            source videos, one directory per source id
      work/<job_id>/    stage intermediates (audio, transcript, crop path)
      exports/          finished clips
      clipforge.db      SQLite database
      config.json       settings (secrets live in the OS keyring)
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_HOME = "CLIPFORGE_HOME"


def root() -> Path:
    """Return the ClipForge home directory.

    Resolved fresh on every call rather than cached at import time, so tests
    that patch ``CLIPFORGE_HOME`` take effect without reloading the module.
    """
    override = os.environ.get(ENV_HOME)
    base = Path(override).expanduser() if override else Path.home() / ".clipforge"
    return base.resolve()


def media_dir() -> Path:
    return root() / "media"


def work_dir() -> Path:
    return root() / "work"


def exports_dir() -> Path:
    return root() / "exports"


def db_path() -> Path:
    return root() / "clipforge.db"


def config_path() -> Path:
    return root() / "config.json"


def job_work_dir(job_id: str) -> Path:
    """Return the per-job scratch directory for pipeline stage artifacts."""
    return work_dir() / job_id


def source_media_dir(source_id: str) -> Path:
    """Return the directory holding a source's downloaded/uploaded media."""
    return media_dir() / source_id


def ensure_layout() -> Path:
    """Create the directory tree if absent and return the root.

    Safe to call repeatedly; used on startup and at the top of each CLI command.
    """
    base = root()
    for path in (base, media_dir(), work_dir(), exports_dir()):
        path.mkdir(parents=True, exist_ok=True)
    return base
