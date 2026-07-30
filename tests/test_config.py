"""Settings persistence and secret storage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from clipforge import config, paths


def test_defaults_load_without_a_config_file() -> None:
    settings = config.load()

    assert settings.active_provider == "anthropic"
    assert settings.whisper.model == "small"
    assert settings.export.loudness_lufs == -14.0
    assert set(settings.providers) == {"anthropic", "openai", "gemini", "ollama"}


def test_settings_round_trip() -> None:
    settings = config.load()
    settings.active_provider = "ollama"
    settings.whisper.model = "large-v3"
    settings.clips.max_clips = 25
    config.save(settings)

    reloaded = config.load()
    assert reloaded.active_provider == "ollama"
    assert reloaded.whisper.model == "large-v3"
    assert reloaded.clips.max_clips == 25


def test_load_falls_back_to_defaults_on_corrupt_file() -> None:
    paths.ensure_layout()
    paths.config_path().write_text("{ not json", encoding="utf-8")

    settings = config.load()

    assert settings.active_provider == "anthropic"


def test_provider_returns_active_by_default() -> None:
    settings = config.load()
    settings.active_provider = "gemini"

    assert settings.provider().model == settings.providers["gemini"].model
    assert settings.provider("openai").model == "gpt-4o"


def test_unknown_provider_key_is_created_on_demand() -> None:
    settings = config.load()

    created = settings.provider("some-future-vendor")

    assert created.model == ""
    assert "some-future-vendor" in settings.providers


def test_save_is_atomic_leaving_no_temp_file() -> None:
    config.save(config.load())

    leftovers = list(paths.root().glob("*.tmp"))
    assert leftovers == []


class TestSecrets:
    def test_secret_round_trip_via_keyring(self, fake_keyring) -> None:
        secure = config.set_secret("anthropic", "sk-ant-test")

        assert secure is True
        assert config.get_secret("anthropic") == "sk-ant-test"

    def test_keyring_storage_never_touches_config_file(self, fake_keyring) -> None:
        config.set_secret("anthropic", "sk-ant-test")
        config.save(config.load())

        raw = paths.config_path().read_text(encoding="utf-8")
        assert "sk-ant-test" not in raw

    def test_missing_secret_returns_none(self, fake_keyring) -> None:
        assert config.get_secret("openai") is None

    def test_delete_removes_the_secret(self, fake_keyring) -> None:
        config.set_secret("openai", "sk-openai-test")
        config.delete_secret("openai")

        assert config.get_secret("openai") is None

    def test_environment_variable_overrides_stored_secret(
        self, fake_keyring, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config.set_secret("anthropic", "from-keyring")
        monkeypatch.setenv("CLIPFORGE_ANTHROPIC_KEY", "from-env")

        assert config.get_secret("anthropic") == "from-env"


class TestSecretsWithoutKeyring:
    """Without a keyring backend we fall back to disk — loudly, never silently."""

    def test_fallback_reports_insecure_storage(self, no_keyring) -> None:
        secure = config.set_secret("anthropic", "sk-plaintext")

        assert secure is False
        assert config.load().insecure_secret_storage is True

    def test_fallback_secret_is_still_readable(self, no_keyring) -> None:
        config.set_secret("anthropic", "sk-plaintext")

        assert config.get_secret("anthropic") == "sk-plaintext"

    def test_fallback_secret_is_not_in_the_public_schema(self, no_keyring) -> None:
        config.set_secret("anthropic", "sk-plaintext")

        settings = config.load()
        # The secret must survive a round trip but stay out of model_dump, so it
        # can never leak through an API response that serialises settings.
        assert "sk-plaintext" not in json.dumps(settings.model_dump(mode="json"))
        assert settings._fallback_secrets["anthropic"] == "sk-plaintext"

    def test_deleting_last_fallback_clears_the_insecure_flag(self, no_keyring) -> None:
        config.set_secret("anthropic", "sk-plaintext")
        config.delete_secret("anthropic")

        assert config.load().insecure_secret_storage is False

    def test_keyring_errors_degrade_to_the_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tests.conftest import FakeKeyring

        monkeypatch.setattr(config, "_keyring", lambda: FakeKeyring(failing=True))

        secure = config.set_secret("gemini", "sk-gemini")

        assert secure is False
        assert config.get_secret("gemini") == "sk-gemini"


def test_config_file_is_written_under_clipforge_home(clipforge_home: Path) -> None:
    config.save(config.load())

    assert paths.config_path() == clipforge_home.resolve() / "config.json"
    assert paths.config_path().exists()
