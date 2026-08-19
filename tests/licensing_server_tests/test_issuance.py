"""Tests for license issuance, signing, validation, and machine limits."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from licensing_server.database import LicenseDatabase
from licensing_server.generation import generate_canonical_key
from licensing_server.issuance import issue_activation, validate_activation


def _expiry(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_valid_token_issues_and_validates(tmp_path: Path) -> None:
    db = LicenseDatabase(tmp_path / "licenses.db")
    key = generate_canonical_key()
    record = db.create_license(
        canonical_key=key,
        entitlements=["render"],
        machine_limit=1,
        expires_at=None,
    )
    private_key = Ed25519PrivateKey.generate()
    result = issue_activation(
        db,
        license_id=record.license_id,
        device_id_hash="a" * 64,
        private_key=private_key,
    )
    assert result["status"] == "activated"
    assert result["activation_token"].startswith("ATK1.")

    validated = validate_activation(
        db,
        license_id=record.license_id,
        device_id_hash="a" * 64,
        activation_token=result["activation_token"],
        public_key=private_key.public_key(),
    )
    assert validated["status"] == "activated"
    db.close()


def test_expired_license_cannot_issue(tmp_path: Path) -> None:
    db = LicenseDatabase(tmp_path / "licenses.db")
    key = generate_canonical_key()
    record = db.create_license(
        canonical_key=key,
        entitlements=["render"],
        machine_limit=1,
        expires_at=_expiry(-1),
    )
    with pytest.raises(ValueError):
        issue_activation(
            db,
            license_id=record.license_id,
            device_id_hash="a" * 64,
            private_key=Ed25519PrivateKey.generate(),
        )
    db.close()


def test_revoked_license_cannot_issue_or_validate(tmp_path: Path) -> None:
    db = LicenseDatabase(tmp_path / "licenses.db")
    key = generate_canonical_key()
    record = db.create_license(
        canonical_key=key,
        entitlements=["render"],
        machine_limit=1,
        expires_at=None,
    )
    private_key = Ed25519PrivateKey.generate()
    result = issue_activation(
        db,
        license_id=record.license_id,
        device_id_hash="a" * 64,
        private_key=private_key,
    )
    db.revoke_license(record.license_id, "test")
    validated = validate_activation(
        db,
        license_id=record.license_id,
        device_id_hash="a" * 64,
        activation_token=result["activation_token"],
        public_key=private_key.public_key(),
    )
    assert validated["status"] == "revoked"
    db.close()


def test_machine_limit_enforced(tmp_path: Path) -> None:
    db = LicenseDatabase(tmp_path / "licenses.db")
    key = generate_canonical_key()
    record = db.create_license(
        canonical_key=key,
        entitlements=["render"],
        machine_limit=1,
        expires_at=None,
    )
    private_key = Ed25519PrivateKey.generate()
    issue_activation(
        db,
        license_id=record.license_id,
        device_id_hash="a" * 64,
        private_key=private_key,
    )
    with pytest.raises(ValueError):
        issue_activation(
            db,
            license_id=record.license_id,
            device_id_hash="b" * 64,
            private_key=private_key,
        )
    db.close()
