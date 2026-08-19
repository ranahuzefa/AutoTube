"""Settings tab: API keys, output dir, render defaults, and providers."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..ai.image.registry import default_ai_image_provider_registry
from ..ai.registry import default_ai_provider_registry
from ..ai.video.registry import default_ai_video_provider_registry
from ..config import Settings, save_settings, validate_settings
from ..exceptions import AutoTubeError
from ..stock.registry import default_stock_provider_registry


class SettingsTab(QWidget):
    """Edit and persist user-level settings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QFormLayout(self)

        self.output_edit = QLineEdit()
        layout.addRow("Output directory:", self._dir_row(self.output_edit, self._pick_output))

        self.pexels_edit = QLineEdit()
        self.pexels_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Pexels API key (stored locally):", self.pexels_edit)

        self.pixabay_edit = QLineEdit()
        self.pixabay_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Pixabay API key (stored locally):", self.pixabay_edit)

        layout.addRow("Stock providers:", self._stock_provider_row())

        self.model_edit = QLineEdit()
        layout.addRow("Whisper model:", self.model_edit)

        self.fps_edit = QLineEdit()
        layout.addRow("FPS:", self.fps_edit)

        self.resolution_edit = QLineEdit()
        layout.addRow("Resolution:", self.resolution_edit)

        self.volume_edit = QLineEdit()
        layout.addRow("Music volume (0.0-1.0):", self.volume_edit)

        self.ai_enabled_checkbox = QCheckBox("Enable AI keyword generation")
        layout.addRow(self.ai_enabled_checkbox)

        self.ai_provider_combo = QComboBox()
        for spec in default_ai_provider_registry().list_all():
            self.ai_provider_combo.addItem(spec.display_name, spec.provider_id)
        self.ai_provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        layout.addRow("AI Provider:", self.ai_provider_combo)

        self.ai_model_edit = QLineEdit()
        layout.addRow("AI Model:", self.ai_model_edit)

        self.ai_base_url_edit = QLineEdit()
        layout.addRow("AI Base URL:", self.ai_base_url_edit)

        self.ai_key_env_edit = QLineEdit()
        self.ai_key_env_edit.textChanged.connect(self._refresh_key_status)
        layout.addRow("AI API key env var:", self.ai_key_env_edit)

        self.ai_key_status_label = QLabel("")
        layout.addRow("Key in environment:", self.ai_key_status_label)

        layout.addRow("AI image generation:", self._generation_row("image"))
        layout.addRow("AI video generation:", self._generation_row("video"))

        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self._save)
        layout.addRow(self.save_button)

    def _stock_provider_row(self) -> QWidget:
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)

        self.stock_provider_list = QListWidget()
        self.stock_provider_list.setMaximumHeight(90)
        for spec in default_stock_provider_registry().list_all():
            item = QListWidgetItem(spec.display_name)
            item.setData(32, spec.provider_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.stock_provider_list.addItem(item)
        outer.addWidget(self.stock_provider_list)

        buttons = QHBoxLayout()
        up_button = QPushButton("Move Up")
        up_button.clicked.connect(self._move_provider_up)
        down_button = QPushButton("Move Down")
        down_button.clicked.connect(self._move_provider_down)
        buttons.addWidget(up_button)
        buttons.addWidget(down_button)
        buttons.addStretch()
        outer.addLayout(buttons)

        self.stock_key_status_label = QLabel("")
        outer.addWidget(self.stock_key_status_label)
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

    def _generation_row(self, kind: str) -> QWidget:
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)

        enabled = QCheckBox("Enable")
        provider_combo = QComboBox()
        model_edit = QLineEdit()
        key_env_edit = QLineEdit()
        base_url_edit = QLineEdit()
        timeout_edit = QLineEdit()
        status_label = QLabel("")

        if kind == "image":
            registry = default_ai_image_provider_registry
        else:
            registry = default_ai_video_provider_registry

        for spec in registry().list_all():
            provider_combo.addItem(spec.display_name, spec.provider_id)
        if provider_combo.count() == 0:
            provider_combo.addItem("(no providers configured)", "")

        def _refresh() -> None:
            env_var = key_env_edit.text().strip()
            status_label.setText(
                "SET" if env_var and os.environ.get(env_var) else "UNSET"
            )

        key_env_edit.textChanged.connect(lambda _=None: _refresh())

        inner = QFormLayout()
        inner.addRow(enabled)
        inner.addRow("Provider:", provider_combo)
        inner.addRow("Model:", model_edit)
        inner.addRow("API key env var:", key_env_edit)
        inner.addRow("Base URL:", base_url_edit)
        inner.addRow("Timeout (s):", timeout_edit)
        inner.addRow("Key in environment:", status_label)
        outer.addLayout(inner)

        attr = f"ai_{kind}"
        setattr(self, f"{attr}_enabled_checkbox", enabled)
        setattr(self, f"{attr}_provider_combo", provider_combo)
        setattr(self, f"{attr}_model_edit", model_edit)
        setattr(self, f"{attr}_key_env_edit", key_env_edit)
        setattr(self, f"{attr}_base_url_edit", base_url_edit)
        setattr(self, f"{attr}_timeout_edit", timeout_edit)
        setattr(self, f"{attr}_key_status_label", status_label)
        return widget

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output directory")
        if path:
            self.output_edit.setText(path)

    def _move_provider_up(self) -> None:
        row = self.stock_provider_list.currentRow()
        if row <= 0:
            return
        item = self.stock_provider_list.takeItem(row)
        self.stock_provider_list.insertItem(row - 1, item)
        self.stock_provider_list.setCurrentItem(item)

    def _move_provider_down(self) -> None:
        row = self.stock_provider_list.currentRow()
        if row < 0 or row >= self.stock_provider_list.count() - 1:
            return
        item = self.stock_provider_list.takeItem(row)
        self.stock_provider_list.insertItem(row + 1, item)
        self.stock_provider_list.setCurrentItem(item)

    def _on_provider_changed(self) -> None:
        provider_id = self.ai_provider_combo.currentData()
        if not provider_id:
            return
        spec = default_ai_provider_registry().get(provider_id)
        self.ai_model_edit.setText(spec.default_model)
        self.ai_base_url_edit.setText(spec.default_base_url)
        self.ai_key_env_edit.setText(spec.default_api_key_env_var)

    def _refresh_key_status(self) -> None:
        env_var = self.ai_key_env_edit.text().strip()
        if not env_var:
            self.ai_key_status_label.setText("")
            return
        status = "SET" if os.environ.get(env_var) else "UNSET"
        self.ai_key_status_label.setText(status)

    def _refresh_stock_key_status(self) -> None:
        parts = []
        for spec in default_stock_provider_registry().list_all():
            status = "SET" if os.environ.get(spec.default_api_key_env_var) else "UNSET"
            parts.append(f"{spec.default_api_key_env_var}: {status}")
        self.stock_key_status_label.setText(" | ".join(parts))

    def _provider_order(self) -> list[str]:
        ids = []
        for index in range(self.stock_provider_list.count()):
            item = self.stock_provider_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(32))
        return ids

    def _set_provider_order(self, provider_ids: list[str]) -> None:
        registry = default_stock_provider_registry()
        known = set(provider_ids)
        ordered = [
            pid for pid in provider_ids if pid in registry.known_ids()
        ]
        extras = [pid for pid in registry.known_ids() if pid not in known]

        # Rebuild the list in the configured order, then unlisted providers.
        self.stock_provider_list.clear()
        for pid in ordered + extras:
            spec = registry.get(pid)
            item = QListWidgetItem(spec.display_name)
            item.setData(32, spec.provider_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if pid in provider_ids
                else Qt.CheckState.Unchecked
            )
            self.stock_provider_list.addItem(item)

    def load_settings(self, settings: Settings) -> None:
        self.output_edit.setText(str(settings.output_dir))
        self.pexels_edit.setText(settings.pexels_api_key)
        self.pixabay_edit.setText(settings.pixabay_api_key)
        self._set_provider_order(settings.stock_providers)
        self._refresh_stock_key_status()
        self.model_edit.setText(settings.whisper_model)
        self.fps_edit.setText(str(settings.fps))
        self.resolution_edit.setText(settings.resolution)
        self.volume_edit.setText(str(settings.music_volume))

        self.ai_enabled_checkbox.setChecked(settings.ai_enabled)
        provider_index = self.ai_provider_combo.findData(settings.ai_provider)
        if provider_index >= 0:
            self.ai_provider_combo.setCurrentIndex(provider_index)
        self.ai_model_edit.setText(settings.ai_model)
        self.ai_base_url_edit.setText(settings.ai_base_url)
        self.ai_key_env_edit.setText(settings.ai_api_key_env_var)
        self._refresh_key_status()

        self._load_generation("image", settings)
        self._load_generation("video", settings)

    def _load_generation(self, kind: str, settings: Settings) -> None:
        prefix = f"ai_{kind}"
        enabled = getattr(self, f"{prefix}_enabled_checkbox")
        combo = getattr(self, f"{prefix}_provider_combo")
        model = getattr(self, f"{prefix}_model_edit")
        key_env = getattr(self, f"{prefix}_key_env_edit")
        base_url = getattr(self, f"{prefix}_base_url_edit")
        timeout = getattr(self, f"{prefix}_timeout_edit")
        status = getattr(self, f"{prefix}_key_status_label")

        enabled.setChecked(getattr(settings, f"{prefix}_enabled"))
        index = combo.findData(getattr(settings, f"{prefix}_provider"))
        if index >= 0:
            combo.setCurrentIndex(index)
        model.setText(getattr(settings, f"{prefix}_model"))
        key_env.setText(getattr(settings, f"{prefix}_api_key_env_var"))
        base_url.setText(getattr(settings, f"{prefix}_base_url"))
        timeout.setText(str(getattr(settings, f"{prefix}_timeout")))
        env_var = key_env.text().strip()
        status.setText("SET" if env_var and os.environ.get(env_var) else "UNSET")

    def _save(self) -> None:
        try:
            settings = Settings(
                output_dir=Path(self.output_edit.text() or "output"),
                pexels_api_key=self.pexels_edit.text(),
                pixabay_api_key=self.pixabay_edit.text(),
                stock_providers=self._provider_order(),
                whisper_model=self.model_edit.text() or "base",
                fps=int(self.fps_edit.text() or "30"),
                resolution=self.resolution_edit.text() or "1920x1080",
                music_volume=float(self.volume_edit.text() or "0.2"),
                ai_enabled=self.ai_enabled_checkbox.isChecked(),
                ai_provider=self.ai_provider_combo.currentData() or "openai_compatible",
                ai_model=self.ai_model_edit.text(),
                ai_api_key_env_var=self.ai_key_env_edit.text().strip(),
                ai_base_url=self.ai_base_url_edit.text().strip(),
                ai_image_enabled=self.ai_image_enabled_checkbox.isChecked(),
                ai_image_provider=self.ai_image_provider_combo.currentData() or "",
                ai_image_model=self.ai_image_model_edit.text().strip(),
                ai_image_api_key_env_var=self.ai_image_key_env_edit.text().strip(),
                ai_image_base_url=self.ai_image_base_url_edit.text().strip(),
                ai_image_timeout=float(self.ai_image_timeout_edit.text() or "60.0"),
                ai_video_enabled=self.ai_video_enabled_checkbox.isChecked(),
                ai_video_provider=self.ai_video_provider_combo.currentData() or "",
                ai_video_model=self.ai_video_model_edit.text().strip(),
                ai_video_api_key_env_var=self.ai_video_key_env_edit.text().strip(),
                ai_video_base_url=self.ai_video_base_url_edit.text().strip(),
                ai_video_timeout=float(self.ai_video_timeout_edit.text() or "120.0"),
            )
            validate_settings(settings)
            save_settings(settings)
        except (ValueError, AutoTubeError) as exc:
            QMessageBox.warning(self, "Invalid settings", str(exc))
            return
        QMessageBox.information(self, "Settings saved", "Settings saved successfully.")
