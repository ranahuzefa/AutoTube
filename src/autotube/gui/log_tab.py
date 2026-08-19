"""Log tab: a read-only QPlainTextEdit fed by the logging handler."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


class LogTab(QWidget):
    """Show application log records."""

    log_message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        self.log_message.connect(self._append)

    def _append(self, message: str) -> None:
        self.text.appendPlainText(message)
        scrollbar = self.text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
