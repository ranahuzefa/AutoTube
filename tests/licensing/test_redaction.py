"""Tests for product-key redaction in errors and logs."""

from __future__ import annotations

import logging

import pytest

from autotube.exceptions import LicenseInvalidError
from autotube.licensing.keys import normalize_key, redact_key

RAW_KEY = "ATK-ABCDEFGHJKMNPQRSTVWXY"


def test_exception_never_contains_raw_key() -> None:
    try:
        normalize_key(RAW_KEY)
    except LicenseInvalidError as exc:
        assert RAW_KEY not in str(exc)
        assert redact_key(RAW_KEY) not in str(exc)
    else:
        # The fixture key is deliberately invalid; ensure the branch ran.
        pytest.fail("expected invalid key")


def test_log_messages_never_contain_raw_key(caplog) -> None:
    logger = logging.getLogger("autotube.licensing.redaction")
    with caplog.at_level(logging.ERROR):
        try:
            normalize_key(RAW_KEY)
        except LicenseInvalidError as exc:
            logger.error("Activation failed: %s", exc)
    assert RAW_KEY not in caplog.text
