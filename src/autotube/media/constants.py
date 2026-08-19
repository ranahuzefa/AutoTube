"""Media-specific constants and spec factories.

All render knobs (resolution, fps, codec, volume) are derived from
:class:`autotube.models.RenderSettings` — never hardcoded at call sites.
"""

from __future__ import annotations

from ..constants import DEFAULT_MUSIC_VOLUME
from ..models import RenderSettings
from .types import AudioSpec, FitPolicy, VideoSpec

__all__ = [
    "DEFAULT_MUSIC_VOLUME",
    "audio_spec_default",
    "video_spec_from_render_settings",
]

DEFAULT_VIDEO_CODEC = "libx264"
DEFAULT_PIX_FMT = "yuv420p"
DEFAULT_PRESET = "medium"
DEFAULT_CRF = "18"
DEFAULT_PAD_COLOR = "black"
DEFAULT_FIT = FitPolicy.CONTAIN

DEFAULT_AUDIO_CODEC = "aac"
DEFAULT_AUDIO_BITRATE = "192k"
DEFAULT_AUDIO_SAMPLE_RATE = 48000
DEFAULT_AUDIO_CHANNELS = 2

DEFAULT_CAPTION_STYLE = "burned"


def _parse_resolution(resolution: str) -> tuple[int, int]:
    width, height = resolution.lower().split("x")
    return int(width), int(height)


def video_spec_from_render_settings(settings: RenderSettings) -> VideoSpec:
    """Build a video spec from project render settings.

    Stock/clip visuals default to video-only (``include_audio=False``).
    """
    width, height = _parse_resolution(settings.resolution)
    return VideoSpec(
        width=width,
        height=height,
        fps=settings.fps,
        codec=DEFAULT_VIDEO_CODEC,
        pix_fmt=DEFAULT_PIX_FMT,
        preset=DEFAULT_PRESET,
        crf=DEFAULT_CRF,
        fit=DEFAULT_FIT,
        pad_color=DEFAULT_PAD_COLOR,
        include_audio=False,
    )


def audio_spec_default() -> AudioSpec:
    return AudioSpec(
        codec=DEFAULT_AUDIO_CODEC,
        bitrate=DEFAULT_AUDIO_BITRATE,
        sample_rate=DEFAULT_AUDIO_SAMPLE_RATE,
        channels=DEFAULT_AUDIO_CHANNELS,
    )
