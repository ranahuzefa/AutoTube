"""Signed activation-token verification (client-side, verification-only).

The distributed client embeds only an Ed25519 **public** verification key,
resolved at runtime via :mod:`autotube.licensing.keysource`. Tokens are minted
by the separate licensing server with the corresponding private key, which
never ships in the client. This module can verify an existing token but cannot
sign or extend one.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ..exceptions import LicenseInvalidError
from .keysource import resolve_public_key

TOKEN_PREFIX = "ATK1."
TOKEN_ALG = "Ed25519"


def _b64decode(value: str) -> bytes:
    try:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:  # noqa: BLE001
        raise LicenseInvalidError("Activation token is malformed.") from exc


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def verify_activation_token(
    token: str,
    *,
    device_id_hash: str,
    public_key: Ed25519PublicKey | None = None,
) -> dict:
    """Verify a signed activation token and return its decoded payload.

    Raises ``LicenseInvalidError`` when the token is malformed, tampered,
    expired, or bound to another device. When ``public_key`` is omitted it is
    resolved through the configured public-key source.
    """
    if not isinstance(token, str) or not token.startswith(TOKEN_PREFIX):
        raise LicenseInvalidError("Activation token is malformed.")

    signing_input = token[len(TOKEN_PREFIX) :]
    parts = signing_input.split(".")
    if len(parts) != 3:
        raise LicenseInvalidError("Activation token is malformed.")

    header_b64, payload_b64, signature_b64 = parts

    try:
        header = json.loads(_b64decode(header_b64))
        payload = json.loads(_b64decode(payload_b64))
        signature = _b64decode(signature_b64)
    except (ValueError, json.JSONDecodeError) as exc:
        raise LicenseInvalidError("Activation token is malformed.") from exc

    if header.get("alg") != TOKEN_ALG:
        raise LicenseInvalidError("Activation token algorithm is unsupported.")

    key = public_key or resolve_public_key()
    try:
        key.verify(signature, f"{header_b64}.{payload_b64}".encode("utf-8"))
    except InvalidSignature as exc:
        raise LicenseInvalidError("Activation token signature is invalid.") from exc

    if payload.get("device_id_hash") != device_id_hash:
        raise LicenseInvalidError("Activation token is bound to another device.")

    expires_at = payload.get("expires_at")
    if expires_at is not None and _now() >= int(expires_at):
        raise LicenseInvalidError("Activation token has expired.")

    return payload
