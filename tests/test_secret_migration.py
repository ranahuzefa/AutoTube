"""Tests for settings-level secret migration and env-var precedence."""

from __future__ import annotations

import json

import pytest

from autotube.config import Settings, load_settings, save_settings
from autotube.storage import SettingsStore


@pytest.fixture
def fake_secret_store(monkeypatch):
    from autotube import secrets as secrets_mod

    class _Backend:
        def __init__(self):
            self.data = {}

        def get(self, name):
            return self.data.get(name, "")

        def set(self, name, value):
            self.data[name] = value

        def delete(self, name):
            self.data.pop(name, None)

    backend = _Backend()
    monkeypatch.setattr(
        secrets_mod.SecretStore, "_default_backend", staticmethod(lambda: backend)
    )
    return backend


def _settings_path(tmp_path):
    return SettingsStore().path


def test_save_settings_writes_keys_to_secret_store_not_settings(
    tmp_path, monkeypatch, fake_secret_store
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    save_settings(
        Settings(pexels_api_key="pex-plain", pixabay_api_key="pix-plain")
    )

    settings_text = _settings_path(tmp_path).read_text(encoding="utf-8")
    assert "pex-plain" not in settings_text
    assert "pix-plain" not in settings_text
    assert "pexels_api_key" not in settings_text
    assert "pixabay_api_key" not in settings_text
    assert fake_secret_store.data["pexels_api_key"] == "pex-plain"
    assert fake_secret_store.data["pixabay_api_key"] == "pix-plain"


def test_load_settings_reads_keys_from_secret_store(
    tmp_path, monkeypatch, fake_secret_store
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    fake_secret_store.data["pexels_api_key"] = "pex-secure"
    fake_secret_store.data["pixabay_api_key"] = "pix-secure"
    settings = load_settings(apply_env=False)
    assert settings.pexels_api_key == "pex-secure"
    assert settings.pixabay_api_key == "pix-secure"


def test_migration_removes_plaintext_keys_once(
    tmp_path, monkeypatch, fake_secret_store
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    path = _settings_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "pexels_api_key": "old-pex",
                "pixabay_api_key": "old-pix",
                "fps": 24,
            }
        ),
        encoding="utf-8",
    )

    settings = load_settings(apply_env=False)

    assert settings.pexels_api_key == "old-pex"
    assert settings.pixabay_api_key == "old-pix"
    assert settings.fps == 24

    raw = path.read_text(encoding="utf-8")
    assert "pexels_api_key" not in raw
    assert "pixabay_api_key" not in raw
    assert "old-pex" not in raw
    assert "old-pix" not in raw
    assert fake_secret_store.data["pexels_api_key"] == "old-pex"
    assert fake_secret_store.data["pixabay_api_key"] == "old-pix"


def test_migration_does_not_overwrite_existing_secret(
    tmp_path, monkeypatch, fake_secret_store
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    fake_secret_store.data["pexels_api_key"] = "already-secure"
    path = _settings_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"pexels_api_key": "legacy-value"}),
        encoding="utf-8",
    )

    settings = load_settings(apply_env=False)

    assert settings.pexels_api_key == "already-secure"
    assert fake_secret_store.data["pexels_api_key"] == "already-secure"


def test_env_override_beats_secret_store(
    tmp_path, monkeypatch, fake_secret_store
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("AUTOTUBE_PEXELS_API_KEY", "env-pex")
    fake_secret_store.data["pexels_api_key"] = "secure-pex"

    settings = load_settings()

    assert settings.pexels_api_key == "env-pex"


def test_corrupt_secret_store_fails_safe_to_empty(
    tmp_path, monkeypatch
) -> None:
    from autotube import secrets as secrets_mod
    from autotube.exceptions import SecretStorageError

    class _Boom:
        def get(self, name):
            raise SecretStorageError("corrupt")

        def set(self, name, value):
            raise SecretStorageError("corrupt")

        def delete(self, name):
            raise SecretStorageError("corrupt")

    monkeypatch.setattr(
        secrets_mod.SecretStore, "_default_backend", staticmethod(lambda: _Boom())
    )
    monkeypatch.setenv("APPDATA", str(tmp_path))

    settings = load_settings(apply_env=False)
    assert settings.pexels_api_key == ""
    assert settings.pixabay_api_key == ""
