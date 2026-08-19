"""Typed media metadata and processing specs.

These dataclasses follow the same explicit ``to_dict``/``from_dict`` pattern as
the Phase 1 models, so probe results can be persisted into project/segment state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ..exceptions import MediaError


class FitPolicy(str, Enum):
    """How to fit source video into the target frame without distortion."""

    CONTAIN = "contain"
    COVER = "cover"


class MotionEffect(str, Enum):
    NONE = "none"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"


def _num(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class StreamInfo:
    """A single media stream from FFprobe."""

    index: int
    codec_type: str
    codec_name: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    pix_fmt: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    duration: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "codec_type": self.codec_type,
            "codec_name": self.codec_name,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "pix_fmt": self.pix_fmt,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamInfo":
        return cls(
            index=int(data.get("index", -1)),
            codec_type=str(data.get("codec_type", "")),
            codec_name=data.get("codec_name"),
            width=_num(data.get("width")),
            height=_num(data.get("height")),
            fps=_float(data.get("fps")),
            pix_fmt=data.get("pix_fmt"),
            sample_rate=_num(data.get("sample_rate")),
            channels=_num(data.get("channels")),
            duration=_float(data.get("duration")),
        )


@dataclass
class MediaInfo:
    """Container/format-level media metadata plus streams."""

    path: Path
    format_name: str | None = None
    duration: float | None = None
    bit_rate: int | None = None
    streams: list[StreamInfo] = field(default_factory=list)

    def video_stream(self) -> StreamInfo | None:
        return next((s for s in self.streams if s.codec_type == "video"), None)

    def audio_stream(self) -> StreamInfo | None:
        return next((s for s in self.streams if s.codec_type == "audio"), None)

    def require_video(self) -> StreamInfo:
        stream = self.video_stream()
        if stream is None:
            raise MediaError(f"No video stream found in {self.path}")
        return stream

    def require_audio(self) -> StreamInfo:
        stream = self.audio_stream()
        if stream is None:
            raise MediaError(f"No audio stream found in {self.path}")
        return stream

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "format_name": self.format_name,
            "duration": self.duration,
            "bit_rate": self.bit_rate,
            "streams": [s.to_dict() for s in self.streams],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MediaInfo":
        return cls(
            path=Path(str(data.get("path", ""))),
            format_name=data.get("format_name"),
            duration=_float(data.get("duration")),
            bit_rate=_num(data.get("bit_rate")),
            streams=[StreamInfo.from_dict(s) for s in data.get("streams", [])],
        )


@dataclass
class AudioSpec:
    """Deterministic audio encoding profile for voiceover/BGM."""

    codec: str = "aac"
    bitrate: str = "192k"
    sample_rate: int = 48000
    channels: int = 2


@dataclass
class VideoSpec:
    """Deterministic video encoding profile for stock/clip visuals."""

    width: int
    height: int
    fps: int
    codec: str = "libx264"
    pix_fmt: str = "yuv420p"
    preset: str = "medium"
    crf: str = "18"
    fit: FitPolicy = FitPolicy.CONTAIN
    pad_color: str = "black"
    include_audio: bool = False

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"
