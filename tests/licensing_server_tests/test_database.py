"""Tests for the server-side license database."""

from __future__ import annotations

from pathlib import Path

import pytest

from licensing_server.database import LicenseDatabase, _hash_key
from licensing_server.generation import generate_canonical_key


def _db(tmp_path: Path) -> LicenseDatabase:
    return LicenseDatabase(tmp_path / "licenses.db")


def test_insert_and_list(tmp_path: Path) -> None:
    db = _db(tmp_path)
    key = generate_canonical_key()
    record = db.create_license(
        canonical_key=key,
        entitlements=["render"],
        machine_limit=1,
        expires_at=None,
    )
    records = db.list_licenses()
    assert len(records) == 1
    assert records[0].license_id == record.license_id
    db.close()


def test_raw_key_never_stored(tmp_path: Path) -> None:
    db = _db(tmp_path)
    key = generate_canonical_key()
    db.create_license(
        canonical_key=key,
        entitlements=["render"],
        machine_limit=1,
        expires_at=None,
    )
    db.close()
    raw = (tmp_path / "licenses.db").read_bytes()
    assert key.encode() not in raw


def test_duplicate_key_rejected(tmp_path: Path) -> None:
    db = _db(tmp_path)
    key = generate_canonical_key()
    db.create_license(
        canonical_key=key,
        entitlements=["render"],
        machine_limit=1,
        expires_at=None,
    )
    with pytest.raises(ValueError):
        db.create_license(
            canonical_key=key,
            entitlements=["render"],
            machine_limit=1,
            expires_at=None,
        )
    db.close()


def test_revocation_marks_activations(tmp_path: Path) -> None:
    db = _db(tmp_path)
    key = generate_canonical_key()
    record = db.create_license(
        canonical_key=key,
        entitlements=["render"],
        machine_limit=1,
        expires_at=None,
    )
    db.upsert_activation(record.license_id, "a" * 64, "ATK1.token")
    db.revoke_license(record.license_id, "test")
    assert db.get_license(record.license_id).status == "revoked"
    db.close()
