"""Tests for the license guard."""

from __future__ import annotations

import pytest

from autotube.exceptions import LicenseNotActivatedError
from autotube.licensing.guard import LicenseGuard
from autotube.licensing.types import LicenseState, LicenseStatus


def test_activated_and_grace_allow() -> None:
    for status in (LicenseStatus.ACTIVATED, LicenseStatus.OFFLINE_GRACE):
        LicenseGuard().ensure_usable(LicenseState(status=status))


@pytest.mark.parametrize(
    "status",
    [
        LicenseStatus.NOT_ACTIVATED,
        LicenseStatus.INVALID,
        LicenseStatus.EXPIRED,
        LicenseStatus.REVOKED,
        LicenseStatus.ACTIVATION_LIMIT_REACHED,
        LicenseStatus.SERVER_UNAVAILABLE,
    ],
)
def test_blocked_states_raise_non_sensitive(status) -> None:
    with pytest.raises(LicenseNotActivatedError) as exc:
        LicenseGuard().ensure_usable(LicenseState(status=status))
    message = str(exc.value)
    assert "token" not in message.lower()
    assert "license_id" not in message.lower()
