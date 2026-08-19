"""Lavfi-based sample media generation for integration tests."""

from __future__ import annotations

from pathlib import Path

from autotube.media.ffmpeg_runner import FFmpegRunner


def make_sample_video(
    path: Path,
    duration: float = 2.0,
    size: str = "320x180",
    fps: int = 30,
    with_audio: bool = True,
) -> Path:
    runner = FFmpegRunner()
    audio_filter = "sine=frequency=440:sample_rate=44100"
    filter_chain = f"testsrc=size={size}:rate={fps}"
    args = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", filter_chain,
    ]
    if with_audio:
        args += ["-f", "lavfi", "-i", audio_filter]
    args += [
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
    ]
    if with_audio:
        args += ["-c:a", "aac"]
    else:
        args += ["-an"]
    args += [str(path)]
    runner.run(args)
    return path


def make_sample_audio(path: Path, duration: float = 2.0) -> Path:
    runner = FFmpegRunner()
    args = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=44100",
        "-t", f"{duration:.3f}",
        "-c:a", "aac",
        str(path),
    ]
    runner.run(args)
    return path
