"""Offline licensing service: verify signed licenses locally.

No network is used. The "product key" supplied by the user is an Ed25519-signed
activation token produced by the separate licensing server's ``issue-token``
command. The client verifies its signature, device binding, expiry, and
entitlements using only the public verification key.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ..exceptions import LicenseInvalidError
from .token import verify_activation_token
from .types import LicenseState, LicenseStatus

NowFn = Callable[[], datetime]


def _default_now() -> datetime:
    return datetime.now(timezone.utc)


def _expires_at_to_datetime(value) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


class OfflineLicensingService:
    """Local-only activation, validation, and deactivation."""

    def __init__(
        self,
        *,
        public_key: Ed25519PublicKey | None = None,
        now: NowFn = _default_now,
    ) -> None:
        self._public_key = public_key
        self._now = now

    def activate(
        self, product_key: str, device_id_hash: str, client_version: str
    ) -> LicenseState:
        """Verify a signed activation token and return activated state."""
        payload = verify_activation_token(
            product_key,
            device_id_hash=device_id_hash,
            public_key=self._public_key,
        )
        now = self._now()
        return LicenseState(
            license_id=str(payload.get("license_id")),
            device_id_hash=device_id_hash,
            activation_token=product_key,
            entitlements=[str(e) for e in payload.get("entitlements", [])],
            expires_at=_expires_at_to_datetime(payload.get("expires_at")),
            activated_at=now,
            last_validated_at=now,
            grace_period_end=None,
            status=LicenseStatus.ACTIVATED,
        )

    def validate(
        self, state: LicenseState, client_version: str
    ) -> LicenseState:
        """Re-verify a stored license locally and refresh its validation time."""
        if not state.activation_token:
            return LicenseState(status=LicenseStatus.INVALID)

        expires_at = state.expires_at
        if expires_at is not None and self._now() >= expires_at:
            return LicenseState(status=LicenseStatus.EXPIRED)

        try:
            payload = verify_activation_token(
                state.activation_token,
                device_id_hash=state.device_id_hash or "",
                public_key=self._public_key,
            )
        except LicenseInvalidError:
            return LicenseState(status=LicenseStatus.INVALID)

        return LicenseState(
            license_id=str(payload.get("license_id")) or state.license_id,
            device_id_hash=state.device_id_hash,
            activation_token=state.activation_token,
            entitlements=[str(e) for e in payload.get("entitlements", [])],
            expires_at=_expires_at_to_datetime(payload.get("expires_at"))
            or state.expires_at,
            activated_at=state.activated_at,
            last_validated_at=self._now(),
            grace_period_end=None,
            status=LicenseStatus.ACTIVATED,
        )

    def deactivate(
        self, state: LicenseState, client_version: str
    ) -> LicenseState:
        """Clear a stored license."""
        return LicenseState(status=LicenseStatus.NOT_ACTIVATED)
