"""Filesystem layout resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
from clipforge import paths


def test_home_override_is_honoured(clipforge_home: Path) -> None:
    assert paths.root() == clipforge_home.resolve()


def test_override_is_read_per_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Resolving lazily rather than caching at import time is what lets tests —
    # and a user changing the env var — take effect without a reload.
    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path / "first"))
    first = paths.root()

    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path / "second"))

    assert paths.root() != first


def test_defaults_under_the_user_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.ENV_HOME, raising=False)

    assert paths.root() == (Path.home() / ".clipforge").resolve()


def test_ensure_layout_creates_the_tree(clipforge_home: Path) -> None:
    paths.ensure_layout()

    for directory in (paths.media_dir(), paths.work_dir(), paths.exports_dir()):
        assert directory.is_dir()


def test_ensure_layout_is_idempotent(clipforge_home: Path) -> None:
    paths.ensure_layout()
    marker = paths.media_dir() / "keep.txt"
    marker.write_text("x", encoding="utf-8")

    paths.ensure_layout()

    assert marker.exists()


def test_all_artifacts_live_under_the_root(clipforge_home: Path) -> None:
    root = paths.root()
    derived = [
        paths.media_dir(),
        paths.work_dir(),
        paths.exports_dir(),
        paths.db_path(),
        paths.config_path(),
        paths.job_work_dir("job123"),
        paths.source_media_dir("src456"),
    ]

    for path in derived:
        assert root in path.parents


def test_per_job_and_per_source_directories_are_namespaced(clipforge_home: Path) -> None:
    assert paths.job_work_dir("job123").name == "job123"
    assert paths.job_work_dir("job123").parent == paths.work_dir()
    assert paths.source_media_dir("src456").parent == paths.media_dir()
