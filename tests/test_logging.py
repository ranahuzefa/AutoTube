"""Tests for production logging setup, redaction, and crash handling."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from autotube.log_redaction import (
    RedactingFormatter,
    RedactionFilter,
    redact_text,
)
from autotube.logging_setup import default_log_directory, setup_logging


def _reset_autotube_logger() -> logging.Logger:
    logger = logging.getLogger("autotube")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.propagate = False
    return logger


def test_redact_text_hides_authorization() -> None:
    text = "Authorization: Bearer sk-1234567890"
    redacted = redact_text(text)
    assert "sk-1234567890" not in redacted
    assert "***" in redacted


def test_redact_text_hides_json_secrets() -> None:
    text = '{"api_key": "pexels-secret", "token": "abc"}'
    redacted = redact_text(text)
    assert "pexels-secret" not in redacted
    assert "abc" not in redacted


def test_redact_text_hides_signed_url() -> None:
    text = "https://example.com/file?signature=abcdef&token=12345"
    redacted = redact_text(text)
    assert "abcdef" not in redacted
    assert "12345" not in redacted


def test_redact_text_hides_license_secrets() -> None:
    text = "activation_token=ATK1.eyJhbGciOiJFZDI1NTE5In0.product-key"
    redacted = redact_text(text)
    assert "eyJhbGciOiJFZDI1NTE5In0" not in redacted
    assert "product-key" not in redacted


def test_redact_text_is_idempotent() -> None:
    text = "Authorization: Bearer sk-1234567890"
    once = redact_text(text)
    twice = redact_text(once)
    assert twice == once


def test_setup_logging_creates_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    logger = _reset_autotube_logger()
    setup_logging(log_directory=tmp_path / "logs")
    logger.info("hello-log")
    for handler in logger.handlers:
        handler.flush()

    log_file = tmp_path / "logs" / "autotube.log"
    assert log_file.exists()
    assert "hello-log" in log_file.read_text(encoding="utf-8")


def test_setup_logging_rotates(tmp_path) -> None:
    logger = _reset_autotube_logger()
    log_file = tmp_path / "rotating.log"
    setup_logging(log_file=log_file)
    file_handlers = [
        h for h in logger.handlers if hasattr(h, "baseFilename")
    ]
    assert file_handlers
    assert file_handlers[0].maxBytes == 1_000_000
    assert file_handlers[0].backupCount == 3


def test_default_log_directory_uses_appdata(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert default_log_directory() == tmp_path / "AutoTube" / "logs"


def test_redaction_filter_redacts_args() -> None:
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname="", lineno=0,
        msg="Authorization: %s", args=("Bearer sk-1234567890",), exc_info=None,
    )
    RedactionFilter().filter(record)
    assert "sk-1234567890" not in record.args[0]
    assert record.args[0] == "Bearer ***"


def test_redacting_formatter_redacts_traceback() -> None:
    formatter = RedactingFormatter("%(message)s")
    record = logging.LogRecord(
        name="t", level=logging.ERROR, pathname="", lineno=0,
        msg="failed", args=(), exc_info=None,
    )
    record.exc_text = "Authorization: Bearer sk-secret"
    assert "sk-secret" not in formatter.format(record)
