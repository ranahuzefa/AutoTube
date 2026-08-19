"""Tests for product-key normalization and redaction."""

from __future__ import annotations

import pytest

from autotube.exceptions import LicenseInvalidError
from autotube.licensing.keys import (
    format_key,
    normalize_key,
    redact_key,
    validate_key_format,
)


def _valid_payload() -> str:
    from autotube.licensing.keys import _checksum_character

    payload = "ABCDEFGHJKMNPQRSTVWX"
    return payload + _checksum_character(payload)


def test_valid_key_normalizes() -> None:
    canonical = _valid_payload()
    raw = f"  {canonical[:5]}-{canonical[5:10]}-{canonical[10:15]}-{canonical[15:20]}-{canonical[20]}  "
    assert normalize_key(raw) == canonical


def test_invalid_charset_rejected() -> None:
    with pytest.raises(LicenseInvalidError):
        normalize_key("ATK-11111-11111-11111-11111-I")


def test_wrong_length_rejected() -> None:
    with pytest.raises(LicenseInvalidError):
        normalize_key("ATK-11111-11111-11111-1111")


def test_bad_checksum_rejected() -> None:
    payload = "ABCDEFGHJKMNPQRSTVWX"
    bad = payload + "0"
    with pytest.raises(LicenseInvalidError):
        normalize_key(bad)


def test_redaction_never_returns_original() -> None:
    canonical = _valid_payload()
    redacted = redact_key(canonical)
    assert canonical not in redacted
    assert redacted == "ATK-*****-*****-*****-*****-*"


def test_validate_key_format_mirrors_normalize() -> None:
    canonical = _valid_payload()
    validate_key_format(canonical)


def test_format_key_roundtrip() -> None:
    canonical = _valid_payload()
    formatted = format_key(canonical)
    assert normalize_key(formatted) == canonical
