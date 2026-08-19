"""Caption/SRT generation and subtitle burn-in foundation."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Iterable

from ..exceptions import MediaError
from .atomic_output import ManagedTempOutput
from .commands import build_burn_captions_cmd
from .ffmpeg_runner import FFmpegRunner
from .ffprobe import FFprobe
from .progress import ProgressCallback
from .types import VideoSpec


def _ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def write_srt(segments: Iterable[Any], path: Path | str) -> Path:
    """Write standard SRT from segment-like objects with start/end/text."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    for index, segment in enumerate(segments, start=1):
        start = float(getattr(segment, "start", 0.0))
        end = float(getattr(segment, "end", start))
        text = str(getattr(segment, "text", ""))
        blocks.append(f"{index}\n{_ts(start)} --> {_ts(end)}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


class CaptionRenderer:
    """Burn SRT captions into a video (video-only by default)."""

    def __init__(self, runner: FFmpegRunner | None = None, probe: FFprobe | None = None) -> None:
        self.runner = runner or FFmpegRunner()
        self.probe = probe or FFprobe(self.runner)

    def render_captions(
        self,
        video: Path | str,
        srt: Path | str,
        destination: Path | str,
        spec: VideoSpec,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        video = Path(video)
        srt = Path(srt)
        destination = Path(destination)
        if not srt.exists():
            raise MediaError(f"SRT file does not exist: {srt}")
        info = self.probe.probe(video)
        info.require_video()

        cmd = [self.runner.ffmpeg_bin] + build_burn_captions_cmd(video, srt, destination, spec)
        with ManagedTempOutput(destination) as temp:
            self.runner.run(
                cmd[:-1] + [str(temp)],
                duration=info.duration,
                progress=progress,
                cancel_event=cancel_event,
            )
        return destination
