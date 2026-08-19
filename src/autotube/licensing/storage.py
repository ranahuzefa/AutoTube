"""Separate license-state persistence.

Uses the existing atomic-write pattern and stores beside ``settings.json`` in
the user config directory, never inside a project file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..exceptions import StorageError
from ..storage import AtomicFileWriter
from .types import LicenseState


class LicenseStore:
    """Persist non-secret license activation state."""

    file_name = "license.json"

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or self._default_directory()

    @staticmethod
    def _default_directory() -> Path:
        if os.name == "nt":
            base = os.environ.get("APPDATA") or str(Path.home())
            return Path(base) / "AutoTube"
        return Path.home() / ".config" / "autotube"

    @property
    def path(self) -> Path:
        return self.directory / self.file_name

    def load(self) -> LicenseState:
        if not self.path.exists():
            return LicenseState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Cannot parse license file {self.path}: {exc}") from exc
        if not isinstance(data, dict):
            raise StorageError(f"License file {self.path} must contain a JSON object.")
        return LicenseState.from_dict(data)

    def save(self, state: LicenseState) -> None:
        try:
            text = json.dumps(state.to_dict(), indent=2, ensure_ascii=False)
            AtomicFileWriter(self.path).write_text(text + "\n")
        except OSError as exc:
            raise StorageError(f"Cannot write license file {self.path}: {exc}") from exc
        if os.name != "nt":
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
