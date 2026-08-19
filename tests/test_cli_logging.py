"""Tests for CLI and worker crash/logging behavior."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from autotube.cli import main


def test_cli_unhandled_exception_is_logged(
    tmp_path, monkeypatch, capsys
) -> None:
    from autotube import logging_setup

    monkeypatch.setattr(logging_setup, "default_log_directory", lambda: tmp_path / "logs")
    monkeypatch.setattr("autotube.cli._cmd_run", lambda args: (_ for _ in ()).throw(RuntimeError("boom")))

    code = main(["--run", "project.json"])

    assert code == 1
    assert "Unexpected error" in capsys.readouterr().err

    log_file = tmp_path / "logs" / "autotube.log"
    assert log_file.exists()
    text = log_file.read_text(encoding="utf-8")
    assert "Unhandled CLI error" in text
    assert "boom" in text


def test_cli_does_not_log_product_key_on_activation(
    tmp_path, monkeypatch, capsys
) -> None:
    from autotube import logging_setup

    monkeypatch.setattr(logging_setup, "default_log_directory", lambda: tmp_path / "logs")
    monkeypatch.setattr(
        "autotube.cli.OfflineLicensingService",
        lambda: (_ for _ in ()).throw(Exception("ATK-SECRET-123")),
    )

    code = main(["--activate-key", "ATK-SECRET-123"])

    assert code == 1
    log_file = tmp_path / "logs" / "autotube.log"
    text = log_file.read_text(encoding="utf-8")
    assert "ATK-SECRET-123" not in text
