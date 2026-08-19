"""Tests for clean GUI FFmpeg failure behavior."""

from __future__ import annotations

import pytest


def test_gui_run_app_returns_without_ffmpeg(monkeypatch, capsys, tmp_path) -> None:
    from autotube.gui import app as gui_app

    monkeypatch.setattr("autotube.media.detection._which", lambda name: None)
    monkeypatch.setattr("autotube.media.detection._bundled_candidates", lambda name: [])
    monkeypatch.setattr("autotube.logging_setup.default_log_directory", lambda: tmp_path / "logs")

    class _FakeApp:
        def __init__(self, *args):
            pass

        def setApplicationName(self, name):
            pass

    called = {}

    def _fake_critical(parent, title, message):
        called["title"] = title
        called["message"] = message

    monkeypatch.setattr("autotube.gui.app.QApplication", _FakeApp)
    monkeypatch.setattr("autotube.gui.app.QMessageBox.critical", _fake_critical)

    result = gui_app.run_app()

    assert result == 1
    assert called["title"] == "FFmpeg required"
    assert "ffmpeg" in called["message"]
