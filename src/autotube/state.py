"""Resumable project state: stages, segments, and persistence-friendly data.

The pipeline stage model maps one-to-one to the master workflow. Audio mixing/BGM
and captions are first-class stages, not hidden inside composition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import Project, RenderSettings, _isoformat, _parse_datetime, _path_to_str, _str_to_path


class PipelineStage(str, Enum):
    """Ordered pipeline stages."""

    TRANSCRIBED = "transcribed"
    SEGMENTS_READY = "segments_ready"
    KEYWORDS_READY = "keywords_ready"
    ASSETS_READY = "assets_ready"
    CLIPS_READY = "clips_ready"
    COMPOSED = "composed"
    AUDIO_READY = "audio_ready"
    CAPTIONS_READY = "captions_ready"
    COMPLETED = "completed"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SegmentStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class KeywordSource(str, Enum):
    """Where a segment's keywords were generated."""

    LOCAL = "local"
    AI = "ai"


STAGE_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.TRANSCRIBED,
    PipelineStage.SEGMENTS_READY,
    PipelineStage.KEYWORDS_READY,
    PipelineStage.ASSETS_READY,
    PipelineStage.CLIPS_READY,
    PipelineStage.COMPOSED,
    PipelineStage.AUDIO_READY,
    PipelineStage.CAPTIONS_READY,
    PipelineStage.COMPLETED,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class StageState:
    """Status and artifacts for a single pipeline stage."""

    stage: PipelineStage
    status: StageStatus = StageStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    artifacts: list[Path] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "started_at": _isoformat(self.started_at),
            "finished_at": _isoformat(self.finished_at),
            "error": self.error,
            "artifacts": [_path_to_str(p) for p in self.artifacts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageState":
        return cls(
            stage=PipelineStage(data["stage"]),
            status=StageStatus(data.get("status", "pending")),
            started_at=_parse_datetime(data.get("started_at")),
            finished_at=_parse_datetime(data.get("finished_at")),
            error=data.get("error"),
            artifacts=[Path(a) for a in data.get("artifacts", [])],
        )


@dataclass
class WordState:
    """A single word with timing information."""

    word: str
    start: float
    end: float
    probability: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "word": self.word,
            "start": self.start,
            "end": self.end,
            "probability": self.probability,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WordState":
        return cls(
            word=str(data["word"]),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            probability=(
                float(data["probability"]) if data.get("probability") is not None else None
            ),
        )


@dataclass
class TranscriptionInfo:
    """Metadata about a completed transcription run."""

    language: str | None = None
    language_probability: float | None = None
    duration: float | None = None
    model: str | None = None
    device: str | None = None
    compute_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "language_probability": self.language_probability,
            "duration": self.duration,
            "model": self.model,
            "device": self.device,
            "compute_type": self.compute_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscriptionInfo":
        return cls(
            language=data.get("language"),
            language_probability=(
                float(data["language_probability"])
                if data.get("language_probability") is not None
                else None
            ),
            duration=(
                float(data["duration"]) if data.get("duration") is not None else None
            ),
            model=data.get("model"),
            device=data.get("device"),
            compute_type=data.get("compute_type"),
        )


@dataclass
class SegmentState:
    """Per-segment processing state."""

    segment_id: str
    text: str
    start: float = 0.0
    end: float = 0.0
    keywords: list[str] = field(default_factory=list)
    selected_clip: dict[str, Any] | None = None
    status: SegmentStatus = SegmentStatus.PENDING
    error: str | None = None
    words: list[WordState] = field(default_factory=list)
    keyword_source: KeywordSource = KeywordSource.LOCAL

    @classmethod
    def new(cls, text: str, start: float = 0.0, end: float = 0.0) -> "SegmentState":
        return cls(segment_id=str(uuid4()), text=text, start=start, end=end)

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "keywords": list(self.keywords),
            "selected_clip": self.selected_clip,
            "status": self.status.value,
            "error": self.error,
            "words": [w.to_dict() for w in self.words],
            "keyword_source": self.keyword_source.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SegmentState":
        return cls(
            segment_id=str(data["segment_id"]),
            text=str(data.get("text", "")),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            keywords=[str(k) for k in data.get("keywords", [])],
            selected_clip=data.get("selected_clip"),
            status=SegmentStatus(data.get("status", "pending")),
            error=data.get("error"),
            words=[WordState.from_dict(w) for w in data.get("words", [])],
            keyword_source=KeywordSource(data.get("keyword_source", "local")),
        )


@dataclass
class ProjectState:
    """Full resumable project state."""

    project_id: str = field(default_factory=lambda: str(uuid4()))
    project: Project | None = None
    render_settings: RenderSettings = field(default_factory=RenderSettings)
    stages: dict[PipelineStage, StageState] = field(default_factory=dict)
    segments: list[SegmentState] = field(default_factory=list)
    transcription: TranscriptionInfo | None = None
    timeline: "TimelineState | None" = None
    last_error: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    version: int = 1

    def __post_init__(self) -> None:
        # Ensure every known stage has a state entry.
        for stage in STAGE_ORDER:
            self.stages.setdefault(stage, StageState(stage=stage))

    def stage(self, stage: PipelineStage) -> StageState:
        return self.stages[stage]

    def next_pending_stage(self, force: bool = False) -> PipelineStage | None:
        """Return the first stage to run (pending or failed), respecting order."""
        for stage in STAGE_ORDER:
            state = self.stages[stage]
            if force or state.status in (StageStatus.PENDING, StageStatus.FAILED):
                return stage
        return None

    def is_complete(self) -> bool:
        return all(
            self.stages[s].status in (StageStatus.COMPLETED, StageStatus.SKIPPED)
            for s in STAGE_ORDER
        )

    def touch(self) -> None:
        self.updated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project": self.project.to_dict() if self.project else None,
            "render_settings": self.render_settings.to_dict(),
            "stages": [self.stages[s].to_dict() for s in STAGE_ORDER],
            "segments": [s.to_dict() for s in self.segments],
            "transcription": self.transcription.to_dict() if self.transcription else None,
            "timeline": self.timeline.to_dict() if self.timeline else None,
            "last_error": self.last_error,
            "created_at": _isoformat(self.created_at),
            "updated_at": _isoformat(self.updated_at),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectState":
        from .timeline.types import TimelineState

        state = cls(
            project_id=str(data.get("project_id") or str(uuid4())),
            project=Project.from_dict(data["project"]) if data.get("project") else None,
            render_settings=RenderSettings.from_dict(data.get("render_settings", {})),
            segments=[SegmentState.from_dict(s) for s in data.get("segments", [])],
            transcription=(
                TranscriptionInfo.from_dict(data["transcription"])
                if data.get("transcription")
                else None
            ),
            timeline=(
                TimelineState.from_dict(data["timeline"])
                if data.get("timeline")
                else None
            ),
            last_error=data.get("last_error"),
            created_at=_parse_datetime(data.get("created_at")) or _now(),
            updated_at=_parse_datetime(data.get("updated_at")) or _now(),
            version=int(data.get("version", 1)),
        )
        for stage_data in data.get("stages", []):
            stage = StageState.from_dict(stage_data)
            state.stages[stage.stage] = stage
        state.__post_init__()
        return state
