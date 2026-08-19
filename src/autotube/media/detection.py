"""FFmpeg/FFprobe availability detection.

This module is independent of the GUI and used before pipeline or render
execution so missing binaries are reported as a clear, user-facing error rather
than a deep ``FFmpegRunner`` failure.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaTooling:
    ffmpeg: str | None
    ffprobe: str | None

    @property
    def available(self) -> bool:
        return self.ffmpeg is not None and self.ffprobe is not None

    def missing_names(self) -> list[str]:
        missing = []
        if self.ffmpeg is None:
            missing.append("ffmpeg")
        if self.ffprobe is None:
            missing.append("ffprobe")
        return missing


def _bundled_candidates(name: str) -> list[Path]:
    """Return candidate paths for bundled binaries inside a frozen app."""
    if not getattr(_sys_module(), "frozen", False):
        return []
    base = Path(getattr(_sys_module(), "executable", Path.cwd())).parent
    executable = name + (".exe" if os.name == "nt" else "")
    return [base / "ffmpeg" / executable, base / executable]


def _sys_module():
    import sys

    return sys


def _which(name: str) -> str | None:
    return shutil.which(name)


def detect_media_tooling() -> MediaTooling:
    """Return resolved ffmpeg/ffprobe paths, preferring PATH over bundled."""
    ffmpeg = _which("ffmpeg")
    ffprobe = _which("ffprobe")

    if ffmpeg is None:
        ffmpeg = _first_existing(_bundled_candidates("ffmpeg"))
    if ffprobe is None:
        ffprobe = _first_existing(_bundled_candidates("ffprobe"))

    return MediaTooling(ffmpeg=ffmpeg, ffprobe=ffprobe)


def _first_existing(paths: list[Path]) -> str | None:
    for path in paths:
        if path.exists():
            return str(path)
    return None


def require_media_tooling() -> MediaTooling:
    """Return tooling or raise a clear ``RuntimeError`` naming missing binaries."""
    tooling = detect_media_tooling()
    if not tooling.available:
        names = ", ".join(tooling.missing_names())
        raise RuntimeError(
            f"Required media tools are missing: {names}. "
            "Install FFmpeg and FFprobe and ensure they are on PATH, or place "
            "them in the bundled ffmpeg directory."
        )
    return tooling
