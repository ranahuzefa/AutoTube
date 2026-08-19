"""Timeline data types with explicit serialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from ..constants import DEFAULT_TRANSITION_DURATION, DEFAULT_TRANSITION_SOUND_VOLUME


class AssetType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class TransitionEffectMode(str, Enum):
    NONE = "none"
    MANUAL = "manual"
    RANDOM = "random"


class TransitionSoundMode(str, Enum):
    NONE = "none"
    RANDOM = "random"
    SEQUENTIAL = "sequential"


class TimelineItemStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    ERROR = "error"
    MISSING = "missing"
    MANUAL_REPLACEMENT_REQUIRED = "manual_replacement_required"


class ReplacementStatus(str, Enum):
    NONE = "none"
    REQUIRED = "required"
    RESOLVED = "resolved"


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


@dataclass
class SubtitleEntry:
    index: int
    start: float
    end: float
    text: str
    animation_preset: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "animation_preset": self.animation_preset,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubtitleEntry":
        return cls(
            index=int(data["index"]),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            text=str(data.get("text", "")),
            animation_preset=data.get("animation_preset"),
        )


@dataclass
class TimedVisualAsset:
    source_path: Path | None = None
    start: float = 0.0
    end: float = 0.0
    asset_type: AssetType = AssetType.IMAGE
    status: TimelineItemStatus = TimelineItemStatus.PENDING
    processed_path: Path | None = None
    error: str | None = None
    source: str = "manual"
    description: str | None = None
    replacement_status: ReplacementStatus = ReplacementStatus.NONE

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": str(self.source_path) if self.source_path else None,
            "start": self.start,
            "end": self.end,
            "asset_type": self.asset_type.value,
            "status": self.status.value,
            "processed_path": str(self.processed_path) if self.processed_path else None,
            "error": self.error,
            "source": self.source,
            "description": self.description,
            "replacement_status": self.replacement_status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimedVisualAsset":
        return cls(
            source_path=Path(str(data["source_path"])) if data.get("source_path") else None,
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            asset_type=AssetType(data.get("asset_type", "image")),
            status=TimelineItemStatus(data.get("status", "pending")),
            processed_path=(
                Path(str(data["processed_path"])) if data.get("processed_path") else None
            ),
            error=data.get("error"),
            source=str(data.get("source", "manual")),
            description=data.get("description"),
            replacement_status=ReplacementStatus(data.get("replacement_status", "none")),
        )


@dataclass
class TransitionSettings:
    effect_mode: TransitionEffectMode = TransitionEffectMode.NONE
    effect: str | None = None
    duration: float = DEFAULT_TRANSITION_DURATION
    sound_folder: Path | None = None
    sound_mode: TransitionSoundMode = TransitionSoundMode.NONE
    sound_volume: float = DEFAULT_TRANSITION_SOUND_VOLUME

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect_mode": self.effect_mode.value,
            "effect": self.effect,
            "duration": self.duration,
            "sound_folder": str(self.sound_folder) if self.sound_folder else None,
            "sound_mode": self.sound_mode.value,
            "sound_volume": self.sound_volume,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransitionSettings":
        return cls(
            effect_mode=TransitionEffectMode(
                data.get("effect_mode", TransitionEffectMode.NONE.value)
            ),
            effect=data.get("effect"),
            duration=float(data.get("duration", DEFAULT_TRANSITION_DURATION)),
            sound_folder=(
                Path(str(data["sound_folder"])) if data.get("sound_folder") else None
            ),
            sound_mode=TransitionSoundMode(
                data.get("sound_mode", TransitionSoundMode.NONE.value)
            ),
            sound_volume=float(
                data.get("sound_volume", DEFAULT_TRANSITION_SOUND_VOLUME)
            ),
        )


@dataclass
class TimelineState:
    subtitles: list[SubtitleEntry] = field(default_factory=list)
    visual_assets: list[TimedVisualAsset] = field(default_factory=list)
    animation_preset: str | None = None
    rendered_path: str | None = None
    rendered_fingerprint: str | None = None
    rendered_at: datetime | None = None
    transition_settings: TransitionSettings = field(default_factory=TransitionSettings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subtitles": [s.to_dict() for s in self.subtitles],
            "visual_assets": [a.to_dict() for a in self.visual_assets],
            "animation_preset": self.animation_preset,
            "rendered_path": self.rendered_path,
            "rendered_fingerprint": self.rendered_fingerprint,
            "rendered_at": _isoformat(self.rendered_at),
            "transition_settings": self.transition_settings.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineState":
        return cls(
            subtitles=[SubtitleEntry.from_dict(s) for s in data.get("subtitles", [])],
            visual_assets=[
                TimedVisualAsset.from_dict(a) for a in data.get("visual_assets", [])
            ],
            animation_preset=data.get("animation_preset"),
            rendered_path=data.get("rendered_path"),
            rendered_fingerprint=data.get("rendered_fingerprint"),
            rendered_at=_parse_datetime(data.get("rendered_at")),
            transition_settings=TransitionSettings.from_dict(
                data.get("transition_settings", {})
            ),
        )
