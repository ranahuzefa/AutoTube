"""Tests for license re-validation and offline-grace orchestration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from autotube.exceptions import (
    LicenseNotActivatedError,
    LicenseServerUnavailableError,
)
from autotube.licensing.client import LicensingClient
from autotube.licensing.runtime import (
    ensure_usable_and_fresh,
    needs_revalidation,
)
from autotube.licensing.storage import LicenseStore
from autotube.licensing.types import LicenseState, LicenseStatus

DEVICE = "a" * 64


def _state(status=LicenseStatus.ACTIVATED, **overrides) -> LicenseState:
    now = datetime.now(timezone.utc)
    base = dict(
        license_id="lic-1",
        device_id_hash=DEVICE,
        activation_token="ATK1.token",
        entitlements=["render"],
        activated_at=now - timedelta(days=1),
        last_validated_at=now,
        grace_period_end=now + timedelta(days=7),
        status=status,
    )
    base.update(overrides)
    return LicenseState(**base)


class _FakeClient:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc
        self.calls = 0

    def validate(self, state, client_version):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.result


def test_needs_revalidation_when_activated_and_stale() -> None:
    state = _state(last_validated_at=datetime.now(timezone.utc) - timedelta(hours=7))
    assert needs_revalidation(state) is True


def test_needs_revalidation_false_when_fresh() -> None:
    assert needs_revalidation(_state()) is False


def test_needs_revalidation_false_when_not_activated() -> None:
    assert needs_revalidation(_state(status=LicenseStatus.NOT_ACTIVATED)) is False


def test_fresh_usable_state_not_revalidated(tmp_path) -> None:
    store = LicenseStore(directory=tmp_path)
    store.save(_state())
    client = _FakeClient(result=_state())
    result = ensure_usable_and_fresh(
        store.load(), store=store, client=client, client_version="0.1.0"
    )
    assert result.status == LicenseStatus.ACTIVATED
    assert client.calls == 0


def test_stale_state_revalidates(tmp_path) -> None:
    stale = _state(last_validated_at=datetime.now(timezone.utc) - timedelta(hours=8))
    store = LicenseStore(directory=tmp_path)
    store.save(stale)
    fresh = _state()
    client = _FakeClient(result=fresh)
    result = ensure_usable_and_fresh(
        store.load(), store=store, client=client, client_version="0.1.0"
    )
    assert client.calls == 1
    assert result.status == LicenseStatus.ACTIVATED


def test_revoked_revalidation_blocks(tmp_path) -> None:
    stale = _state(last_validated_at=datetime.now(timezone.utc) - timedelta(hours=8))
    store = LicenseStore(directory=tmp_path)
    store.save(stale)
    client = _FakeClient(result=_state(status=LicenseStatus.REVOKED))
    with pytest.raises(LicenseNotActivatedError):
        ensure_usable_and_fresh(
            store.load(), store=store, client=client, client_version="0.1.0"
        )


def test_expired_revalidation_blocks(tmp_path) -> None:
    stale = _state(last_validated_at=datetime.now(timezone.utc) - timedelta(hours=8))
    store = LicenseStore(directory=tmp_path)
    store.save(stale)
    client = _FakeClient(result=_state(status=LicenseStatus.EXPIRED))
    with pytest.raises(LicenseNotActivatedError):
        ensure_usable_and_fresh(
            store.load(), store=store, client=client, client_version="0.1.0"
        )


def test_invalid_revalidation_blocks(tmp_path) -> None:
    stale = _state(last_validated_at=datetime.now(timezone.utc) - timedelta(hours=8))
    store = LicenseStore(directory=tmp_path)
    store.save(stale)
    client = _FakeClient(result=_state(status=LicenseStatus.INVALID))
    with pytest.raises(LicenseNotActivatedError):
        ensure_usable_and_fresh(
            store.load(), store=store, client=client, client_version="0.1.0"
        )


def test_not_activated_state_blocks_without_request(tmp_path) -> None:
    store = LicenseStore(directory=tmp_path)
    store.save(_state(status=LicenseStatus.NOT_ACTIVATED))
    client = _FakeClient(result=_state())
    with pytest.raises(LicenseNotActivatedError):
        ensure_usable_and_fresh(
            store.load(), store=store, client=client, client_version="0.1.0"
        )
    assert client.calls == 0


def test_server_unavailable_within_grace_enters_offline_grace(tmp_path) -> None:
    stale = _state(last_validated_at=datetime.now(timezone.utc) - timedelta(hours=8))
    store = LicenseStore(directory=tmp_path)
    store.save(stale)
    client = _FakeClient(exc=LicenseServerUnavailableError("down"))
    result = ensure_usable_and_fresh(
        store.load(), store=store, client=client, client_version="0.1.0"
    )
    assert result.status == LicenseStatus.OFFLINE_GRACE
    assert store.load().status == LicenseStatus.OFFLINE_GRACE


def test_server_unavailable_after_grace_blocks(tmp_path) -> None:
    now = datetime.now(timezone.utc)
    stale = _state(
        last_validated_at=now - timedelta(hours=8),
        grace_period_end=now - timedelta(seconds=1),
    )
    store = LicenseStore(directory=tmp_path)
    store.save(stale)
    client = _FakeClient(exc=LicenseServerUnavailableError("down"))
    with pytest.raises(LicenseNotActivatedError):
        ensure_usable_and_fresh(
            store.load(), store=store, client=client, client_version="0.1.0"
        )
    assert store.load().status == LicenseStatus.SERVER_UNAVAILABLE


def test_guard_blocks_expired_timestamp() -> None:
    from autotube.licensing.guard import LicenseGuard

    expired = _state(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    with pytest.raises(LicenseNotActivatedError):
        LicenseGuard().ensure_usable(expired)


def test_guard_allows_future_expiry() -> None:
    from autotube.licensing.guard import LicenseGuard

    valid = _state(expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    LicenseGuard().ensure_usable(valid)


def test_guard_blocks_offline_grace_past_grace() -> None:
    from autotube.licensing.guard import LicenseGuard

    state = _state(
        status=LicenseStatus.OFFLINE_GRACE,
        grace_period_end=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    with pytest.raises(LicenseNotActivatedError):
        LicenseGuard().ensure_usable(state)
