"""faster-whisper transcription service."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..exceptions import (
    MediaError,
    TranscriptionCancelledError,
    TranscriptionError,
)
from ..state import SegmentState, WordState
from .config import TranscriptionConfig
from .model import WhisperModelLoader

TranscriptionProgressCallback = Callable[[float], None]


@dataclass
class TranscriptionResult:
    segments: list[SegmentState]
    language: str
    language_probability: float
    duration: float
    model: str
    device: str
    compute_type: str


class FasterWhisperTranscriptionService:
    """Concrete faster-whisper transcription service.

    Cancellation is cooperative: it is checked before model load, after model
    load, and between yielded segments. A single in-progress inference step or
    model download cannot be interrupted.
    """

    def __init__(self, loader: WhisperModelLoader | None = None) -> None:
        self._loader = loader or WhisperModelLoader()
        self._transcription_lock = threading.Lock()

    def transcribe(
        self, voiceover_path: Path, model: str
    ) -> list[SegmentState]:
        """Backward-compatible Phase 1 API."""
        config = TranscriptionConfig(model=model)
        return self.transcribe_with_config(voiceover_path, config).segments

    def transcribe_with_config(
        self,
        voiceover_path: Path,
        config: TranscriptionConfig,
        *,
        progress: TranscriptionProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> TranscriptionResult:
        voiceover_path = Path(voiceover_path)
        if not voiceover_path.exists():
            raise MediaError(f"Voiceover file does not exist: {voiceover_path}")

        # Cooperative cancellation before model load.
        self._check_cancel(cancel_event)
        model = self._loader.get(config)
        self._check_cancel(cancel_event)

        with self._transcription_lock:
            return self._run_locked(
                voiceover_path, config, model, progress, cancel_event
            )

    def _run_locked(
        self,
        voiceover_path: Path,
        config: TranscriptionConfig,
        model,
        progress: TranscriptionProgressCallback | None,
        cancel_event: threading.Event | None,
    ) -> TranscriptionResult:
        from .device import DeviceDetector

        device = DeviceDetector().detect(config.device, config.compute_type)
        total_duration = self._probe_duration(voiceover_path)

        try:
            segments_iter, info = model.transcribe(
                str(voiceover_path),
                language=config.language,
                word_timestamps=config.word_timestamps,
                vad_filter=config.vad_filter,
                condition_on_previous_text=config.condition_on_previous_text,
            )
        except Exception as exc:  # noqa: BLE001 - wrap transcription failures
            raise TranscriptionError(f"Transcription failed: {exc}") from exc

        segments: list[SegmentState] = []
        last_percent = 0.0
        if progress is not None:
            progress(0.0)

        for raw in segments_iter:
            self._check_cancel(cancel_event)
            segment = self._to_segment(raw)
            if segment is None:
                continue
            segments.append(segment)

            if progress is not None and total_duration and total_duration > 0:
                percent = min(100.0, max(0.0, segment.end / total_duration * 100.0))
                if percent > last_percent:
                    progress(percent)
                    last_percent = percent

        self._check_cancel(cancel_event)

        if progress is not None:
            progress(100.0)

        duration = total_duration or (segments[-1].end if segments else 0.0)
        return TranscriptionResult(
            segments=segments,
            language=info.language,
            language_probability=info.language_probability,
            duration=duration,
            model=config.model,
            device=device.device,
            compute_type=device.compute_type,
        )

    @staticmethod
    def _probe_duration(voiceover_path: Path) -> float | None:
        try:
            from ..media.service import FFmpegMediaService

            return FFmpegMediaService().probe_audio(voiceover_path).duration
        except Exception:  # noqa: BLE001 - duration is optional for progress
            return None

    @staticmethod
    def _to_segment(raw) -> SegmentState | None:
        text = (getattr(raw, "text", "") or "").strip()
        if not text:
            return None

        start = float(getattr(raw, "start", 0.0))
        end = float(getattr(raw, "end", start))
        words = []
        for word in getattr(raw, "words", None) or []:
            words.append(
                WordState(
                    word=getattr(word, "word", ""),
                    start=float(getattr(word, "start", start)),
                    end=float(getattr(word, "end", end)),
                    probability=getattr(word, "probability", None),
                )
            )
        from uuid import uuid4

        return SegmentState(
            segment_id=str(uuid4()),
            text=text,
            start=start,
            end=end,
            words=words,
        )

    @staticmethod
    def _check_cancel(cancel_event: threading.Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise TranscriptionCancelledError("Transcription cancelled.")
