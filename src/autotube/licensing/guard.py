"""Render/export gating helper."""

from __future__ import annotations

from datetime import datetime, timezone

from ..exceptions import LicenseNotActivatedError
from .types import LicenseState, LicenseStatus


class LicenseGuard:
    """Decide whether a gated operation is allowed."""

    def __init__(self, state: LicenseState | None = None) -> None:
        self.state = state

    def ensure_usable(self, state: LicenseState | None = None) -> None:
        current = state or self.state or LicenseState()
        if current.status != LicenseStatus.ACTIVATED:
            raise LicenseNotActivatedError(_reason(current.status))
        if _is_expired(current):
            raise LicenseNotActivatedError("The current license has expired.")
        if "render" not in {e.lower() for e in current.entitlements}:
            raise LicenseNotActivatedError(
                "The current license does not include the render entitlement."
            )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_expired(state: LicenseState) -> bool:
    expires_at = _as_utc(state.expires_at)
    return expires_at is not None and _now() >= expires_at


def _reason(status: LicenseStatus) -> str:
    return {
        LicenseStatus.NOT_ACTIVATED: "A product license is required to render or export.",
        LicenseStatus.INVALID: "The current license is invalid.",
        LicenseStatus.EXPIRED: "The current license has expired.",
        LicenseStatus.REVOKED: "The current license has been revoked.",
        LicenseStatus.ACTIVATION_LIMIT_REACHED: "The activation limit has been reached.",
        LicenseStatus.SERVER_UNAVAILABLE: "License validation is unavailable. Reconnect to re-validate.",
        LicenseStatus.ACTIVATED: "",
        LicenseStatus.OFFLINE_GRACE: "",
    }[status]
