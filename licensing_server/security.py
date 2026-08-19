"""Security and redaction helpers for the licensing server."""

from __future__ import annotations


def redact_private_key(key_pem: str) -> str:
    return "***PRIVATE KEY REDACTED***"


def redact_activation_token(token: str) -> str:
    return token[:6] + "***" if token else "***"
