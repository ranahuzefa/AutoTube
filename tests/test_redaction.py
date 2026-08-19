"""Tests for URL redaction."""

from __future__ import annotations

from autotube.redaction import redact_url


def test_redacts_sensitive_query_values() -> None:
    url = (
        "https://pixabay.com/api/videos/?key=SECRETKEY&q=ocean&per_page=3"
    )
    redacted = redact_url(url)
    assert "SECRETKEY" not in redacted
    assert "key=%2A%2A%2A" in redacted
    assert "q=ocean" in redacted
    assert "per_page=3" in redacted


def test_redacts_signed_cdn_query_values() -> None:
    url = (
        "https://cdn.example.com/v.mp4"
        "?Signature=abc123&Expires=12345&x-amz-credential=cred"
        "&non_sensitive=ok"
    )
    redacted = redact_url(url)
    assert "abc123" not in redacted
    assert "12345" not in redacted
    assert "cred" not in redacted.split("x-amz-credential=")[1].split("&")[0]
    assert "non_sensitive=ok" in redacted


def test_preserves_scheme_host_path() -> None:
    url = "https://example.com/path/to?token=secret&page=2"
    redacted = redact_url(url)
    assert redacted.startswith("https://example.com/path/to?")
    assert "token=%2A%2A%2A" in redacted
    assert "page=2" in redacted


def test_no_query_returns_unchanged() -> None:
    url = "https://example.com/path"
    assert redact_url(url) == url


def test_non_string_returns_unchanged() -> None:
    assert redact_url(None) is None
    assert redact_url("") == ""
