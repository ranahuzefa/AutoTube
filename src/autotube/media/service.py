"""Concrete FFmpeg-backed media service.

Implements the media operations defined by the ``MediaService`` protocol. This
module imports no GUI code and is safe to use from the CLI, pipeline, or workers.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Iterable

from ..constants import DEFAULT_TRANSITION_SOUND_VOLUME
from .atomic_output import ManagedTempOutput
from .audio import AudioProcessor
from .captions import CaptionRenderer
from .clips import ClipProcessor, ProcessedClip
from .commands import (
    build_black_segment_cmd,
    build_compose_cmd,
    build_compose_video_only_cmd,
    build_image_duration_cmd,
    build_mux_video_audio_cmd,
    build_overlay_subtitles_cmd,
    build_transition_run_cmd,
    build_transition_sfx_cmd,
)
from .ffmpeg_runner import FFmpegRunner
from .ffprobe import FFprobe
from .progress import ProgressCallback
from .types import AudioSpec, MediaInfo, MotionEffect, VideoSpec
from .video import VideoProcessor


class FFmpegMediaService:
    """Aggregate FFmpeg media operations with a shared runner/probe."""

    def __init__(self, runner: FFmpegRunner | None = None, probe: FFprobe | None = None) -> None:
        self.runner = runner or FFmpegRunner()
        self.probe = probe or FFprobe(self.runner)
        self.audio = AudioProcessor(self.runner, self.probe)
        self.video = VideoProcessor(self.runner, self.probe)
        self.captions = CaptionRenderer(self.runner, self.probe)
        self.clips = ClipProcessor(self.video, self.runner, self.probe)

    def probe_media(self, path: Path | str) -> MediaInfo:
        return self.probe.probe(path)

    def probe_video(self, path: Path | str) -> MediaInfo:
        return self.video.probe_video(path)

    def probe_audio(self, path: Path | str) -> MediaInfo:
        return self.audio.probe_audio(path)

    def normalize_audio(
        self,
        source: Path | str,
        destination: Path | str,
        spec: AudioSpec | None = None,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        return self.audio.normalize_audio(source, destination, spec, progress=progress, cancel_event=cancel_event)

    def normalize_video(
        self,
        source: Path | str,
        destination: Path | str,
        spec: VideoSpec,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        return self.video.normalize_video(source, destination, spec, progress=progress, cancel_event=cancel_event)

    def trim_audio(
        self,
        source: Path | str,
        destination: Path | str,
        start: float,
        end: float,
        spec: AudioSpec | None = None,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        return self.audio.trim_audio(source, destination, start, end, spec, progress=progress, cancel_event=cancel_event)

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
        return self.video.trim_video(source, destination, spec, start, end, progress=progress, cancel_event=cancel_event)

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
        return self.video.loop_video(source, destination, spec, duration, progress=progress, cancel_event=cancel_event)

    def mix_audio(
        self,
        voiceover: Path | str,
        destination: Path | str,
        music: Path | str | None = None,
        spec: AudioSpec | None = None,
        music_volume: float | None = None,
        *,
        sfx: Path | str | None = None,
        sfx_volume: float = DEFAULT_TRANSITION_SOUND_VOLUME,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        kwargs = {}
        if music_volume is not None:
            kwargs["music_volume"] = music_volume
        return self.audio.mix_audio(
            voiceover,
            destination,
            music,
            spec,
            sfx=sfx,
            sfx_volume=sfx_volume,
            progress=progress,
            cancel_event=cancel_event,
            **kwargs,
        )

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
        return self.captions.render_captions(video, srt, destination, spec, progress=progress, cancel_event=cancel_event)

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
        return self.clips.process_clip(
            asset, segment, spec, output_dir, motion,
            progress=progress, cancel_event=cancel_event,
        )

    def compose(
        self,
        clip_list_file: Path | str,
        audio: Path | str,
        destination: Path | str,
        spec: VideoSpec,
        audio_spec: AudioSpec | None = None,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Compose video-only clips with a separately mixed final audio track."""
        destination = Path(destination)
        info = self.probe.probe(audio)
        info.require_audio()

        cmd = [self.runner.ffmpeg_bin] + build_compose_cmd(
            clip_list_file, audio, destination, spec, audio_spec
        )
        with ManagedTempOutput(destination) as temp:
            self.runner.run(
                cmd[:-1] + [str(temp)],
                duration=info.duration,
                progress=progress,
                cancel_event=cancel_event,
            )
        return destination

    def compose_video_only(
        self,
        clip_list_file: Path | str,
        destination: Path | str,
        spec: VideoSpec,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Compose video-only clips without any audio stream."""
        destination = Path(destination)
        cmd = [self.runner.ffmpeg_bin] + build_compose_video_only_cmd(
            clip_list_file, destination, spec
        )
        with ManagedTempOutput(destination) as temp:
            self.runner.run(
                cmd[:-1] + [str(temp)],
                duration=None,
                progress=progress,
                cancel_event=cancel_event,
            )
        return destination

    def compose_transition_run(
        self,
        inputs: list[Path | str],
        durations: list[float],
        transition_names: list[str],
        destination: Path | str,
        spec: VideoSpec,
        duration: float,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Render an overlapping crossfade run of adjacent clips."""
        destination = Path(destination)
        cmd = [self.runner.ffmpeg_bin] + build_transition_run_cmd(
            inputs, durations, transition_names, duration, destination, spec
        )
        total = sum(durations)
        with ManagedTempOutput(destination) as temp:
            self.runner.run(
                cmd[:-1] + [str(temp)],
                duration=total,
                progress=progress,
                cancel_event=cancel_event,
            )
        return destination

    def build_transition_sfx(
        self,
        placements: list[tuple[Path | str, float]],
        destination: Path | str,
        *,
        duration: float,
        transition_duration: float,
        spec: AudioSpec | None = None,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Render a transition-SFX placement track trimmed to voiceover length."""
        spec = spec or AudioSpec()
        destination = Path(destination)
        cmd = [self.runner.ffmpeg_bin] + build_transition_sfx_cmd(
            placements,
            duration,
            destination,
            spec,
            transition_duration=transition_duration,
        )
        with ManagedTempOutput(destination) as temp:
            self.runner.run(
                cmd[:-1] + [str(temp)],
                duration=duration,
                progress=progress,
                cancel_event=cancel_event,
            )
        return destination

    def normalize_image(
        self,
        source: Path | str,
        destination: Path | str,
        spec: VideoSpec,
        duration: float,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Render a still image into a video-only clip of exact duration."""
        destination = Path(destination)
        cmd = [self.runner.ffmpeg_bin] + build_image_duration_cmd(
            source, destination, spec, duration
        )
        with ManagedTempOutput(destination) as temp:
            self.runner.run(
                cmd[:-1] + [str(temp)],
                duration=duration,
                progress=progress,
                cancel_event=cancel_event,
            )
        return destination

    def mux_video_audio(
        self,
        video: Path | str,
        audio: Path | str,
        destination: Path | str,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Mux a video-only track with the final mixed audio track."""
        destination = Path(destination)
        cmd = [self.runner.ffmpeg_bin] + build_mux_video_audio_cmd(
            video, audio, destination
        )
        with ManagedTempOutput(destination) as temp:
            self.runner.run(
                cmd[:-1] + [str(temp)],
                duration=None,
                progress=progress,
                cancel_event=cancel_event,
            )
        return destination

    def black_segment(
        self,
        destination: Path | str,
        spec: VideoSpec,
        duration: float,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Generate a video-only black clip of exact duration."""
        destination = Path(destination)
        cmd = [self.runner.ffmpeg_bin] + build_black_segment_cmd(
            destination, spec, duration
        )
        with ManagedTempOutput(destination) as temp:
            self.runner.run(
                cmd[:-1] + [str(temp)],
                duration=duration,
                progress=progress,
                cancel_event=cancel_event,
            )
        return destination

    def overlay_subtitles(
        self,
        video: Path | str,
        ass: Path | str,
        destination: Path | str,
        spec: VideoSpec,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Burn an ASS subtitle file into a video-only track."""
        destination = Path(destination)
        cmd = [self.runner.ffmpeg_bin] + build_overlay_subtitles_cmd(
            video, ass, destination, spec
        )
        with ManagedTempOutput(destination) as temp:
            self.runner.run(
                cmd[:-1] + [str(temp)],
                duration=None,
                progress=progress,
                cancel_event=cancel_event,
            )
        return destination
