"""Project tab: input file pickers and project create/save/resume."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from ..exceptions import ValidationError
from ..models import Project
from ..state import ProjectState
from ..storage import ProjectStore


class ProjectTab(QWidget):
    """Collect project inputs and persist a new ProjectState."""

    project_created = Signal(object)
    project_loaded = Signal(object)
    project_path_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_state: ProjectState | None = None
        self._build()

    def _build(self) -> None:
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("My Video")
        layout.addRow("Project name:", self.name_edit)

        self.script_edit = QLineEdit()
        layout.addRow("Script:", self._file_row(self.script_edit, self._pick_script))

        self.voiceover_edit = QLineEdit()
        layout.addRow("Voiceover:", self._file_row(self.voiceover_edit, self._pick_voiceover))

        self.music_edit = QLineEdit()
        layout.addRow("Background music:", self._file_row(self.music_edit, self._pick_music))

        self.output_edit = QLineEdit()
        self.output_edit.setText(str(Path("output")))
        layout.addRow("Output dir:", self._dir_row(self.output_edit, self._pick_output))

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Create Project")
        self.save_button.clicked.connect(self._create_project)
        self.save_button.setEnabled(False)
        buttons.addWidget(self.save_button)
        layout.addRow(buttons)

        self.name_edit.textChanged.connect(self._validate)
        self.script_edit.textChanged.connect(self._validate)
        self.voiceover_edit.textChanged.connect(self._validate)

    def _file_row(self, edit: QLineEdit, handler) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit)
        button = QPushButton("Browse...")
        button.clicked.connect(handler)
        row.addWidget(button)
        return widget

    def _dir_row(self, edit: QLineEdit, handler) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit)
        button = QPushButton("Choose...")
        button.clicked.connect(handler)
        row.addWidget(button)
        return widget

    def _pick_script(self) -> None:
        self._pick_file(self.script_edit, "Select script", "Text files (*.txt *.md)")

    def _pick_voiceover(self) -> None:
        self._pick_file(self.voiceover_edit, "Select voiceover", "Audio files (*.mp3 *.wav)")

    def _pick_music(self) -> None:
        self._pick_file(self.music_edit, "Select background music", "Audio files (*.mp3 *.wav)")

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output directory")
        if path:
            self.output_edit.setText(path)

    def _pick_file(self, edit: QLineEdit, title: str, filter_: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, title, "", filter_)
        if path:
            edit.setText(path)

    def _validate(self) -> None:
        self.save_button.setEnabled(
            bool(self.name_edit.text().strip())
            and bool(self.script_edit.text().strip())
            and bool(self.voiceover_edit.text().strip())
        )

    def clear(self) -> None:
        self.name_edit.clear()
        self.script_edit.clear()
        self.voiceover_edit.clear()
        self.music_edit.clear()
        self.output_edit.setText(str(Path("output")))
        self.project_state = None
        self._validate()

    def _create_project(self) -> None:
        project = Project(
            name=self.name_edit.text().strip(),
            script_path=Path(self.script_edit.text()) if self.script_edit.text() else None,
            voiceover_path=Path(self.voiceover_edit.text()) if self.voiceover_edit.text() else None,
            music_path=Path(self.music_edit.text()) if self.music_edit.text() else None,
        )
        from ..models import RenderSettings

        render = RenderSettings(output_dir=Path(self.output_edit.text() or "output"))

        try:
            from ..models import validate_project

            validate_project(project)
        except ValidationError as exc:
            QMessageBox.warning(self, "Invalid project", str(exc))
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save project", "project.json", "JSON files (*.json)"
        )
        if not path:
            return

        self.project_state = ProjectState(project=project, render_settings=render)
        try:
            ProjectStore().save(self.project_state, Path(path))
        except Exception as exc:  # noqa: BLE001 - surface any save failure
            self.project_state = None
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.project_created.emit(self.project_state)
        self.project_path_changed.emit(str(path))
        QMessageBox.information(self, "Project created", f"Saved to {path}")

    def load_project(self, path: Path) -> None:
        self.project_state = ProjectStore().load(path)
        project = self.project_state.project
        if project is not None:
            self.name_edit.setText(project.name)
            self.script_edit.setText(str(project.script_path or ""))
            self.voiceover_edit.setText(str(project.voiceover_path or ""))
            self.music_edit.setText(str(project.music_path or ""))
        self.output_edit.setText(str(self.project_state.render_settings.output_dir))
        self.project_loaded.emit(self.project_state)
        self.project_path_changed.emit(str(path))
