"""Transcription configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..constants import (
    DEFAULT_MAX_SEGMENT_DURATION,
    DEFAULT_MERGE_GAP_THRESHOLD,
    DEFAULT_MIN_SEGMENT_DURATION,
    DEFAULT_VAD_FILTER,
    DEFAULT_WHISPER_MODEL,
)
from ..models import RenderSettings


@dataclass
class TranscriptionConfig:
    """Configuration for a faster-whisper transcription run."""

    model: str = DEFAULT_WHISPER_MODEL
    device: str = "auto"
    compute_type: str = "auto"
    cpu_threads: int = 0
    language: str | None = None
    word_timestamps: bool = True
    vad_filter: bool = DEFAULT_VAD_FILTER
    condition_on_previous_text: bool = False
    min_segment_duration: float = DEFAULT_MIN_SEGMENT_DURATION
    max_segment_duration: float = DEFAULT_MAX_SEGMENT_DURATION
    merge_gap_threshold: float = DEFAULT_MERGE_GAP_THRESHOLD
    download_root: str | None = None

    @classmethod
    def from_render_settings(cls, settings: RenderSettings) -> "TranscriptionConfig":
        return cls(model=settings.whisper_model)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "device": self.device,
            "compute_type": self.compute_type,
            "cpu_threads": self.cpu_threads,
            "language": self.language,
            "word_timestamps": self.word_timestamps,
            "vad_filter": self.vad_filter,
            "condition_on_previous_text": self.condition_on_previous_text,
            "min_segment_duration": self.min_segment_duration,
            "max_segment_duration": self.max_segment_duration,
            "merge_gap_threshold": self.merge_gap_threshold,
            "download_root": self.download_root,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscriptionConfig":
        return cls(
            model=str(data.get("model", DEFAULT_WHISPER_MODEL)),
            device=str(data.get("device", "auto")),
            compute_type=str(data.get("compute_type", "auto")),
            cpu_threads=int(data.get("cpu_threads", 0)),
            language=data.get("language"),
            word_timestamps=bool(data.get("word_timestamps", True)),
            vad_filter=bool(data.get("vad_filter", DEFAULT_VAD_FILTER)),
            condition_on_previous_text=bool(
                data.get("condition_on_previous_text", False)
            ),
            min_segment_duration=float(
                data.get("min_segment_duration", DEFAULT_MIN_SEGMENT_DURATION)
            ),
            max_segment_duration=float(
                data.get("max_segment_duration", DEFAULT_MAX_SEGMENT_DURATION)
            ),
            merge_gap_threshold=float(
                data.get("merge_gap_threshold", DEFAULT_MERGE_GAP_THRESHOLD)
            ),
            download_root=data.get("download_root"),
        )
