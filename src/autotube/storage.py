"""Atomic JSON persistence for projects and settings."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Settings
from .exceptions import CorruptProjectError, StorageError
from .state import ProjectState


class AtomicFileWriter:
    """Write bytes to a file atomically via a temp file + os.replace."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write_text(self, text: str, encoding: str = "utf-8") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent),
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding=encoding) as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


class ProjectStore:
    """Persist ProjectState to/from project.json."""

    def __init__(self, version: int = 1) -> None:
        self.version = version

    def save(self, state: ProjectState, path: Path) -> None:
        state.touch()
        payload = state.to_dict()
        payload["version"] = self.version
        try:
            text = json.dumps(payload, indent=2, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise StorageError(f"Cannot serialize project: {exc}") from exc
        try:
            AtomicFileWriter(path).write_text(text + "\n")
        except OSError as exc:
            raise StorageError(f"Cannot write project file {path}: {exc}") from exc

    def load(self, path: Path) -> ProjectState:
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except FileNotFoundError as exc:
            raise StorageError(f"Project file not found: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise CorruptProjectError(f"Cannot parse project file {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise CorruptProjectError(f"Project file {path} must contain a JSON object.")
        return ProjectState.from_dict(data)


@dataclass
class SettingsStore:
    """Persist app settings to the platform user-config directory."""

    file_name: str = "settings.json"
    directory: Path | None = None

    def __post_init__(self) -> None:
        if self.directory is None:
            self.directory = self._default_directory()

    @staticmethod
    def _default_directory() -> Path:
        if os.name == "nt":
            base = os.environ.get("APPDATA") or str(Path.home())
            return Path(base) / "AutoTube"
        return Path.home() / ".config" / "autotube"

    @property
    def path(self) -> Path:
        assert self.directory is not None
        return self.directory / self.file_name

    def save(self, settings: Settings) -> None:
        try:
            text = json.dumps(settings.to_dict(), indent=2, ensure_ascii=False)
            AtomicFileWriter(self.path).write_text(text + "\n")
        except OSError as exc:
            raise StorageError(f"Cannot write settings file {self.path}: {exc}") from exc

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Cannot parse settings file {self.path}: {exc}") from exc
        if not isinstance(data, dict):
            raise StorageError(f"Settings file {self.path} must contain a JSON object.")
        return Settings.from_dict(data)
