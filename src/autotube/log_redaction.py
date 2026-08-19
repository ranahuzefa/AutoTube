"""Central log redaction for secrets, tokens, and signed URLs.

The existing ``autotube.redaction.redact_url`` remains the authority for
URL query redaction. This module adds broader, idempotent text redaction used
by the logging pipeline so known secret patterns can never reach a log record
even when an exception message or traceback contains them.
"""

from __future__ import annotations

import logging
import re

# Reuse the same sensitive query-key set as autotube.redaction.
_SENSITIVE_QUERY_KEYS = (
    "key",
    "api_key",
    "apikey",
    "token",
    "auth",
    "authorization",
    "signature",
    "sig",
    "expires",
    "expiry",
    "x-amz-credential",
    "x-amz-signature",
    "x-amz-security-token",
    "x-amz-date",
    "x-amz-algorithm",
    "x-amz-signedheaders",
    "x-amz-expires",
)

_QUERY_ALTERNATION = "|".join(_SENSITIVE_QUERY_KEYS)

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Authorization / bearer credentials.
    (
        re.compile(
            r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?([^\s,;]+)",
        ),
        r"\1***",
    ),
    (
        re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._\-]+)"),
        r"\1***",
    ),
    # JSON-style key-value secrets.
    (
        re.compile(
            r'(?i)("(?:api[_-]?key|apikey|secret|token|password|authorization|'
            r'product[_-]?key|activation[_-]?token|access[_-]?key)"\s*:\s*")'
            r'[^"]*(")',
        ),
        r"\1***\2",
    ),
    # Assignment-style key-value secrets.
    (
        re.compile(
            r"(?i)(\b(?:api[_-]?key|apikey|secret|token|password|authorization|"
            r"access[_-]?key)\b\s*[:=]\s*)([^\s,;]+)",
        ),
        r"\1***",
    ),
    # Sensitive query parameters inside signed or credential URLs.
    (
        re.compile(
            rf"(?i)([?&](?:{_QUERY_ALTERNATION})=)([^&#\s]+)",
        ),
        r"\1***",
    ),
    # Product/license secrets. Product keys and activation tokens are always
    # non-log-safe regardless of surrounding context.
    (
        re.compile(r"ATK1\.[A-Za-z0-9._\-]+"),
        "ATK1.***",
    ),
    (
        re.compile(r"ATK-[A-Z0-9\-]+"),
        "ATK-***",
    ),
]


def redact_text(text: str) -> str:
    """Return ``text`` with known secret patterns replaced by ``***``."""
    if not isinstance(text, str):
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _redact_value(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    return value


class RedactionFilter(logging.Filter):
    """Redact ``record.msg`` and ``record.args`` before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_text(record.msg)
            record.args = _redact_value(record.args)
            if getattr(record, "exc_text", None):
                record.exc_text = redact_text(record.exc_text)
        except Exception:  # noqa: BLE001 - redaction must never crash logging
            pass
        return True


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts the complete final record, including tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))
