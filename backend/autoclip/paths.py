"""Filesystem layout for AutoClip artifacts.

Everything AutoClip writes lives under a single root (``~/.autoclip`` by
default). The root is resolved through ``AUTOCLIP_HOME`` so tests — and users
who keep media on another drive — can relocate it without touching code.

Layout::

    <root>/
      media/            source videos, one directory per source id
      work/<job_id>/    stage intermediates (audio, transcript, crop path)
      exports/          finished clips
      autoclip.db       SQLite database
      config.json       settings (secrets live in the OS keyring)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

ENV_HOME = "AUTOCLIP_HOME"

DEFAULT_DIR_NAME = ".autoclip"

#: The project was called ClipForge before release. An install that predates the
#: rename has its media, database, and settings under the old name, and media
#: files are far too large to copy silently — so the old directory is adopted in
#: place when the new one doesn't exist yet.
LEGACY_DIR_NAME = ".clipforge"


def root() -> Path:
    """Return the AutoClip home directory.

    Resolved fresh on every call rather than cached at import time, so tests
    that patch ``AUTOCLIP_HOME`` take effect without reloading the module.
    """
    override = os.environ.get(ENV_HOME)
    if override:
        return Path(override).expanduser().resolve()

    default = Path.home() / DEFAULT_DIR_NAME
    if not default.exists():
        legacy = Path.home() / LEGACY_DIR_NAME
        if legacy.is_dir():
            log.info(
                "Using the pre-rename data directory %s. Rename it to %s when "
                "convenient; AutoClip will use whichever it finds.",
                legacy,
                default,
            )
            return legacy.resolve()

    return default.resolve()


def media_dir() -> Path:
    return root() / "media"


def work_dir() -> Path:
    return root() / "work"


def exports_dir() -> Path:
    return root() / "exports"


DB_NAME = "autoclip.db"
LEGACY_DB_NAME = "clipforge.db"


def db_path() -> Path:
    """Return the SQLite database path.

    Adopts a pre-rename database in place rather than starting an empty one
    beside it, which would silently orphan every job the user already has.
    """
    base = root()
    current = base / DB_NAME
    if not current.exists():
        legacy = base / LEGACY_DB_NAME
        if legacy.is_file():
            return legacy
    return current


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
