"""License issuance, activation-token signing, and validation."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .database import LicenseDatabase, LicenseRecord

TOKEN_PREFIX = "ATK1."
TOKEN_ALG = "Ed25519"


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _expires_at_to_int(expires_at: str | int | None) -> int | None:
    if expires_at is None:
        return None
    if isinstance(expires_at, int):
        return expires_at
    return int(datetime.fromisoformat(expires_at).timestamp())


def sign_activation_token(
    *,
    license_id: str,
    device_id_hash: str,
    entitlements: list[str],
    expires_at: str | int | None,
    private_key: Ed25519PrivateKey,
) -> str:
    header = {"alg": TOKEN_ALG, "typ": "JWT"}
    payload = {
        "license_id": license_id,
        "device_id_hash": device_id_hash,
        "entitlements": entitlements,
        "expires_at": _expires_at_to_int(expires_at),
        "iat": _now(),
    }
    header_b64 = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header_b64}.{payload_b64}"
    signature = private_key.sign(signing_input.encode("utf-8"))
    return f"{TOKEN_PREFIX}{signing_input}.{_b64encode(signature)}"


def verify_activation_token(
    token: str,
    *,
    device_id_hash: str,
    public_key: Ed25519PublicKey,
) -> dict:
    if not isinstance(token, str) or not token.startswith(TOKEN_PREFIX):
        raise ValueError("Activation token is malformed.")

    signing_input = token[len(TOKEN_PREFIX) :]
    parts = signing_input.split(".")
    if len(parts) != 3:
        raise ValueError("Activation token is malformed.")

    header_b64, payload_b64, signature_b64 = parts
    try:
        header = json.loads(_b64decode(header_b64))
        payload = json.loads(_b64decode(payload_b64))
        signature = _b64decode(signature_b64)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Activation token is malformed.") from exc

    if header.get("alg") != TOKEN_ALG:
        raise ValueError("Activation token algorithm is unsupported.")

    try:
        public_key.verify(signature, f"{header_b64}.{payload_b64}".encode("utf-8"))
    except InvalidSignature as exc:
        raise ValueError("Activation token signature is invalid.") from exc

    if payload.get("device_id_hash") != device_id_hash:
        raise ValueError("Activation token is bound to another device.")

    expires_at = payload.get("expires_at")
    if expires_at is not None and _now() >= int(expires_at):
        raise ValueError("Activation token has expired.")

    return payload


def issue_activation(
    db: LicenseDatabase,
    *,
    license_id: str,
    device_id_hash: str,
    private_key: Ed25519PrivateKey,
) -> dict:
    record = db.get_license(license_id)
    if record is None:
        raise ValueError("License not found.")
    if record.status == "revoked":
        raise ValueError("License is revoked.")
    if record.expires_at:
        expires_dt = datetime.fromisoformat(record.expires_at)
        if datetime.now(timezone.utc) >= expires_dt:
            raise ValueError("License has expired.")

    active = db.count_active_activations(license_id)
    if active >= record.machine_limit:
        # Allow reactivation of an already-known device.
        known = db._conn.execute(
            "SELECT COUNT(*) FROM activations WHERE license_id = ? AND device_id_hash = ? AND status = 'active'",
            (license_id, device_id_hash),
        ).fetchone()
        if int(known[0]) == 0:
            raise ValueError("Machine limit reached for this license.")

    token = sign_activation_token(
        license_id=record.license_id,
        device_id_hash=device_id_hash,
        entitlements=record.entitlements,
        expires_at=record.expires_at,
        private_key=private_key,
    )
    db.upsert_activation(record.license_id, device_id_hash, token)
    return {
        "license_id": record.license_id,
        "status": "activated",
        "entitlements": record.entitlements,
        "expires_at": record.expires_at,
        "machine_limit": record.machine_limit,
        "activation_token": token,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "grace_days": 7,
    }


def validate_activation(
    db: LicenseDatabase,
    *,
    license_id: str,
    device_id_hash: str,
    activation_token: str,
    public_key: Ed25519PublicKey,
) -> dict:
    record = db.get_license(license_id)
    if record is None:
        return {"status": "invalid"}

    try:
        payload = verify_activation_token(
            activation_token, device_id_hash=device_id_hash, public_key=public_key
        )
    except Exception:
        return {"status": "invalid"}

    if record.status == "revoked":
        return {"status": "revoked"}
    if record.expires_at:
        expires_dt = datetime.fromisoformat(record.expires_at)
        if datetime.now(timezone.utc) >= expires_dt:
            return {"status": "expired"}

    db.touch_activation(license_id, device_id_hash)
    return {
        "license_id": record.license_id,
        "status": "activated",
        "entitlements": record.entitlements,
        "expires_at": record.expires_at,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "grace_days": 7,
    }
