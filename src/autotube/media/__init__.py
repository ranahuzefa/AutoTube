"""FFmpeg/FFprobe media core.

This package is intentionally independent of the GUI. It uses only Python's
standard library and talks to FFmpeg/FFprobe via direct subprocess argument
lists (``shell=False``).
"""

from .audio import AudioProcessor
from .captions import CaptionRenderer, write_srt
from .clips import ClipProcessor, ProcessedClip
from .ffmpeg_runner import FFmpegResult, FFmpegRunner
from .ffprobe import FFprobe
from .service import FFmpegMediaService
from .types import (
    AudioSpec,
    FitPolicy,
    MediaInfo,
    MotionEffect,
    StreamInfo,
    VideoSpec,
)
from .video import VideoProcessor

__all__ = [
    "AudioProcessor",
    "AudioSpec",
    "CaptionRenderer",
    "ClipProcessor",
    "FFmpegMediaService",
    "FFmpegResult",
    "FFmpegRunner",
    "FFprobe",
    "FitPolicy",
    "MediaInfo",
    "MotionEffect",
    "ProcessedClip",
    "StreamInfo",
    "VideoProcessor",
    "VideoSpec",
    "write_srt",
]
