"""Tests for the licensing server admin CLI."""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from licensing_server.admin_cli import main
from licensing_server.database import LicenseDatabase
from licensing_server.generation import format_key, generate_canonical_key
from licensing_server.issuance import verify_activation_token


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


def test_issue_token_accepts_formatted_and_canonical_keys(tmp_path, monkeypatch) -> None:
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(
        "licensing_server.admin_cli.ensure_keypair",
        lambda: (private_key, private_key.public_key()),
    )

    for index, product_key_style in enumerate(("formatted", "canonical")):
        db_dir = tmp_path / str(index)
        db_dir.mkdir()
        db_path = db_dir / "licenses.db"
        canonical = generate_canonical_key()
        LicenseDatabase(db_path).create_license(
            canonical_key=canonical,
            entitlements=["render"],
            machine_limit=1,
            expires_at=None,
        )
        product_key = format_key(canonical) if product_key_style == "formatted" else canonical

        code, token = _capture(
            [
                "issue-token",
                "--product-key",
                product_key,
                "--device-id-hash",
                "a" * 64,
            ],
            monkeypatch,
            db_dir,
        )

        assert code == 0
        assert token.startswith("ATK1.")
        payload = verify_activation_token(
            token.strip(),
            device_id_hash="a" * 64,
            public_key=private_key.public_key(),
        )
        assert payload["device_id_hash"] == "a" * 64
