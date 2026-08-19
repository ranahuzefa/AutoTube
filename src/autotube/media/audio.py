"""Audio operations: probing, normalization, trimming, and mixing."""

from __future__ import annotations

import threading
from pathlib import Path

from ..exceptions import MediaError
from .atomic_output import ManagedTempOutput
from .commands import (
    build_mix_audio_cmd,
    build_normalize_audio_cmd,
    build_trim_audio_cmd,
)
from ..constants import DEFAULT_TRANSITION_SOUND_VOLUME
from .constants import DEFAULT_MUSIC_VOLUME
from .ffmpeg_runner import FFmpegRunner
from .ffprobe import FFprobe
from .progress import ProgressCallback
from .types import AudioSpec, MediaInfo, StreamInfo


class AudioProcessor:
    """Real FFmpeg-backed audio operations for voiceover and BGM."""

    def __init__(self, runner: FFmpegRunner | None = None, probe: FFprobe | None = None) -> None:
        self.runner = runner or FFmpegRunner()
        self.probe = probe or FFprobe(self.runner)

    def probe_audio(self, path: Path | str) -> MediaInfo:
        info = self.probe.probe(path)
        info.require_audio()
        return info

    def normalize_audio(
        self,
        source: Path | str,
        destination: Path | str,
        spec: AudioSpec | None = None,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        spec = spec or AudioSpec()
        destination = Path(destination)
        duration = self._probe_duration(source)
        cmd = [self.runner.ffmpeg_bin] + build_normalize_audio_cmd(source, destination, spec)
        self._run(cmd, destination, duration, progress, cancel_event)
        return destination

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
        if end <= start:
            raise MediaError("Audio trim end must be greater than start.")
        spec = spec or AudioSpec()
        destination = Path(destination)
        duration = end - start
        cmd = [self.runner.ffmpeg_bin] + build_trim_audio_cmd(source, destination, spec, start, end)
        self._run(cmd, destination, duration, progress, cancel_event)
        return destination

    def mix_audio(
        self,
        voiceover: Path | str,
        destination: Path | str,
        music: Path | str | None = None,
        spec: AudioSpec | None = None,
        music_volume: float = DEFAULT_MUSIC_VOLUME,
        *,
        sfx: Path | str | None = None,
        sfx_volume: float = DEFAULT_TRANSITION_SOUND_VOLUME,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        spec = spec or AudioSpec()
        destination = Path(destination)
        duration = self._probe_duration(voiceover)
        cmd = [self.runner.ffmpeg_bin] + build_mix_audio_cmd(
            voiceover,
            music,
            destination,
            spec,
            music_volume,
            sfx=sfx,
            sfx_volume=sfx_volume,
        )
        self._run(cmd, destination, duration, progress, cancel_event)
        return destination

    def _probe_duration(self, path: Path | str) -> float | None:
        info = self.probe.probe(path)
        return info.duration

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
