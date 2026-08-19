"""License validation orchestration (offline-only)."""

from __future__ import annotations

from .guard import LicenseGuard
from .offline import OfflineLicensingService
from .storage import LicenseStore
from .types import LicenseState


def ensure_usable_and_fresh(
    state: LicenseState | None = None,
    *,
    store: LicenseStore | None = None,
    client: OfflineLicensingService | None = None,
    client_version: str = "1.0.0",
) -> LicenseState:
    """Validate locally and return a usable license state.

    A stored activation token is re-verified against the configured public key
    and expiry; ``LicenseGuard`` performs the final status and entitlement
    check. No network is used.
    """
    current = state or (store or LicenseStore()).load()
    refreshed = (client or OfflineLicensingService()).validate(
        current, client_version
    )

    guard = LicenseGuard()
    guard.ensure_usable(refreshed)

    if store is not None and refreshed.status != current.status:
        store.save(refreshed)

    return refreshed
