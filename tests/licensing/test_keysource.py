"""Tests for client-side public-key resolution (fail-closed)."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from autotube.exceptions import LicenseConfigurationError
from autotube.licensing.keysource import resolve_public_key
from autotube.licensing.token import verify_activation_token
from licensing_server.issuance import sign_activation_token

DEVICE = "a" * 64


def _sign(private_key):
    return sign_activation_token(
        license_id="lic-1",
        device_id_hash=DEVICE,
        entitlements=["render"],
        expires_at=None,
        private_key=private_key,
    )


def _public_pem(public_key) -> str:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def test_resolve_public_key_from_env(monkeypatch) -> None:
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setenv("AUTOTUBE_LICENSE_PUBLIC_KEY", _public_pem(private_key.public_key()))
    token = _sign(private_key)
    payload = verify_activation_token(token, device_id_hash=DEVICE)
    assert payload["license_id"] == "lic-1"


def test_resolve_public_key_from_file(monkeypatch, tmp_path) -> None:
    private_key = Ed25519PrivateKey.generate()
    path = tmp_path / "public.pem"
    path.write_text(_public_pem(private_key.public_key()), encoding="utf-8")
    monkeypatch.setenv("AUTOTUBE_LICENSE_PUBLIC_KEY_FILE", str(path))
    token = _sign(private_key)
    payload = verify_activation_token(token, device_id_hash=DEVICE)
    assert payload["license_id"] == "lic-1"


def test_resolve_fails_closed_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("AUTOTUBE_LICENSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("AUTOTUBE_LICENSE_PUBLIC_KEY_FILE", raising=False)
    with pytest.raises(LicenseConfigurationError):
        resolve_public_key()


def test_resolve_rejects_wrong_key_type(monkeypatch) -> None:
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv("AUTOTUBE_LICENSE_PUBLIC_KEY", _public_pem(rsa_key.public_key()))
    with pytest.raises(LicenseConfigurationError):
        resolve_public_key()
