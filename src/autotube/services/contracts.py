"""Service contracts for later phases.

These are pure `typing.Protocol` interfaces, not instantiable classes. Phase 1
defines the contracts; no fake implementations exist here.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Protocol

from ..exceptions import AutoTubeError
from ..media.progress import ProgressCallback
from ..media.types import AudioSpec, MediaInfo, MotionEffect, VideoSpec
from ..state import SegmentState
from ..transcription.config import TranscriptionConfig
from ..transcription.service import (
    TranscriptionProgressCallback,
    TranscriptionResult,
)


class TranscriptionService(Protocol):
    """Transcribe a voiceover into timed segments.

    ``transcribe`` is the Phase 1-compatible signature and must remain valid.
    ``transcribe_with_config`` is the Phase 3 additive API.
    """

    def transcribe(self, voiceover_path: Path, model: str) -> list[SegmentState]:
        """Return timed segments. Raises TranscriptionError on failure."""
        ...

    def transcribe_with_config(
        self,
        voiceover_path: Path,
        config: TranscriptionConfig,
        *,
        progress: TranscriptionProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> TranscriptionResult:
        """Return a full transcription result. Raises TranscriptionError."""
        ...


class KeywordService(Protocol):
    """Generate visual keywords for a segment."""

    def generate_keywords(self, segment: SegmentState) -> list[str]:
        """Return keywords for a segment. Raises AutoTubeError on failure."""
        ...


class StockService(Protocol):
    """Search and download stock footage.

    ``search``/``download`` are the Phase 1-compatible signatures. Phase 4 adds
    richer dataclass-based methods while preserving these existing methods.
    """

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Return candidate assets. Raises StockError on failure."""
        ...

    def download(self, asset: dict[str, Any], destination: Path) -> Path:
        """Download an asset and return its local path. Raises StockError."""
        ...


class MediaService(Protocol):
    """Media/FFmpeg operations.

    Video primitives and ``process_clip`` are video-only by default; audio mixing
    is a separate operation, so stock clip audio can never leak into a final
    composition.
    """

    def probe_media(self, path: Path) -> MediaInfo:
        ...

    def probe_audio(self, path: Path) -> MediaInfo:
        ...

    def probe_video(self, path: Path) -> MediaInfo:
        ...

    def normalize_audio(
        self,
        source: Path,
        destination: Path,
        spec: AudioSpec | None = None,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        ...

    def normalize_video(
        self,
        source: Path,
        destination: Path,
        spec: VideoSpec,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        ...

    def trim_audio(
        self,
        source: Path,
        destination: Path,
        start: float,
        end: float,
        spec: AudioSpec | None = None,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        ...

    def trim_video(
        self,
        source: Path,
        destination: Path,
        spec: VideoSpec,
        start: float,
        end: float,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        ...

    def loop_video(
        self,
        source: Path,
        destination: Path,
        spec: VideoSpec,
        duration: float,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        ...

    def render_captions(
        self,
        video: Path,
        srt: Path,
        destination: Path,
        spec: VideoSpec,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        ...

    def mix_audio(
        self,
        voiceover: Path,
        destination: Path,
        music: Path | None = None,
        spec: AudioSpec | None = None,
        music_volume: float | None = None,
        *,
        sfx: Path | None = None,
        sfx_volume: float | None = None,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        ...

    def process_clip(
        self,
        asset: Path,
        segment: Any,
        spec: VideoSpec,
        output_dir: Path,
        motion: MotionEffect = MotionEffect.NONE,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Any:
        ...

    def compose(
        self,
        clip_list_file: Path,
        audio: Path,
        destination: Path,
        spec: VideoSpec,
        audio_spec: AudioSpec | None = None,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        ...

    def compose_transition_run(
        self,
        inputs: list[Path],
        durations: list[float],
        transition_names: list[str],
        destination: Path,
        spec: VideoSpec,
        duration: float,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        ...

    def build_transition_sfx(
        self,
        placements: list[tuple[Path, float]],
        destination: Path,
        *,
        duration: float,
        transition_duration: float,
        spec: AudioSpec | None = None,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        ...
