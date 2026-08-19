"""Tests for worker signal routing and cancellation classification."""

from __future__ import annotations

import pytest

from autotube.exceptions import (
    AutoTubeError,
    MediaCancelledError,
    is_cancellation,
)
from autotube.gui.workers import Worker


def test_is_cancellation_typed() -> None:
    assert is_cancellation(MediaCancelledError("x"))
    assert not is_cancellation(RuntimeError("x"))


def test_is_cancellation_known_message() -> None:
    assert is_cancellation(AutoTubeError("Pipeline cancelled."))
    assert not is_cancellation(AutoTubeError("Something failed."))


def test_worker_routes_cancelled(qt_app) -> None:
    seen = {}

    def boom():
        raise AutoTubeError("Pipeline cancelled.")

    worker = Worker(boom)
    worker.signals.cancelled.connect(lambda m: seen.setdefault("cancelled", m))
    worker.signals.failed.connect(lambda m: seen.setdefault("failed", m))
    worker.run()
    assert "cancelled" in seen
    assert "failed" not in seen


def test_worker_routes_failed(qt_app) -> None:
    seen = {}

    def boom():
        raise RuntimeError("boom")

    worker = Worker(boom)
    worker.signals.cancelled.connect(lambda m: seen.setdefault("cancelled", m))
    worker.signals.failed.connect(lambda m: seen.setdefault("failed", m))
    worker.run()
    assert "failed" in seen
    assert "cancelled" not in seen


def test_worker_logs_traceback_without_secrets(qt_app, tmp_path) -> None:
    import logging
    from autotube.logging_setup import setup_logging

    logger = logging.getLogger("autotube")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.propagate = False

    log_file = tmp_path / "worker.log"
    setup_logging(log_file=log_file)

    def boom():
        raise RuntimeError("Authorization: Bearer sk-1234567890")

    worker = Worker(boom)
    worker.signals.failed.connect(lambda m: None)
    worker.run()

    for handler in logger.handlers:
        handler.flush()
    text = log_file.read_text(encoding="utf-8")
    assert "Traceback" in text
    assert "sk-1234567890" not in text


def test_worker_routes_finished(qt_app) -> None:
    seen = {}

    def ok():
        return "done"

    worker = Worker(ok)
    worker.signals.finished.connect(lambda r: seen.setdefault("finished", r))
    worker.run()
    assert seen.get("finished") == "done"
