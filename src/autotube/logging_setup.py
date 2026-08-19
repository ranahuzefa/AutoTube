"""Logging setup with console, rotating file, and optional GUI signal handler."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from .log_redaction import RedactingFormatter, RedactionFilter

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DEFAULT_LOG_FILE_NAME = "autotube.log"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3


def default_log_directory() -> Path:
    """Return the AutoTube user-config directory for logs."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "AutoTube" / "logs"
    return Path.home() / ".config" / "autotube" / "logs"


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    log_directory: Path | None = None,
    handler: logging.Handler | None = None,
) -> logging.Logger:
    """Configure the root logger and return it.

    When neither ``log_file`` nor ``log_directory`` is supplied, a rotating file
    is created in the default AutoTube log directory so production runs always
    persist logs. A GUI handler (e.g. a Qt-signal handler) may be attached so
    records also appear in the application log tab.
    """
    logger = logging.getLogger("autotube")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    redaction_filter = RedactionFilter()

    # Avoid duplicate handlers when called more than once (tests, GUI).
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console = logging.StreamHandler()
        console.setFormatter(RedactingFormatter(_FORMAT))
        console.addFilter(redaction_filter)
        logger.addHandler(console)

    resolved_log_file = log_file or (
        (log_directory or default_log_directory()) / _DEFAULT_LOG_FILE_NAME
    )
    if not any(
        isinstance(h, RotatingFileHandler)
        and getattr(h, "baseFilename", None) == str(resolved_log_file)
        for h in logger.handlers
    ):
        try:
            resolved_log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                resolved_log_file,
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(RedactingFormatter(_FORMAT))
            file_handler.addFilter(redaction_filter)
            logger.addHandler(file_handler)
        except OSError:
            # Logging must never crash the application; console still works.
            logger.debug("Unable to open log file %s", resolved_log_file, exc_info=True)

    if handler is not None and handler not in logger.handlers:
        handler.setFormatter(RedactingFormatter(_FORMAT))
        handler.addFilter(redaction_filter)
        logger.addHandler(handler)

    return logger


class QtLogHandler(logging.Handler):
    """Emit log records through a callable (typically a PySide6 Signal).

    The signal is wired by the GUI; the handler itself stays Qt-free so logging
    can be tested headlessly.
    """

    def __init__(self, emit: Any, level: int = logging.INFO) -> None:
        super().__init__(level)
        self._emit = emit

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._emit(self.format(record))
        except Exception:  # noqa: BLE001 - never let logging break the app
            pass
