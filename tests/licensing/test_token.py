"""Tests for client-side signed activation token verification.

Signing is performed by the separate ``licensing_server`` package; the client
package under test contains no private-key signing capability.
"""

from __future__ import annotations

import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from autotube.exceptions import LicenseInvalidError
from autotube.licensing.token import verify_activation_token
from licensing_server.issuance import sign_activation_token

DEVICE = "a" * 64


def _sign(*, expires_at=None, device=DEVICE, entitlements=None):
    key = Ed25519PrivateKey.generate()
    token = sign_activation_token(
        license_id="lic-1",
        device_id_hash=device,
        entitlements=entitlements or ["render"],
        expires_at=expires_at,
        private_key=key,
    )
    return token, key.public_key()


def test_valid_token_verifies() -> None:
    token, public = _sign()
    payload = verify_activation_token(token, device_id_hash=DEVICE, public_key=public)
    assert payload["license_id"] == "lic-1"
    assert payload["entitlements"] == ["render"]


def test_tampered_token_fails() -> None:
    token, public = _sign()
    tampered = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
    with pytest.raises(LicenseInvalidError):
        verify_activation_token(tampered, device_id_hash=DEVICE, public_key=public)


def test_expired_token_fails() -> None:
    token, public = _sign(expires_at=int(time.time()) - 10)
    with pytest.raises(LicenseInvalidError):
        verify_activation_token(token, device_id_hash=DEVICE, public_key=public)


def test_wrong_public_key_cannot_verify() -> None:
    token, _ = _sign()
    other = Ed25519PrivateKey.generate().public_key()
    with pytest.raises(LicenseInvalidError):
        verify_activation_token(token, device_id_hash=DEVICE, public_key=other)


def test_other_device_fails() -> None:
    token, public = _sign()
    with pytest.raises(LicenseInvalidError):
        verify_activation_token(token, device_id_hash="b" * 64, public_key=public)


def test_malformed_token_fails() -> None:
    with pytest.raises(LicenseInvalidError):
        verify_activation_token("not-a-token", device_id_hash=DEVICE)
