"""Tests for secure product-key generation."""

from __future__ import annotations

from autotube.licensing.keys import normalize_key
from licensing_server.generation import (
    format_key,
    generate_canonical_key,
    redact_key,
)


def test_generated_key_normalizes() -> None:
    canonical = generate_canonical_key()
    formatted = format_key(canonical)
    assert normalize_key(formatted) == canonical


def test_payload_has_100_bits_entropy() -> None:
    canonical = generate_canonical_key()
    assert len(canonical) == 21
    assert len(canonical[:-1]) == 20


def test_keys_are_unique() -> None:
    keys = {generate_canonical_key() for _ in range(100)}
    assert len(keys) == 100


def test_redaction_hides_key() -> None:
    canonical = generate_canonical_key()
    redacted = redact_key()
    assert canonical not in redacted
    assert redacted == "ATK-*****-*****-*****-*****-*"
