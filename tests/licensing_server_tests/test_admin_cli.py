"""Tests for the licensing server admin CLI."""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout

from licensing_server.admin_cli import main
from licensing_server.database import LicenseDatabase


def _capture(args, monkeypatch, tmp_path):
    monkeypatch.setattr("licensing_server.admin_cli.LicenseDatabase", lambda: LicenseDatabase(tmp_path / "licenses.db"))
    monkeypatch.setattr("licensing_server.database.DATABASE_FILE", tmp_path / "licenses.db")
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(args)
    return code, out.getvalue()


def test_generate_key_prints_raw_once(tmp_path, monkeypatch) -> None:
    code, out = _capture(["generate-key"], monkeypatch, tmp_path)
    assert code == 0
    assert "ATK-" in out
    assert "store this product key securely" in out.lower()


def test_list_keys_redacts(tmp_path, monkeypatch) -> None:
    _capture(["generate-key"], monkeypatch, tmp_path)
    code, out = _capture(["list-keys"], monkeypatch, tmp_path)
    assert code == 0
    assert "ATK-*****-*****-*****-*****-*" in out


def test_invalid_command_fails_cleanly(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("licensing_server.admin_cli.LicenseDatabase", lambda: LicenseDatabase(tmp_path / "licenses.db"))
    code = main(["revoke-key", "--license-id", "missing", "--reason", "test"])
    assert code == 1
