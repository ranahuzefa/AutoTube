"""Tests for the offline licensing service."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from autotube.exceptions import LicenseInvalidError
from autotube.licensing.offline import OfflineLicensingService
from autotube.licensing.storage import LicenseStore
from autotube.licensing.types import LicenseState, LicenseStatus
from licensing_server.issuance import sign_activation_token

DEVICE = "a" * 64


def _sign(
    private_key: Ed25519PrivateKey,
    *,
    device: str = DEVICE,
    entitlements=None,
    expires_at=None,
) -> str:
    return sign_activation_token(
        license_id="lic-1",
        device_id_hash=device,
        entitlements=entitlements or ["render"],
        expires_at=expires_at,
        private_key=private_key,
    )


def _service(private_key, now=None) -> OfflineLicensingService:
    return OfflineLicensingService(
        public_key=private_key.public_key(),
        now=now or (lambda: datetime.now(timezone.utc)),
    )


def test_activate_valid_token() -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _sign(private_key)
    state = _service(private_key).activate(token, DEVICE, "1.0.0")
    assert state.status == LicenseStatus.ACTIVATED
    assert state.license_id == "lic-1"
    assert state.entitlements == ["render"]


def test_activate_persists_signed_activation_token_and_round_trips(tmp_path) -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _sign(private_key)
    state = _service(private_key).activate(token, DEVICE, "1.0.0")
    store = LicenseStore(directory=tmp_path)
    store.save(state)

    serialized = state.to_dict()
    assert serialized["activation_token"] == token
    assert "product_key" not in serialized
    assert "ATK-XXXXX-XXXXX-XXXXX-XXXXX-X" not in str(serialized)

    restored = store.load()
    assert restored.activation_token == token
    validated = _service(private_key).validate(restored, "1.0.0")
    assert validated.status == LicenseStatus.ACTIVATED
    assert validated.activation_token == token


def test_deactivate_clears_persisted_activation_token(tmp_path) -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _sign(private_key)
    store = LicenseStore(directory=tmp_path)
    store.save(_service(private_key).activate(token, DEVICE, "1.0.0"))

    deactivated = _service(private_key).deactivate(store.load(), "1.0.0")
    store.save(deactivated)

    restored = store.load()
    assert restored.status == LicenseStatus.NOT_ACTIVATED
    assert restored.activation_token is None


def test_activate_wrong_device_rejected() -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _sign(private_key, device="b" * 64)
    with pytest.raises(LicenseInvalidError):
        _service(private_key).activate(token, DEVICE, "1.0.0")


def test_activate_tampered_token_rejected() -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _sign(private_key)
    tampered = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
    with pytest.raises(LicenseInvalidError):
        _service(private_key).activate(tampered, DEVICE, "1.0.0")


def test_activate_expired_token_rejected() -> None:
    private_key = Ed25519PrivateKey.generate()
    expired_at = int(datetime.now(timezone.utc).timestamp()) - 10
    token = _sign(private_key, expires_at=expired_at)
    with pytest.raises(LicenseInvalidError):
        _service(private_key).activate(token, DEVICE, "1.0.0")


def test_validate_reverifies_valid_token() -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _sign(private_key)
    service = _service(private_key)
    state = service.activate(token, DEVICE, "1.0.0")
    validated = service.validate(state, "1.0.0")
    assert validated.status == LicenseStatus.ACTIVATED


def test_validate_expired_state_returns_expired() -> None:
    private_key = Ed25519PrivateKey.generate()
    token = _sign(private_key, expires_at=int(datetime.now(timezone.utc).timestamp()) + 5)
    service = _service(private_key)
    state = service.activate(token, DEVICE, "1.0.0")

    later = datetime.fromtimestamp(state.expires_at.timestamp(), tz=timezone.utc)
    service_expired = OfflineLicensingService(
        public_key=private_key.public_key(),
        now=lambda: later,
    )
    validated = service_expired.validate(state, "1.0.0")
    assert validated.status == LicenseStatus.EXPIRED


def test_validate_missing_token_returns_invalid() -> None:
    private_key = Ed25519PrivateKey.generate()
    state = LicenseState(status=LicenseStatus.ACTIVATED, device_id_hash=DEVICE)
    validated = _service(private_key).validate(state, "1.0.0")
    assert validated.status == LicenseStatus.INVALID


def test_deactivate_returns_not_activated() -> None:
    private_key = Ed25519PrivateKey.generate()
    state = LicenseState(status=LicenseStatus.ACTIVATED)
    result = _service(private_key).deactivate(state, "1.0.0")
    assert result.status == LicenseStatus.NOT_ACTIVATED


def test_offline_module_has_no_http_imports() -> None:
    import autotube.licensing.offline as offline

    source = open(offline.__file__, encoding="utf-8").read()
    assert "urllib" not in source
    assert "http" not in source
