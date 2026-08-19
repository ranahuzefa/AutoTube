"""Main window with Project, Workflow, Settings, and Log tabs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from ..config import load_settings
from ..logging_setup import QtLogHandler, setup_logging
from ..services import Pipeline
from .license_tab import LicenseTab
from .log_tab import LogTab
from .project_tab import ProjectTab
from .settings_tab import SettingsTab
from .timeline_tab import TimelineTab
from .workflow_tab import WorkflowTab


class MainWindow(QMainWindow):
    """Application shell."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AutoTube Creator")
        self.resize(900, 600)

        self.tabs = QTabWidget()
        self.project_tab = ProjectTab()
        self.workflow_tab = WorkflowTab()
        self.settings_tab = SettingsTab()
        self.timeline_tab = TimelineTab()
        self.license_tab = LicenseTab()
        self.log_tab = LogTab()

        self.tabs.addTab(self.project_tab, "Project")
        self.tabs.addTab(self.workflow_tab, "Workflow")
        self.tabs.addTab(self.timeline_tab, "Timeline")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.license_tab, "License")
        self.tabs.addTab(self.log_tab, "Log")
        self.setCentralWidget(self.tabs)

        self.project_tab.project_created.connect(self.workflow_tab.set_state)
        self.project_tab.project_loaded.connect(self.workflow_tab.set_state)
        self.project_tab.project_created.connect(self.timeline_tab.set_state)
        self.project_tab.project_loaded.connect(self.timeline_tab.set_state)
        self.project_tab.project_path_changed.connect(self._on_project_path_changed)

        self._build_menu()
        self.settings_tab.load_settings(load_settings())

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        new_action = file_menu.addAction("&New Project")
        new_action.triggered.connect(self._new_project)

        open_action = file_menu.addAction("&Open Project...")
        open_action.triggered.connect(self._open_project)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

    def setup_logging(self, log_file: Path | None = None) -> None:
        handler = QtLogHandler(self.log_tab.log_message.emit)
        setup_logging(log_file=log_file, handler=handler)

    def _on_project_path_changed(self, path: str) -> None:
        self.workflow_tab.set_project_path(Path(path))
        self.timeline_tab.set_project_path(Path(path))

    def _new_project(self) -> None:
        if self._is_busy():
            QMessageBox.warning(
                self, "Action in progress", "Wait for the current action to finish."
            )
            return
        self.project_tab.clear()
        self.workflow_tab.set_state(None)
        self.timeline_tab.set_state(None)
        self.tabs.setCurrentIndex(0)

    def _open_project(self) -> None:
        if self._is_busy():
            QMessageBox.warning(
                self, "Action in progress", "Wait for the current action to finish."
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open project", "", "JSON files (*.json)"
        )
        if not path:
            return
        try:
            self.project_tab.load_project(Path(path))
            self.workflow_tab.set_state(self.project_tab.project_state)
            self.timeline_tab.set_state(self.project_tab.project_state)
            self.workflow_tab.set_project_path(Path(path))
            self.timeline_tab.set_project_path(Path(path))
        except Exception as exc:  # noqa: BLE001 - surface any load error
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self.tabs.setCurrentIndex(1)

    def _is_busy(self) -> bool:
        return self.workflow_tab.is_busy or self.timeline_tab.is_busy
