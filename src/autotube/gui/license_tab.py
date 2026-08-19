"""License activation/status GUI tab."""

from __future__ import annotations

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from ..exceptions import LicenseError
from ..licensing.device import current_device_id_hash
from ..licensing.offline import OfflineLicensingService
from ..licensing.storage import LicenseStore
from ..licensing.types import LicenseState, LicenseStatus
from .. import __version__
from .workers import Worker


class LicenseTab(QWidget):
    """Activate/deactivate a product license and show its status."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = LicenseStore()
        self._state = LicenseState()
        self._thread_pool = QThreadPool.globalInstance()
        self._worker: Worker | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QFormLayout(self)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("ATK-XXXXX-XXXXX-XXXXX-XXXXX-X")
        layout.addRow("Product Key:", self.key_edit)

        self.activate_button = QPushButton("Activate")
        self.activate_button.clicked.connect(self._activate)
        layout.addRow(self.activate_button)

        self.deactivate_button = QPushButton("Deactivate")
        self.deactivate_button.clicked.connect(self._deactivate)
        self.deactivate_button.setEnabled(False)
        layout.addRow(self.deactivate_button)

        self.status_label = QLabel("")
        layout.addRow("Status:", self.status_label)

    def refresh(self) -> None:
        try:
            self._state = self._store.load()
        except Exception:  # noqa: BLE001 - show a safe status
            self._state = LicenseState()
        self.status_label.setText(self._state.status.value)
        self.deactivate_button.setEnabled(
            self._state.status in (LicenseStatus.ACTIVATED, LicenseStatus.OFFLINE_GRACE)
        )

    def _activate(self) -> None:
        if self._worker is not None:
            return
        raw = self.key_edit.text()
        self.key_edit.clear()
        if not raw.strip():
            return

        device_hash = current_device_id_hash()

        def task(progress_cb=None):
            state = OfflineLicensingService().activate(raw, device_hash, __version__)
            LicenseStore().save(state)
            return state

        self.activate_button.setEnabled(False)
        self.status_label.setText("Activating...")

        worker = Worker(task)
        worker.signals.finished.connect(self._on_activated)
        worker.signals.failed.connect(self._on_failed)
        self._worker = worker
        self._thread_pool.start(worker)

    def _deactivate(self) -> None:
        if self._worker is not None:
            return

        def task(progress_cb=None):
            state = OfflineLicensingService().deactivate(self._state, __version__)
            LicenseStore().save(state)
            return state

        self.deactivate_button.setEnabled(False)
        worker = Worker(task)
        worker.signals.finished.connect(self._on_activated)
        worker.signals.failed.connect(self._on_failed)
        self._worker = worker
        self._thread_pool.start(worker)

    def _on_activated(self, result) -> None:
        self._worker = None
        self._state = result
        self.activate_button.setEnabled(True)
        self.refresh()

    def _on_failed(self, message: str) -> None:
        self._worker = None
        self.activate_button.setEnabled(True)
        self.deactivate_button.setEnabled(False)
        self.status_label.setText("Activation failed")
        QMessageBox.warning(self, "License", message)
