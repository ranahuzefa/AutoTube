"""Public-key resolution for client-side activation-token verification.

The distributed client never embeds a private signing key and never imports the
licensing server. It needs only the server's Ed25519 *public* verification key,
which is resolved at runtime from the first of these sources:

1. The ``AUTOTUBE_LICENSE_PUBLIC_KEY`` environment variable (PEM text).
2. The ``AUTOTUBE_LICENSE_PUBLIC_KEY_FILE`` environment variable (a PEM file).
3. A bundled ``license_public.pem`` beside the running module or, for frozen
   builds, beside the executable.

If none is available, a ``LicenseConfigurationError`` is raised rather than
falling back to a placeholder key, so a misconfigured client fails closed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ..exceptions import LicenseConfigurationError
from .constants import (
    BUNDLED_PUBLIC_KEY_FILE_NAME,
    LICENSE_PUBLIC_KEY_ENV_VAR,
    LICENSE_PUBLIC_KEY_FILE_ENV_VAR,
)


def _load_pem_public_key(pem: str) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(pem.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - key loading boundary
        raise LicenseConfigurationError(
            "License verification public key is invalid."
        ) from exc
    if not isinstance(key, Ed25519PublicKey):
        raise LicenseConfigurationError(
            "License verification public key is not Ed25519."
        )
    return key


def _env_public_key() -> Ed25519PublicKey | None:
    value = os.environ.get(LICENSE_PUBLIC_KEY_ENV_VAR)
    if not value:
        return None
    return _load_pem_public_key(value)


def _env_public_key_file() -> Ed25519PublicKey | None:
    path = os.environ.get(LICENSE_PUBLIC_KEY_FILE_ENV_VAR)
    if not path:
        return None
    candidate = Path(path)
    if not candidate.is_file():
        raise LicenseConfigurationError(
            f"License verification public key file not found: {candidate}"
        )
    return _load_pem_public_key(candidate.read_text(encoding="utf-8"))


def _bundled_public_key_file() -> Path | None:
    module_dir = Path(__file__).resolve().parent
    candidate = module_dir / BUNDLED_PUBLIC_KEY_FILE_NAME
    if candidate.is_file():
        return candidate

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidate = exe_dir / BUNDLED_PUBLIC_KEY_FILE_NAME
        if candidate.is_file():
            return candidate

    return None


def resolve_public_key() -> Ed25519PublicKey:
    """Resolve the server's public verification key, failing closed if unset."""
    key = _env_public_key()
    if key is not None:
        return key

    key = _env_public_key_file()
    if key is not None:
        return key

    path = _bundled_public_key_file()
    if path is not None:
        return _load_pem_public_key(path.read_text(encoding="utf-8"))

    raise LicenseConfigurationError(
        "License verification is not configured. Provide the server public key "
        f"via {LICENSE_PUBLIC_KEY_ENV_VAR}, {LICENSE_PUBLIC_KEY_FILE_ENV_VAR}, "
        f"or a bundled {BUNDLED_PUBLIC_KEY_FILE_NAME} file."
    )
