"""Real-FFmpeg timeline media integration tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from autotube.media.service import FFmpegMediaService
from autotube.media.types import VideoSpec
from autotube.timeline.media import TimelineMediaProcessor
from autotube.timeline.types import AssetType, TimedVisualAsset

pytestmark = pytest.mark.integration


@pytest.fixture
def enabled() -> bool:
    return os.environ.get("AUTOTUBE_RUN_TIMELINE_TESTS") == "1"


@pytest.fixture
def require_media(enabled: bool):
    if not enabled:
        pytest.skip("AUTOTUBE_RUN_TIMELINE_TESTS not set")


def _make_image(path: Path) -> None:
    FFmpegMediaService().runner.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=red:s=640x360",
            "-frames:v", "1",
            str(path),
        ]
    )


def _make_video(path: Path, duration: float) -> None:
    FFmpegMediaService().runner.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
            "-t", f"{duration:.2f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(path),
        ]
    )


def test_image_exact_duration(tmp_path: Path, require_media) -> None:
    image = tmp_path / "img.png"
    _make_image(image)
    processor = TimelineMediaProcessor(FFmpegMediaService())
    asset = TimedVisualAsset(
        source_path=image, start=0.0, end=2.0, asset_type=AssetType.IMAGE
    )
    out = processor.process(asset, VideoSpec(640, 360, 30), tmp_path / "out")
    info = FFmpegMediaService().probe_media(out)
    assert info.video_stream() is not None
    assert info.audio_stream() is None
    assert info.duration is not None
    assert abs(info.duration - 2.0) < 0.3


def test_video_trim_exact_duration(tmp_path: Path, require_media) -> None:
    video = tmp_path / "long.mp4"
    _make_video(video, 5.0)
    processor = TimelineMediaProcessor(FFmpegMediaService())
    asset = TimedVisualAsset(
        source_path=video, start=0.0, end=2.0, asset_type=AssetType.VIDEO
    )
    out = processor.process(asset, VideoSpec(640, 360, 30), tmp_path / "out")
    info = FFmpegMediaService().probe_media(out)
    assert abs(info.duration - 2.0) < 0.3


def test_video_loop_exact_duration(tmp_path: Path, require_media) -> None:
    video = tmp_path / "short.mp4"
    _make_video(video, 1.0)
    processor = TimelineMediaProcessor(FFmpegMediaService())
    asset = TimedVisualAsset(
        source_path=video, start=0.0, end=3.0, asset_type=AssetType.VIDEO
    )
    out = processor.process(asset, VideoSpec(640, 360, 30), tmp_path / "out")
    info = FFmpegMediaService().probe_media(out)
    assert abs(info.duration - 3.0) < 0.3
    assert info.audio_stream() is None
