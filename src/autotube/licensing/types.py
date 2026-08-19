"""Licensing data types and state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class LicenseStatus(str, Enum):
    NOT_ACTIVATED = "not_activated"
    ACTIVATED = "activated"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ACTIVATION_LIMIT_REACHED = "activation_limit_reached"
    OFFLINE_GRACE = "offline_grace"
    SERVER_UNAVAILABLE = "server_unavailable"


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class LicenseState:
    """Persisted activation state (no raw product key)."""

    license_id: str | None = None
    device_id_hash: str | None = None
    activation_token: str | None = None
    entitlements: list[str] = field(default_factory=list)
    expires_at: datetime | None = None
    activated_at: datetime | None = None
    last_validated_at: datetime | None = None
    grace_period_end: datetime | None = None
    status: LicenseStatus = LicenseStatus.NOT_ACTIVATED

    def to_dict(self) -> dict[str, Any]:
        return {
            "license_id": self.license_id,
            "device_id_hash": self.device_id_hash,
            "activation_token": self.activation_token,
            "entitlements": list(self.entitlements),
            "expires_at": _isoformat(self.expires_at),
            "activated_at": _isoformat(self.activated_at),
            "last_validated_at": _isoformat(self.last_validated_at),
            "grace_period_end": _isoformat(self.grace_period_end),
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LicenseState":
        return cls(
            license_id=data.get("license_id"),
            device_id_hash=data.get("device_id_hash"),
            activation_token=data.get("activation_token"),
            entitlements=[str(e) for e in data.get("entitlements", [])],
            expires_at=_parse_datetime(data.get("expires_at")),
            activated_at=_parse_datetime(data.get("activated_at")),
            last_validated_at=_parse_datetime(data.get("last_validated_at")),
            grace_period_end=_parse_datetime(data.get("grace_period_end")),
            status=LicenseStatus(data.get("status", LicenseStatus.NOT_ACTIVATED.value)),
        )

    def usable(self) -> bool:
        return self.status in (LicenseStatus.ACTIVATED, LicenseStatus.OFFLINE_GRACE)
