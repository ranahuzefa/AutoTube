"""PySide6 application bootstrap."""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from ..logging_setup import QtLogHandler, setup_logging
from ..media.detection import require_media_tooling
from .main_window import MainWindow


def _install_excepthook(logger: logging.Logger) -> None:
    """Route unhandled GUI exceptions to the log and a safe error dialog."""

    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        text = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
        logger.critical("Unhandled GUI exception:\n%s", text)
        QMessageBox.critical(
            None,
            "Unexpected error",
            "AutoTube encountered an unexpected error. "
            "See the log for details.",
        )

    sys.excepthook = handle_exception


def run_app(log_file: Path | None = None) -> int:
    """Create the QApplication, main window, and start the event loop."""
    app = QApplication(sys.argv)
    app.setApplicationName("AutoTube Creator")

    logger = setup_logging(log_file=log_file)
    _install_excepthook(logger)

    try:
        require_media_tooling()
    except RuntimeError as exc:
        QMessageBox.critical(None, "FFmpeg required", str(exc))
        return 1

    window = MainWindow()
    window.setup_logging(log_file)
    window.show()

    return app.exec()
