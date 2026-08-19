"""Machine-readable FFmpeg progress parsing.

FFmpeg is run with ``-progress pipe:1``, producing ``key=value`` records such as
``frame=120``, ``fps=30.0``, ``out_time_us=4000000``, and ``progress=continue``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

ProgressCallback = Callable[[float, int, float], None]


def _as_int(value: str | None) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def _as_float(value: str | None) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


@dataclass
class FFmpegProgressParser:
    """Accumulate progress records and emit a percent/frame/fps callback."""

    total_duration: float | None = None

    def __post_init__(self) -> None:
        self._state: dict[str, str] = {}

    def parse_line(self, line: str, callback: ProgressCallback | None = None) -> dict[str, str]:
        """Parse one progress line and return the current accumulated snapshot."""
        line = line.strip()
        if "=" in line:
            key, value = line.split("=", 1)
            self._state[key] = value

        frame = _as_int(self._state.get("frame"))
        fps = _as_float(self._state.get("fps"))

        if self._state.get("progress") == "end":
            if callback is not None:
                callback(100.0, frame, fps)
            return self._state

        if self.total_duration is not None and self.total_duration > 0:
            out_time_us = _as_float(self._state.get("out_time_us"))
            seconds = out_time_us / 1_000_000.0
            percent = min(100.0, max(0.0, seconds / self.total_duration * 100.0))
            if callback is not None:
                callback(percent, frame, fps)

        return self._state
