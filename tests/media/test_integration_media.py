"""Real FFmpeg/FFprobe integration tests.

Skipped automatically when FFmpeg/FFprobe are not available.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from autotube.exceptions import MediaCancelledError, MediaCommandError
from autotube.media.captions import write_srt
from autotube.media.ffmpeg_runner import FFmpegRunner
from autotube.media.service import FFmpegMediaService
from autotube.media.types import AudioSpec, MotionEffect, VideoSpec

from media_fixtures import make_sample_audio, make_sample_video

pytestmark = pytest.mark.integration


@pytest.fixture
def spec() -> VideoSpec:
    return VideoSpec(width=640, height=360, fps=30)


@pytest.fixture
def service(require_media) -> FFmpegMediaService:
    return FFmpegMediaService()


def test_probe_generated_video(service: FFmpegMediaService, tmp_path: Path) -> None:
    src = make_sample_video(tmp_path / "src.mp4", duration=2.0, size="320x180", fps=30)
    info = service.probe_video(src)
    stream = info.video_stream()
    assert stream is not None
    assert stream.width == 320
    assert stream.height == 180
    assert info.duration is not None and info.duration > 0


def test_normalize_video_video_only(service: FFmpegMediaService, spec: VideoSpec, tmp_path: Path) -> None:
    src = make_sample_video(tmp_path / "src.mp4", duration=1.0, size="320x180", fps=30)
    dst = service.normalize_video(src, tmp_path / "norm.mp4", spec)
    info = service.probe_media(dst)
    video = info.video_stream()
    assert video is not None
    assert video.width == 640
    assert video.height == 360
    assert video.pix_fmt == "yuv420p"
    assert info.audio_stream() is None


def test_trim_video_exact_duration_video_only(service: FFmpegMediaService, spec: VideoSpec, tmp_path: Path) -> None:
    src = make_sample_video(tmp_path / "src.mp4", duration=3.0, size="320x180", fps=30)
    dst = service.trim_video(src, tmp_path / "trim.mp4", spec, start=0.0, end=1.5)
    info = service.probe_media(dst)
    assert info.duration is not None
    assert abs(info.duration - 1.5) < 0.2
    assert info.audio_stream() is None


def test_loop_video_exact_duration_video_only(service: FFmpegMediaService, spec: VideoSpec, tmp_path: Path) -> None:
    src = make_sample_video(tmp_path / "src.mp4", duration=1.0, size="320x180", fps=30)
    dst = service.loop_video(src, tmp_path / "loop.mp4", spec, duration=2.5)
    info = service.probe_media(dst)
    assert info.duration is not None
    assert abs(info.duration - 2.5) < 0.3
    assert info.audio_stream() is None


def test_process_clip_is_video_only(service: FFmpegMediaService, spec: VideoSpec, tmp_path: Path) -> None:
    src = make_sample_video(tmp_path / "src.mp4", duration=1.0, size="320x180", fps=30)
    segment = SimpleNamespace(segment_id="seg1", start=0.0, end=2.0)
    clip = service.process_clip(src, segment, spec, tmp_path / "out")
    info = service.probe_media(clip.path)
    assert info.video_stream() is not None
    assert info.audio_stream() is None


def test_mix_audio(service: FFmpegMediaService, tmp_path: Path) -> None:
    vo = make_sample_audio(tmp_path / "vo.m4a", duration=2.0)
    bg = make_sample_audio(tmp_path / "bg.m4a", duration=2.0)
    dst = service.mix_audio(vo, tmp_path / "mix.m4a", music=bg, music_volume=0.25)
    info = service.probe_audio(dst)
    assert info.audio_stream() is not None
    assert info.audio_stream().codec_name == "aac"


def test_burn_captions(service: FFmpegMediaService, spec: VideoSpec, tmp_path: Path) -> None:
    src = make_sample_video(tmp_path / "src.mp4", duration=1.5, size="320x180", fps=30)
    srt = write_srt(
        [SimpleNamespace(start=0.0, end=1.0, text="Hello")],
        tmp_path / "captions.srt",
    )
    dst = service.render_captions(src, srt, tmp_path / "captioned.mp4", spec)
    info = service.probe_media(dst)
    assert info.video_stream() is not None
    assert info.audio_stream() is None


def test_compose_clips_with_final_audio(service: FFmpegMediaService, spec: VideoSpec, tmp_path: Path) -> None:
    clip1 = service.normalize_video(
        make_sample_video(tmp_path / "c1.mp4", duration=1.0, size="320x180", fps=30),
        tmp_path / "n1.mp4",
        spec,
    )
    clip2 = service.normalize_video(
        make_sample_video(tmp_path / "c2.mp4", duration=1.0, size="320x180", fps=30),
        tmp_path / "n2.mp4",
        spec,
    )
    list_file = tmp_path / "clips.txt"
    list_file.write_text(f"file '{clip1}'\nfile '{clip2}'\n", encoding="utf-8")

    audio = service.mix_audio(make_sample_audio(tmp_path / "vo.m4a", duration=2.0), tmp_path / "final.m4a")

    dst = service.compose(list_file, audio, tmp_path / "final.mp4", spec)
    info = service.probe_media(dst)
    assert info.video_stream() is not None
    assert info.audio_stream() is not None
    assert len([s for s in info.streams if s.codec_type == "audio"]) == 1


def test_motion_effect_preserves_fps_and_duration(service: FFmpegMediaService, spec: VideoSpec, tmp_path: Path) -> None:
    src = make_sample_video(tmp_path / "src.mp4", duration=1.0, size="320x180", fps=30)
    segment = SimpleNamespace(segment_id="seg1", start=0.0, end=1.0)
    clip = service.process_clip(src, segment, spec, tmp_path / "out", motion=MotionEffect.ZOOM_IN)
    info = service.probe_media(clip.path)
    video = info.video_stream()
    assert video is not None
    assert abs(video.fps - 30) < 1.0
    assert info.duration is not None
    assert abs(info.duration - 1.0) < 0.2


def test_cancellation_cleanup(service: FFmpegMediaService, spec: VideoSpec, tmp_path: Path) -> None:
    src = make_sample_video(tmp_path / "src.mp4", duration=3.0, size="640x360", fps=30)
    dst = tmp_path / "cancel.mp4"
    cancel = threading.Event()

    def _cancel_later() -> None:
        time.sleep(0.2)
        cancel.set()

    threading.Thread(target=_cancel_later, daemon=True).start()
    with pytest.raises(MediaCancelledError):
        service.normalize_video(src, dst, spec, cancel_event=cancel)

    assert not dst.exists()
    assert list(tmp_path.glob("*.partial*")) == []


def test_timeout_raises(service: FFmpegMediaService, spec: VideoSpec, tmp_path: Path) -> None:
    src = make_sample_video(tmp_path / "src.mp4", duration=2.0, size="320x180", fps=30)
    runner = service.runner
    from autotube.media.commands import build_normalize_video_cmd

    cmd = [runner.ffmpeg_bin] + build_normalize_video_cmd(src, tmp_path / "x.mp4", spec)
    with pytest.raises(MediaCommandError):
        runner.run(cmd, timeout=0.001)
