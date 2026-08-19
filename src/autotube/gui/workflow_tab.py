"""Workflow tab: ordered stage list, run/resume, and cancellation."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import load_settings
from ..licensing.storage import LicenseStore
from ..media.service import FFmpegMediaService
from ..services.orchestrator import PipelineOrchestrator
from ..state import PipelineStage, ProjectState, StageStatus, STAGE_ORDER
from ..storage import ProjectStore
from ..stock.cache import AssetCache
from ..stock.download import DownloadManager
from ..stock.manager import StockManager
from ..stock.factory import build_stock_providers
from ..stock.workflow import StockWorkflow
from ..timeline.composer import TimelineComposer
from ..transcription.workflow import TranscriptionWorkflow
from .workers import Worker


class WorkflowTab(QWidget):
    """Display the 9-stage pipeline and run it on a worker thread."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: ProjectState | None = None
        self._project_path: Path | None = None
        self._cancel_event: threading.Event | None = None
        self._thread_pool = QThreadPool.globalInstance()
        self._worker: Worker | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Pipeline stages"))

        self.stage_list = QListWidget()
        for stage in STAGE_ORDER:
            item = QListWidgetItem(stage.value)
            item.setData(Qt.ItemDataRole.UserRole, stage)
            self.stage_list.addItem(item)
        layout.addWidget(self.stage_list)

        controls = QHBoxLayout()
        self.force_checkbox = QCheckBox("Force re-run completed stages")
        controls.addWidget(self.force_checkbox)

        self.run_button = QPushButton("Run / Resume")
        self.run_button.clicked.connect(self._run)
        controls.addWidget(self.run_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel)
        self.cancel_button.setEnabled(False)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)

        self.status_label = QLabel("No project loaded.")
        layout.addWidget(self.status_label)

    def set_state(self, state: ProjectState | None) -> None:
        self._state = state
        self.refresh()

    def set_project_path(self, path: Path | None) -> None:
        self._project_path = path

    def refresh(self) -> None:
        for row in range(self.stage_list.count()):
            item = self.stage_list.item(row)
            stage = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(stage, str):
                stage = PipelineStage(stage)
            if self._state is None:
                item.setText(stage.value)
                continue
            stage_state = self._state.stage(stage)
            item.setText(f"{stage.value} — {stage_state.status.value}")

        if self._state is None:
            self.status_label.setText("No project loaded.")
            self.run_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
            return

        self.run_button.setEnabled(self._worker is None)
        next_stage = self._state.next_pending_stage(force=self.force_checkbox.isChecked())
        if next_stage is None:
            self.status_label.setText("Pipeline complete.")
        else:
            self.status_label.setText(f"Next stage: {next_stage.value}")

    def _build_orchestrator(self) -> PipelineOrchestrator:
        settings = load_settings()
        media = FFmpegMediaService()

        providers = build_stock_providers(settings)

        cache = AssetCache(Path("stock_cache"))
        stock_manager = StockManager(
            providers=providers,
            downloader=DownloadManager(cache),
            cache=cache,
            media_service=media,
        )

        project_path = self._project_path or Path(f"{self._state.project_id}.json")

        return PipelineOrchestrator(
            transcription_workflow=TranscriptionWorkflow(project_path=None),
            stock_workflow=StockWorkflow(
                stock_manager=stock_manager, project_path=None
            ),
            media_service=media,
            store=ProjectStore(),
            project_path=project_path,
            timeline_composer=TimelineComposer(media),
        )

    def _run(self) -> None:
        if self._state is None or self._worker is not None:
            return

        try:
            from ..licensing.runtime import ensure_usable_and_fresh

            ensure_usable_and_fresh(LicenseStore().load())
        except Exception as exc:  # noqa: BLE001 - surface license block
            self.status_label.setText(str(exc))
            return

        self._cancel_event = threading.Event()
        try:
            orchestrator = self._build_orchestrator()
        except Exception as exc:  # noqa: BLE001 - surface construction errors
            self.status_label.setText(f"Cannot start: {exc}")
            return
        state = self._state
        force = self.force_checkbox.isChecked()

        def task(progress_cb=None):
            return orchestrator.run(
                state,
                force=force,
                allow_missing=False,
                cancel_event=self._cancel_event,
                progress=progress_cb,
            )

        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_label.setText("Running pipeline...")

        worker = Worker(task, progress_cb=True)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        worker.signals.cancelled.connect(self._on_cancelled)
        worker.signals.progress.connect(self._on_progress)
        self._worker = worker
        self._thread_pool.start(worker)

    def _cancel(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
        self.status_label.setText("Cancelling...")

    def _on_finished(self, result) -> None:
        self._worker = None
        self.cancel_button.setEnabled(False)
        self.refresh()

    def _on_failed(self, message: str) -> None:
        self._worker = None
        self.cancel_button.setEnabled(False)
        self.refresh()
        self.status_label.setText(f"Failed: {message}")

    def _on_cancelled(self, message: str) -> None:
        self._worker = None
        self.cancel_button.setEnabled(False)
        self.refresh()
        self.status_label.setText(f"Cancelled: {message}")

    def _on_progress(self, value: int) -> None:
        self.status_label.setText(f"Progress: {value}%")

    @property
    def is_busy(self) -> bool:
        return self._worker is not None
