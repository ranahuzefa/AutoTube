"""URL redaction helpers for safe error messages."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SENSITIVE_KEYS = {
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
}

_REDACTED = "***"


def redact_url(url: str) -> str:
    """Return ``url`` with sensitive query values replaced by ``***``.

    Non-sensitive query values, the scheme, host, path, and fragment are
    preserved. Malformed or non-string input is returned unchanged.
    """
    if not isinstance(url, str) or not url:
        return url
    parts = urlsplit(url)
    if not parts.query:
        return url

    redacted_pairs = [
        (key, _REDACTED if key.lower() in _SENSITIVE_KEYS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    redacted_query = urlencode(redacted_pairs)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, redacted_query, parts.fragment)
    )
