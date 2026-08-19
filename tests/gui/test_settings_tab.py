"""Tests for the settings tab stock provider controls."""

from __future__ import annotations

import pytest

from PySide6.QtCore import Qt

from autotube.config import Settings
from autotube.gui.settings_tab import SettingsTab


@pytest.fixture
def tab(qt_app):
    return SettingsTab()


def _items(tab: SettingsTab):
    return [tab.stock_provider_list.item(i) for i in range(tab.stock_provider_list.count())]


def test_stock_list_populated_from_registry(tab: SettingsTab) -> None:
    ids = [item.data(32) for item in _items(tab)]
    assert ids == ["pexels", "pixabay"]


def test_load_settings_sets_checks_and_order(tab: SettingsTab) -> None:
    tab.load_settings(Settings(stock_providers=["pixabay"]))
    items = _items(tab)
    assert [item.data(32) for item in items] == ["pixabay", "pexels"]
    assert items[0].checkState() == Qt.CheckState.Checked
    assert items[1].checkState() == Qt.CheckState.Unchecked


def test_load_settings_roundtrip_default(tab: SettingsTab) -> None:
    tab.load_settings(Settings())
    items = _items(tab)
    assert [item.data(32) for item in items] == ["pexels", "pixabay"]
    assert [item.checkState() for item in items] == [
        Qt.CheckState.Checked,
        Qt.CheckState.Checked,
    ]


def test_move_up_and_down(tab: SettingsTab) -> None:
    tab.load_settings(Settings(stock_providers=["pexels", "pixabay"]))
    tab.stock_provider_list.setCurrentRow(1)
    tab._move_provider_up()
    assert [item.data(32) for item in _items(tab)] == ["pixabay", "pexels"]
    tab._move_provider_down()
    assert [item.data(32) for item in _items(tab)] == ["pexels", "pixabay"]


def test_provider_order_only_checked(tab: SettingsTab) -> None:
    tab.load_settings(Settings(stock_providers=["pexels", "pixabay"]))
    items = _items(tab)
    items[1].setCheckState(Qt.CheckState.Unchecked)
    assert tab._provider_order() == ["pexels"]


def test_save_writes_legacy_keys_and_providers(
    tab: SettingsTab, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def _fake_save(settings: Settings) -> None:
        captured["settings"] = settings

    monkeypatch.setattr("autotube.gui.settings_tab.save_settings", _fake_save)
    monkeypatch.setattr(
        "autotube.gui.settings_tab.QMessageBox.information", lambda *a, **k: None
    )

    tab.load_settings(Settings(stock_providers=["pixabay", "pexels"]))
    tab.pexels_edit.setText("pex")
    tab.pixabay_edit.setText("pix")
    tab._save()

    settings = captured["settings"]
    assert settings.pexels_api_key == "pex"
    assert settings.pixabay_api_key == "pix"
    assert settings.stock_providers == ["pixabay", "pexels"]


def test_env_status_shows_set_and_unset(
    tab: SettingsTab, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PEXELS_API_KEY", "x")
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    tab._refresh_stock_key_status()
    assert "PEXELS_API_KEY: SET" in tab.stock_key_status_label.text()
    assert "PIXABAY_API_KEY: UNSET" in tab.stock_key_status_label.text()


def test_image_video_generation_rows_load_save(
    tab: SettingsTab, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def _fake_save(settings: Settings) -> None:
        captured["settings"] = settings

    monkeypatch.setattr("autotube.gui.settings_tab.save_settings", _fake_save)
    monkeypatch.setattr(
        "autotube.gui.settings_tab.QMessageBox.information", lambda *a, **k: None
    )

    settings = Settings(
        ai_image_enabled=False,
        ai_image_provider="",
        ai_image_model="img-model",
        ai_image_api_key_env_var="IMG_KEY",
        ai_image_base_url="https://img.example/v1",
        ai_image_timeout=45.0,
        ai_video_enabled=False,
        ai_video_model="vid-model",
        ai_video_timeout=90.0,
    )
    tab.load_settings(settings)
    tab._save()

    saved = captured["settings"]
    assert saved.ai_image_enabled is False
    assert saved.ai_image_model == "img-model"
    assert saved.ai_image_timeout == 45.0
    assert saved.ai_video_enabled is False
    assert saved.ai_video_model == "vid-model"
    assert saved.ai_video_timeout == 90.0


def test_generation_env_status(
    tab: SettingsTab, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IMG_KEY", "x")
    monkeypatch.delenv("VID_KEY", raising=False)
    tab.load_settings(
        Settings(
            ai_image_api_key_env_var="IMG_KEY",
            ai_video_api_key_env_var="VID_KEY",
        )
    )
    assert tab.ai_image_key_status_label.text() == "SET"
    assert tab.ai_video_key_status_label.text() == "UNSET"
