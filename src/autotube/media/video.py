"""Video operations: probing, normalization, trimming, and looping.

All visual primitives produce video-only output by default (``-an``) so stock
clip audio never leaks into the final composition.
"""

from __future__ import annotations

import threading
from pathlib import Path

from ..exceptions import MediaError
from .atomic_output import ManagedTempOutput
from .commands import build_loop_video_cmd, build_normalize_video_cmd, build_trim_video_cmd
from .ffmpeg_runner import FFmpegRunner
from .ffprobe import FFprobe
from .progress import ProgressCallback
from .types import MediaInfo, StreamInfo, VideoSpec


class VideoProcessor:
    """Real FFmpeg-backed video operations for stock/clip visuals."""

    def __init__(self, runner: FFmpegRunner | None = None, probe: FFprobe | None = None) -> None:
        self.runner = runner or FFmpegRunner()
        self.probe = probe or FFprobe(self.runner)

    def probe_video(self, path: Path | str) -> MediaInfo:
        info = self.probe.probe(path)
        info.require_video()
        if info.duration is None or info.duration <= 0:
            raise MediaError(f"Video has no positive duration: {path}")
        return info

    def normalize_video(
        self,
        source: Path | str,
        destination: Path | str,
        spec: VideoSpec,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        destination = Path(destination)
        info = self.probe_video(source)
        cmd = [self.runner.ffmpeg_bin] + build_normalize_video_cmd(source, destination, spec)
        self._run(cmd, destination, info.duration, progress, cancel_event)
        return destination

    def trim_video(
        self,
        source: Path | str,
        destination: Path | str,
        spec: VideoSpec,
        start: float,
        end: float,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        if end <= start:
            raise MediaError("Video trim end must be greater than start.")
        destination = Path(destination)
        info = self.probe_video(source)
        duration = end - start
        cmd = [self.runner.ffmpeg_bin] + build_trim_video_cmd(source, destination, spec, start, end)
        self._run(cmd, destination, duration, progress, cancel_event)
        return destination

    def loop_video(
        self,
        source: Path | str,
        destination: Path | str,
        spec: VideoSpec,
        duration: float,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        if duration <= 0:
            raise MediaError("Loop duration must be positive.")
        destination = Path(destination)
        self.probe_video(source)
        cmd = [self.runner.ffmpeg_bin] + build_loop_video_cmd(source, destination, spec, duration)
        self._run(cmd, destination, duration, progress, cancel_event)
        return destination

    def _run(
        self,
        cmd: list[str],
        destination: Path,
        duration: float | None,
        progress: ProgressCallback | None,
        cancel_event: threading.Event | None,
    ) -> None:
        with ManagedTempOutput(destination) as temp:
            self.runner.run(
                cmd[:-1] + [str(temp)],
                duration=duration,
                progress=progress,
                cancel_event=cancel_event,
            )
