"""Product-key normalization, local validation, and redaction."""

from __future__ import annotations

from ..exceptions import LicenseInvalidError
from .constants import (
    LICENSE_ALPHABET,
    LICENSE_CHECKSUM_BASE,
    LICENSE_GROUP_LENGTH,
    LICENSE_KEY_LENGTH,
    LICENSE_PAYLOAD_LENGTH,
    LICENSE_PREFIX,
)


def _checksum_character(payload: str) -> str:
    """CRC24-style checksum over the canonical payload, mapped to Base32."""
    crc = 0xB704CE
    for char in payload:
        crc ^= ord(char) << 16
        for _ in range(8):
            crc <<= 1
            if crc & 0x1000000:
                crc ^= 0x1864CFB
    return LICENSE_ALPHABET[crc % len(LICENSE_ALPHABET)]


def normalize_key(raw: str) -> str:
    """Return the canonical uppercase key with hyphens stripped.

    Raises ``LicenseInvalidError`` on malformed input. The message never
    includes the raw key.
    """
    if not isinstance(raw, str):
        raise LicenseInvalidError("Product key must be text.")

    stripped = "".join(raw.split()).upper().replace("-", "")
    if stripped.startswith(LICENSE_PREFIX):
        stripped = stripped[len(LICENSE_PREFIX) :]

    if len(stripped) != LICENSE_KEY_LENGTH:
        raise LicenseInvalidError("Product key has an invalid length.")

    if any(char not in LICENSE_ALPHABET for char in stripped):
        raise LicenseInvalidError("Product key contains invalid characters.")

    payload = stripped[:LICENSE_PAYLOAD_LENGTH]
    checksum = stripped[LICENSE_PAYLOAD_LENGTH]
    if _checksum_character(payload) != checksum:
        raise LicenseInvalidError("Product key checksum does not match.")

    return stripped


def validate_key_format(raw: str) -> None:
    """Validate a key without returning it (mirrors ``normalize_key``)."""
    normalize_key(raw)


def format_key(canonical: str) -> str:
    """Format a canonical payload+checksum into the user-facing grouped form."""
    payload = canonical[:LICENSE_PAYLOAD_LENGTH]
    checksum = canonical[LICENSE_PAYLOAD_LENGTH:]
    groups = [
        payload[i : i + LICENSE_GROUP_LENGTH]
        for i in range(0, LICENSE_PAYLOAD_LENGTH, LICENSE_GROUP_LENGTH)
    ]
    return f"{LICENSE_PREFIX}-" + "-".join(groups + [checksum])


def redact_key(raw: str) -> str:
    """Return a redacted representation that never leaks original characters."""
    return f"{LICENSE_PREFIX}-" + "-".join(
        ["*" * LICENSE_GROUP_LENGTH] * 4 + ["*"]
    )
