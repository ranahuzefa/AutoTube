"""Tests for settings config and env overrides."""

from __future__ import annotations

from pathlib import Path

import pytest

from autotube.config import Settings, load_settings, save_settings
from autotube.exceptions import ValidationError
from autotube.config import validate_settings


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTOTUBE_PEXELS_API_KEY", "secret")
    monkeypatch.setenv("AUTOTUBE_FPS", "24")
    settings = load_settings()
    assert settings.pexels_api_key == "secret"
    assert settings.fps == 24


def test_settings_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    original = Settings(output_dir=Path("out"), music_volume=0.4)
    save_settings(original)
    loaded = load_settings(apply_env=False)
    assert loaded.output_dir == Path("out")
    assert loaded.music_volume == 0.4


def test_validate_settings_rejects_bad_volume() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(music_volume=2.0))


def test_stock_providers_default_and_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    settings = Settings(stock_providers=["pixabay", "pexels"])
    save_settings(settings)
    loaded = load_settings(apply_env=False)
    assert loaded.stock_providers == ["pixabay", "pexels"]


def test_stock_providers_default_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from autotube.storage import SettingsStore

    monkeypatch.setenv("APPDATA", str(tmp_path))
    store = SettingsStore()
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text('{"fps": 24}', encoding="utf-8")
    loaded = load_settings(apply_env=False)
    assert loaded.stock_providers == ["pexels", "pixabay"]


def test_stock_providers_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOTUBE_STOCK_PROVIDERS", "pixabay,pexels")
    settings = load_settings()
    assert settings.stock_providers == ["pixabay", "pexels"]


def test_validate_settings_rejects_unknown_stock_provider() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(stock_providers=["unsplash"]))


def test_validate_settings_rejects_duplicate_stock_provider() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(stock_providers=["pexels", "pexels"]))


def test_validate_settings_accepts_empty_stock_providers() -> None:
    validate_settings(Settings(stock_providers=[]))
