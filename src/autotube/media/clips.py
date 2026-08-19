"""Clip processing: trim/loop/normalize stock video into a video-only clip."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..exceptions import MediaError
from .ffmpeg_runner import FFmpegRunner
from .ffprobe import FFprobe
from .progress import ProgressCallback
from .types import MotionEffect, VideoSpec
from .video import VideoProcessor


@dataclass
class ProcessedClip:
    path: Path
    source: Path
    duration: float
    segment_id: str


class ClipProcessor:
    """Produce a normalized, video-only clip for one segment.

    Pipeline: trim (if source longer) → loop (if source shorter) → normalize →
    optional motion → atomic rename. Every visual step is ``-an``, so the output
    has no audio stream.
    """

    def __init__(
        self,
        video: VideoProcessor | None = None,
        runner: FFmpegRunner | None = None,
        probe: FFprobe | None = None,
    ) -> None:
        self.runner = runner or FFmpegRunner()
        self.probe = probe or FFprobe(self.runner)
        self.video = video or VideoProcessor(self.runner, self.probe)

    def process_clip(
        self,
        asset: Path | str,
        segment: Any,
        spec: VideoSpec,
        output_dir: Path | str,
        motion: MotionEffect = MotionEffect.NONE,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ProcessedClip:
        asset = Path(asset)
        output_dir = Path(output_dir)
        segment_id = str(getattr(segment, "segment_id", "clip"))
        start = float(getattr(segment, "start", 0.0))
        end = float(getattr(segment, "end", 0.0))
        requested_duration = end - start

        if requested_duration <= 0:
            raise MediaError("Clip segment must have a positive duration.")

        info = self.video.probe_video(asset)
        source_duration = info.duration or 0.0

        destination = output_dir / "clips" / f"{segment_id}.mp4"

        # Normalization is folded into trim/loop; use those when they apply.
        if source_duration > requested_duration:
            self.video.trim_video(
                asset, destination, spec, start=0.0, end=requested_duration,
                progress=progress, cancel_event=cancel_event,
            )
        else:
            self.video.loop_video(
                asset, destination, spec, requested_duration,
                progress=progress, cancel_event=cancel_event,
            )

        if motion != MotionEffect.NONE:
            destination = self._apply_motion(
                destination, destination, spec, requested_duration,
                motion, progress, cancel_event,
            )

        return ProcessedClip(
            path=destination,
            source=asset,
            duration=requested_duration,
            segment_id=segment_id,
        )

    def _apply_motion(
        self,
        source: Path,
        destination: Path,
        spec: VideoSpec,
        duration: float,
        motion: MotionEffect,
        progress: ProgressCallback | None,
        cancel_event: threading.Event | None,
    ) -> Path:
        from .commands import build_motion_filter, build_normalize_video_cmd
        from .atomic_output import ManagedTempOutput

        motion_filter = build_motion_filter(motion, spec.fps, duration, spec.width, spec.height)
        if not motion_filter:
            return source

        base_cmd = build_normalize_video_cmd(source, destination, spec)
        # Insert the motion filter at the front of the existing filter chain
        # and cap output to the exact requested duration.
        vf_index = base_cmd.index("-vf")
        base_cmd[vf_index + 1] = f"{motion_filter},{base_cmd[vf_index + 1]}"
        input_index = base_cmd.index(str(source))
        base_cmd.insert(input_index + 1, "-t")
        base_cmd.insert(input_index + 2, f"{duration:.3f}")

        cmd = [self.runner.ffmpeg_bin] + base_cmd
        with ManagedTempOutput(destination) as temp:
            self.runner.run(
                cmd[:-1] + [str(temp)],
                duration=duration,
                progress=progress,
                cancel_event=cancel_event,
            )
        return destination
