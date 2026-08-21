"""Product-key generation compatible with the distributed client format."""

from __future__ import annotations

import secrets

from .constants import (
    PRODUCT_KEY_ALPHABET,
    PRODUCT_KEY_PAYLOAD_LENGTH,
    PRODUCT_KEY_PREFIX,
)


def _checksum_character(payload: str) -> str:
    crc = 0xB704CE
    for char in payload:
        crc ^= ord(char) << 16
        for _ in range(8):
            crc <<= 1
            if crc & 0x1000000:
                crc ^= 0x1864CFB
    return PRODUCT_KEY_ALPHABET[crc % len(PRODUCT_KEY_ALPHABET)]


def generate_canonical_key() -> str:
    """Return a canonical payload+checksum string (21 characters)."""
    payload = "".join(
        secrets.choice(PRODUCT_KEY_ALPHABET)
        for _ in range(PRODUCT_KEY_PAYLOAD_LENGTH)
    )
    return payload + _checksum_character(payload)


def normalize_product_key(raw: str) -> str:
    """Return the canonical key after validating the user-facing form."""
    if not isinstance(raw, str):
        raise ValueError("Product key must be text.")

    stripped = "".join(raw.split()).upper().replace("-", "")
    if stripped.startswith(PRODUCT_KEY_PREFIX):
        stripped = stripped[len(PRODUCT_KEY_PREFIX) :]

    expected_length = PRODUCT_KEY_PAYLOAD_LENGTH + 1
    if len(stripped) != expected_length:
        raise ValueError("Product key has an invalid length.")
    if any(char not in PRODUCT_KEY_ALPHABET for char in stripped):
        raise ValueError("Product key contains invalid characters.")

    payload = stripped[:PRODUCT_KEY_PAYLOAD_LENGTH]
    if _checksum_character(payload) != stripped[PRODUCT_KEY_PAYLOAD_LENGTH]:
        raise ValueError("Product key checksum does not match.")
    return stripped


def format_key(canonical: str) -> str:
    """Format a canonical key into ``ATK-XXXXX-XXXXX-XXXXX-XXXXX-C``."""
    payload = canonical[:PRODUCT_KEY_PAYLOAD_LENGTH]
    checksum = canonical[PRODUCT_KEY_PAYLOAD_LENGTH:]
    groups = [
        payload[i : i + 5]
        for i in range(0, PRODUCT_KEY_PAYLOAD_LENGTH, 5)
    ]
    return f"{PRODUCT_KEY_PREFIX}-" + "-".join(groups + [checksum])


def redact_key() -> str:
    return f"{PRODUCT_KEY_PREFIX}-" + "-".join(["*" * 5] * 4 + ["*"])
