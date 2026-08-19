"""Timeline & visual editing tab."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QComboBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import load_settings
from ..licensing.storage import LicenseStore
from ..media.service import FFmpegMediaService
from ..services.orchestrator import PipelineOrchestrator
from ..state import PipelineStage, ProjectState
from ..storage import ProjectStore
from ..stock.cache import AssetCache
from ..stock.download import DownloadManager
from ..stock.manager import StockManager
from ..stock.factory import build_stock_providers
from ..stock.workflow import StockWorkflow
from ..timeline.animations import (
    apply_preset_to_all,
    default_animation_registry,
)
from ..timeline.assets import VisualAssetScanner
from ..timeline.composer import TimelineComposer
from ..timeline.missing import (
    apply_scanned_replacements,
    assign_manual_replacement,
    build_missing_asset_report,
)
from ..timeline.overlap import find_overlaps
from ..timeline.srt import SRTParser
from ..timeline.transitions import default_transition_effect_registry
from ..timeline.types import (
    TimelineState,
    TransitionEffectMode,
    TransitionSettings,
    TransitionSoundMode,
)
from ..transcription.workflow import TranscriptionWorkflow
from .workers import Worker


class TimelineTab(QWidget):
    """Import SRT and local visual assets into a project timeline."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: ProjectState | None = None
        self._project_path: Path | None = None
        self._registry = default_animation_registry()
        self._transition_registry = default_transition_effect_registry()
        self._cancel_event: threading.Event | None = None
        self._thread_pool = QThreadPool.globalInstance()
        self._worker: Worker | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.srt_edit = QLineEdit()
        srt_row = QWidget()
        srt_layout = QHBoxLayout(srt_row)
        srt_layout.setContentsMargins(0, 0, 0, 0)
        srt_layout.addWidget(self.srt_edit)
        srt_button = QPushButton("Browse...")
        srt_button.clicked.connect(self._pick_srt)
        srt_layout.addWidget(srt_button)
        form.addRow("SRT file:", srt_row)

        self.preset_combo = QComboBox()
        for preset in self._registry.list_all():
            self.preset_combo.addItem(preset.name, preset.preset_id)
        form.addRow("Animation:", self.preset_combo)

        self.apply_button = QPushButton("Apply to All")
        self.apply_button.clicked.connect(self._apply_preset)
        form.addRow(self.apply_button)

        self.transition_mode_combo = QComboBox()
        for mode in TransitionEffectMode:
            self.transition_mode_combo.addItem(mode.value.title(), mode)
        self.transition_mode_combo.currentIndexChanged.connect(
            self._on_transition_mode_changed
        )
        form.addRow("Transition effect mode:", self.transition_mode_combo)

        self.manual_effect_combo = QComboBox()
        for preset in self._transition_registry.list_all():
            self.manual_effect_combo.addItem(preset.name, preset.preset_id)
        self.manual_effect_combo.setEnabled(False)
        self.manual_effect_combo.currentIndexChanged.connect(
            self._persist_transition_settings
        )
        form.addRow("Manual effect:", self.manual_effect_combo)

        self.transition_duration_edit = QLineEdit("1.0")
        self.transition_duration_edit.textChanged.connect(
            self._persist_transition_settings
        )
        form.addRow("Transition duration (s):", self.transition_duration_edit)

        self.transition_sound_folder_edit = QLineEdit()
        self.transition_sound_folder_edit.textChanged.connect(
            self._persist_transition_settings
        )
        sfx_folder_row = QWidget()
        sfx_folder_layout = QHBoxLayout(sfx_folder_row)
        sfx_folder_layout.setContentsMargins(0, 0, 0, 0)
        sfx_folder_layout.addWidget(self.transition_sound_folder_edit)
        sfx_folder_button = QPushButton("Choose...")
        sfx_folder_button.clicked.connect(self._pick_transition_sound_folder)
        sfx_folder_layout.addWidget(sfx_folder_button)
        form.addRow("Transition sound folder:", sfx_folder_row)

        self.transition_sound_mode_combo = QComboBox()
        for mode in TransitionSoundMode:
            self.transition_sound_mode_combo.addItem(mode.value.title(), mode)
        self.transition_sound_mode_combo.currentIndexChanged.connect(
            self._persist_transition_settings
        )
        form.addRow("Transition sound mode:", self.transition_sound_mode_combo)

        self.transition_sound_volume_spin = QSpinBox()
        self.transition_sound_volume_spin.setRange(0, 100)
        self.transition_sound_volume_spin.setValue(35)
        self.transition_sound_volume_spin.valueChanged.connect(
            self._persist_transition_settings
        )
        form.addRow("Transition sound volume (%):", self.transition_sound_volume_spin)

        self.folder_edit = QLineEdit()
        folder_row = QWidget()
        folder_layout = QHBoxLayout(folder_row)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.addWidget(self.folder_edit)
        folder_button = QPushButton("Choose...")
        folder_button.clicked.connect(self._pick_folder)
        folder_layout.addWidget(folder_button)
        form.addRow("Visual Assets Folder:", folder_row)

        self.scan_button = QPushButton("Scan Assets")
        self.scan_button.clicked.connect(self._scan_assets)
        form.addRow(self.scan_button)

        replace_row = QWidget()
        replace_layout = QHBoxLayout(replace_row)
        replace_layout.setContentsMargins(0, 0, 0, 0)
        self.replace_button = QPushButton("Replace Selected...")
        self.replace_button.clicked.connect(self._replace_selected)
        replace_layout.addWidget(self.replace_button)
        self.report_button = QPushButton("Report Missing Assets")
        self.report_button.clicked.connect(self._report_missing)
        replace_layout.addWidget(self.report_button)
        form.addRow(replace_row)

        self.allow_missing_checkbox = QCheckBox("Allow missing visual slots (render black)")
        form.addRow(self.allow_missing_checkbox)

        render_row = QWidget()
        render_layout = QHBoxLayout(render_row)
        render_layout.setContentsMargins(0, 0, 0, 0)
        self.render_button = QPushButton("Render Timeline")
        self.render_button.clicked.connect(self._render)
        render_layout.addWidget(self.render_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel)
        self.cancel_button.setEnabled(False)
        render_layout.addWidget(self.cancel_button)
        form.addRow(render_row)

        layout.addLayout(form)

        layout.addWidget(QLabel("Timeline / Scene List"))
        self.timeline_list = QListWidget()
        layout.addWidget(self.timeline_list)

        self.warnings_label = QLabel("")
        self.warnings_label.setWordWrap(True)
        layout.addWidget(self.warnings_label)

    def set_state(self, state: ProjectState | None) -> None:
        self._state = state
        if state is not None and state.timeline is None:
            state.timeline = TimelineState()
        self.refresh()

    def set_project_path(self, path: Path | None) -> None:
        self._project_path = path

    def refresh(self) -> None:
        self.timeline_list.clear()
        if self._state is None or self._state.timeline is None:
            return

        timeline = self._state.timeline
        for sub in timeline.subtitles:
            self.timeline_list.addItem(
                f"[{sub.start:.2f} -> {sub.end:.2f}] {sub.text} "
                f"({sub.animation_preset or 'none'})"
            )
        for asset in timeline.visual_assets:
            source = asset.source_path.name if asset.source_path else "(missing)"
            self.timeline_list.addItem(
                f"[{asset.start:.2f} -> {asset.end:.2f}] {source} "
                f"({asset.asset_type.value}, {asset.status.value})"
            )
        self._load_transition_controls()

    def _load_transition_controls(self) -> None:
        if self._state is None or self._state.timeline is None:
            return
        settings = self._state.timeline.transition_settings
        index = self.transition_mode_combo.findData(settings.effect_mode)
        if index >= 0:
            self.transition_mode_combo.setCurrentIndex(index)
        index = self.manual_effect_combo.findData(settings.effect)
        if index >= 0:
            self.manual_effect_combo.setCurrentIndex(index)
        self.transition_duration_edit.setText(str(settings.duration))
        self.transition_sound_folder_edit.setText(
            str(settings.sound_folder) if settings.sound_folder else ""
        )
        index = self.transition_sound_mode_combo.findData(settings.sound_mode)
        if index >= 0:
            self.transition_sound_mode_combo.setCurrentIndex(index)
        self.transition_sound_volume_spin.setValue(int(round(settings.sound_volume * 100)))
        self._on_transition_mode_changed()

    def _on_transition_mode_changed(self) -> None:
        self.manual_effect_combo.setEnabled(
            self.transition_mode_combo.currentData() == TransitionEffectMode.MANUAL
        )
        self._persist_transition_settings()

    def _pick_transition_sound_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Transition Sound Folder")
        if path:
            self.transition_sound_folder_edit.setText(path)
            self._persist_transition_settings()

    def _persist_transition_settings(self) -> None:
        if self._state is None or self._state.timeline is None:
            return
        settings = self._state.timeline.transition_settings
        settings.effect_mode = self.transition_mode_combo.currentData() or TransitionEffectMode.NONE
        settings.effect = self.manual_effect_combo.currentData()
        try:
            settings.duration = float(self.transition_duration_edit.text() or "1.0")
        except ValueError:
            settings.duration = 1.0
        folder = self.transition_sound_folder_edit.text().strip()
        settings.sound_folder = Path(folder) if folder else None
        settings.sound_mode = self.transition_sound_mode_combo.currentData() or TransitionSoundMode.NONE
        settings.sound_volume = self.transition_sound_volume_spin.value() / 100.0

    def _pick_srt(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select SRT", "", "SRT files (*.srt)")
        if path:
            self.srt_edit.setText(path)
            self._load_srt(Path(path))

    def _load_srt(self, path: Path) -> None:
        if self._state is None:
            return
        try:
            subtitles = SRTParser().parse_file(path)
        except Exception as exc:  # noqa: BLE001 - show parse errors
            QMessageBox.warning(self, "SRT import failed", str(exc))
            return
        timeline = self._state.timeline or TimelineState()
        timeline.subtitles = subtitles
        self._state.timeline = timeline
        self.refresh()

    def _apply_preset(self) -> None:
        if self._state is None or self._state.timeline is None:
            return
        preset_id = self.preset_combo.currentData()
        apply_preset_to_all(self._state.timeline.subtitles, preset_id, self._registry)
        self._state.timeline.animation_preset = preset_id
        self.refresh()

    def _pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Visual Assets Folder")
        if path:
            self.folder_edit.setText(path)

    def _scan_assets(self) -> None:
        if self._state is None:
            return
        folder = self.folder_edit.text().strip()
        if not folder:
            return
        assets, warnings = VisualAssetScanner().scan(Path(folder))
        timeline = self._state.timeline or TimelineState()

        if timeline.visual_assets:
            remaining = apply_scanned_replacements(timeline, assets)
            if remaining:
                warnings.append(
                    f"{len(remaining)} missing slot(s) could not be matched to scanned assets."
                )
        else:
            timeline.visual_assets = assets

        self._state.timeline = timeline

        overlaps = find_overlaps(timeline.visual_assets)
        messages = list(warnings)
        if overlaps:
            messages.append(
                f"Overlapping visual assets detected: "
                f"{', '.join(f'{o.first.source_path.name} & {o.second.source_path.name}' for o in overlaps if o.first.source_path and o.second.source_path)}"
            )
        self.warnings_label.setText("\n".join(messages))
        self.refresh()

    def _replace_selected(self) -> None:
        if self._state is None or self._state.timeline is None:
            return
        item = self.timeline_list.currentItem()
        if item is None:
            return

        row = self.timeline_list.row(item)
        subtitle_count = len(self._state.timeline.subtitles)
        if row < subtitle_count:
            return

        asset_index = row - subtitle_count
        if asset_index >= len(self._state.timeline.visual_assets):
            return
        slot = self._state.timeline.visual_assets[asset_index]

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select replacement visual asset",
            "",
            "Media files (*.png *.jpg *.jpeg *.webp *.mp4 *.mov)",
        )
        if not path:
            return

        assign_manual_replacement(self._state.timeline, slot, Path(path))
        self.refresh()
        self.warnings_label.setText(
            f"Assigned replacement to {slot.start:.2f} -> {slot.end:.2f}"
        )

    def _report_missing(self) -> None:
        if self._state is None or self._state.timeline is None:
            return
        self.warnings_label.setText(build_missing_asset_report(self._state.timeline))

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
            timeline_composer=TimelineComposer(
                media, self._registry, self._transition_registry
            ),
        )

    def _render(self) -> None:
        if self._state is None or self._worker is not None:
            return

        try:
            from ..licensing.runtime import ensure_usable_and_fresh

            ensure_usable_and_fresh(LicenseStore().load())
        except Exception as exc:  # noqa: BLE001 - surface license block
            self.warnings_label.setText(str(exc))
            return

        self._cancel_event = threading.Event()
        try:
            orchestrator = self._build_orchestrator()
        except Exception as exc:  # noqa: BLE001 - surface construction errors
            self.warnings_label.setText(f"Cannot start render: {exc}")
            return
        state = self._state
        allow_missing = self.allow_missing_checkbox.isChecked()

        def task(progress_cb=None):
            return orchestrator.run(
                state,
                allow_missing=allow_missing,
                cancel_event=self._cancel_event,
                progress=progress_cb,
            )

        self.render_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.warnings_label.setText("Rendering timeline...")

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
        self.warnings_label.setText("Cancelling...")

    def _on_finished(self, result) -> None:
        self._worker = None
        self.render_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if self._state is not None:
            artifacts = self._state.stage(PipelineStage.COMPLETED).artifacts
            final = artifacts[-1] if artifacts else result
        else:
            final = result
        self.warnings_label.setText(f"Rendered: {final}")
        self.refresh()

    def _on_failed(self, message: str) -> None:
        self._worker = None
        self.render_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.warnings_label.setText(f"Render failed: {message}")
        self.refresh()

    def _on_cancelled(self, message: str) -> None:
        self._worker = None
        self.render_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.warnings_label.setText(f"Render cancelled: {message}")
        self.refresh()

    def _on_progress(self, value: int) -> None:
        self.warnings_label.setText(f"Rendering: {value}%")

    @property
    def is_busy(self) -> bool:
        return self._worker is not None
