"""Tests for timeline media command construction and decisions."""

from __future__ import annotations

from pathlib import Path

from autotube.media.commands import build_image_duration_cmd
from autotube.media.types import VideoSpec
from autotube.timeline.media import TimelineMediaProcessor
from autotube.timeline.types import AssetType, TimedVisualAsset


def test_image_duration_command() -> None:
    spec = VideoSpec(width=640, height=360, fps=30)
    cmd = build_image_duration_cmd("img.png", "out.mp4", spec, 2.0)
    assert "-loop" in cmd
    assert "1" in cmd
    assert "-t" in cmd
    assert "2.000" in cmd
    assert "-an" in cmd


def test_video_longer_trims(tmp_path) -> None:
    class _Media:
        def probe_video(self, path):
            from types import SimpleNamespace

            return SimpleNamespace(duration=5.0)

        def trim_video(self, *a, **k):
            return Path("trimmed.mp4")

        def loop_video(self, *a, **k):
            return Path("looped.mp4")

    processor = TimelineMediaProcessor(_Media())
    asset = TimedVisualAsset(
        source_path=Path("clip.mp4"), start=0.0, end=2.0, asset_type=AssetType.VIDEO
    )
    result = processor.process(asset, VideoSpec(640, 360, 30), tmp_path)
    assert result.name == "trimmed.mp4"


def test_video_shorter_loops(tmp_path) -> None:
    class _Media:
        def probe_video(self, path):
            from types import SimpleNamespace

            return SimpleNamespace(duration=1.0)

        def trim_video(self, *a, **k):
            return Path("trimmed.mp4")

        def loop_video(self, *a, **k):
            return Path("looped.mp4")

    processor = TimelineMediaProcessor(_Media())
    asset = TimedVisualAsset(
        source_path=Path("clip.mp4"), start=0.0, end=3.0, asset_type=AssetType.VIDEO
    )
    result = processor.process(asset, VideoSpec(640, 360, 30), tmp_path)
    assert result.name == "looped.mp4"
