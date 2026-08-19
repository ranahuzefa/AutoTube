"""Threading helpers for blocking stages.

Workers run on a QThreadPool and emit safe messages to the GUI while logging the
full traceback for diagnostics.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ..exceptions import is_cancellation

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal(str)
    progress = Signal(int)


class Worker(QRunnable):
    """Run a callable on a thread pool and emit results via signals."""

    def __init__(self, fn, *args, progress_cb=None, **kwargs) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.progress_cb = progress_cb
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if self.progress_cb is not None:
                result = self.fn(
                    *self.args,
                    progress_cb=lambda value: self.signals.progress.emit(int(value)),
                    **self.kwargs,
                )
            else:
                result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001 - worker boundary
            logger.exception("Worker task failed: %s", exc)
            if is_cancellation(exc):
                self.signals.cancelled.emit(str(exc))
            else:
                self.signals.failed.emit(str(exc))
        else:
            self.signals.finished.emit(result)
