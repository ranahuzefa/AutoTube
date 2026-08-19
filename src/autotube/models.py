"""Domain models implemented as plain dataclasses with explicit serialization."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import (
    DEFAULT_CAPTION_STYLE,
    DEFAULT_FPS,
    DEFAULT_MUSIC_VOLUME,
    DEFAULT_RESOLUTION,
    DEFAULT_WHISPER_MODEL,
)
from .exceptions import ValidationError


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _path_to_str(value: Path | None) -> str | None:
    return None if value is None else str(value)


def _str_to_path(value: str | None) -> Path | None:
    return None if value is None else Path(value)


@dataclass
class Project:
    """Top-level project inputs (no pipeline state)."""

    name: str
    script_path: Path | None = None
    voiceover_path: Path | None = None
    music_path: Path | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "script_path": _path_to_str(self.script_path),
            "voiceover_path": _path_to_str(self.voiceover_path),
            "music_path": _path_to_str(self.music_path),
            "created_at": _isoformat(self.created_at),
            "updated_at": _isoformat(self.updated_at),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        return cls(
            name=str(data["name"]),
            script_path=_str_to_path(data.get("script_path")),
            voiceover_path=_str_to_path(data.get("voiceover_path")),
            music_path=_str_to_path(data.get("music_path")),
            created_at=_parse_datetime(data.get("created_at")) or utc_now(),
            updated_at=_parse_datetime(data.get("updated_at")) or utc_now(),
        )


@dataclass
class Script:
    """Script content loaded from disk."""

    text: str
    source_path: Path | None = None
    encoding: str = "utf-8"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source_path": _path_to_str(self.source_path),
            "encoding": self.encoding,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Script":
        return cls(
            text=str(data.get("text", "")),
            source_path=_str_to_path(data.get("source_path")),
            encoding=str(data.get("encoding", "utf-8")),
        )

    @classmethod
    def from_file(cls, path: Path) -> "Script":
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise ValidationError(f"Cannot read script file {path}: {exc}") from exc
        return cls(text=text, source_path=path, encoding="utf-8")


@dataclass
class Voiceover:
    """Voiceover reference. Duration is probed in Phase 2."""

    path: Path
    duration: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": _path_to_str(self.path),
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Voiceover":
        return cls(
            path=Path(str(data["path"])),
            duration=data.get("duration"),
        )


@dataclass
class RenderSettings:
    """Output and render configuration carried with a project."""

    output_dir: Path = field(default_factory=lambda: Path("output"))
    resolution: str = DEFAULT_RESOLUTION
    fps: int = DEFAULT_FPS
    music_volume: float = DEFAULT_MUSIC_VOLUME
    whisper_model: str = DEFAULT_WHISPER_MODEL
    caption_style: str = DEFAULT_CAPTION_STYLE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {
            "output_dir": _path_to_str(self.output_dir),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RenderSettings":
        return cls(
            output_dir=Path(str(data.get("output_dir", "output"))),
            resolution=str(data.get("resolution", "1920x1080")),
            fps=int(data.get("fps", 30)),
            music_volume=float(data.get("music_volume", 0.2)),
            whisper_model=str(data.get("whisper_model", "base")),
            caption_style=str(data.get("caption_style", "burned")),
        )


def validate_project(project: Project) -> None:
    """Validate a project's required inputs."""
    if not project.name.strip():
        raise ValidationError("Project name is required.")
    if project.script_path is None:
        raise ValidationError("Script path is required.")
    if project.voiceover_path is None:
        raise ValidationError("Voiceover path is required.")
    if not project.script_path.exists():
        raise ValidationError(f"Script file does not exist: {project.script_path}")
    if not project.voiceover_path.exists():
        raise ValidationError(f"Voiceover file does not exist: {project.voiceover_path}")
    if project.music_path is not None and not project.music_path.exists():
        raise ValidationError(f"Music file does not exist: {project.music_path}")


def validate_render_settings(settings: RenderSettings) -> None:
    """Validate render settings."""
    try:
        width, height = settings.resolution.lower().split("x")
        int(width)
        int(height)
    except ValueError as exc:
        raise ValidationError(
            f"Invalid resolution {settings.resolution!r}; expected WIDTHxHEIGHT."
        ) from exc
    if settings.fps <= 0:
        raise ValidationError("FPS must be positive.")
    if not 0.0 <= settings.music_volume <= 1.0:
        raise ValidationError("Music volume must be between 0.0 and 1.0.")
