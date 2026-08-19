"""Tests for TimelineComposer with fakes (no FFmpeg)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from autotube.exceptions import ValidationError
from autotube.media.types import VideoSpec
from autotube.models import Project, RenderSettings
from autotube.state import PipelineStage, ProjectState, StageStatus
from autotube.timeline.composer import TimelineComposer
from autotube.timeline.types import (
    AssetType,
    SubtitleEntry,
    TimelineState,
    TimedVisualAsset,
)


class _FakeMedia:
    def __init__(self):
        self.calls = []

    def probe_audio(self, path):
        from types import SimpleNamespace

        return SimpleNamespace(duration=5.0)

    def mix_audio(self, *a, **k):
        self.calls.append("mix_audio")
        return Path("audio.m4a")

    def overlay_subtitles(self, *a, **k):
        self.calls.append("overlay_subtitles")
        return Path("burned.mp4")

    def mux_video_audio(self, *a, **k):
        self.calls.append("mux_video_audio")
        return Path("final.mp4")

    def probe_media(self, path):
        from types import SimpleNamespace

        return SimpleNamespace(
            streams=[
                SimpleNamespace(codec_type="video", width=640, height=360, fps=30.0),
                SimpleNamespace(codec_type="audio"),
            ],
            video_stream=lambda: SimpleNamespace(width=640, height=360, fps=30.0),
            duration=5.0,
        )

    def black_segment(self, *a, **k):
        self.calls.append("black_segment")
        return Path("black.mp4")

    def compose_video_only(self, *a, **k):
        self.calls.append("compose_video_only")
        return Path("base.mp4")


class _FakeProcessor:
    def process(self, asset, spec, output_dir, *, cancel_event=None):
        asset.processed_path = Path("processed.mp4")
        return Path("processed.mp4")


def _state(tmp_path: Path) -> ProjectState:
    project = Project(name="T", voiceover_path=tmp_path / "voice.mp3")
    (tmp_path / "voice.mp3").write_bytes(b"fake")
    state = ProjectState(
        project=project, render_settings=RenderSettings(resolution="640x360", fps=30)
    )
    state.timeline = TimelineState()
    return state


def _composer(media) -> TimelineComposer:
    composer = TimelineComposer(media)
    composer.processor = _FakeProcessor()
    return composer


def test_compose_orders_assets_and_fills_gaps(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(Path("a.mp4"), 0.0, 1.0, AssetType.VIDEO),
        TimedVisualAsset(Path("b.mp4"), 2.0, 3.0, AssetType.VIDEO),
    ]
    state.timeline.subtitles = [
        SubtitleEntry(index=1, start=0.0, end=1.0, text="A", animation_preset="fade_in")
    ]

    result = _composer(media).compose(state, tmp_path / "out")

    assert result == Path("final.mp4")
    assert "black_segment" in media.calls
    assert "compose_video_only" in media.calls
    assert "mix_audio" in media.calls
    assert "overlay_subtitles" in media.calls
    assert state.timeline.rendered_path == str(result)


def test_missing_asset_fails(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(Path("missing.mp4"), 0.0, 1.0, AssetType.VIDEO)
    ]

    composer = _composer(media)

    # Override processor to raise for missing file.
    class _Missing:
        def process(self, asset, spec, output_dir, *, cancel_event=None):
            raise ValidationError("missing file")

    composer.processor = _Missing()

    with pytest.raises(ValidationError):
        composer.compose(state, tmp_path / "out")
    assert state.timeline.rendered_path is None


def test_overlap_blocks_render(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(Path("a.mp4"), 0.0, 2.0, AssetType.VIDEO),
        TimedVisualAsset(Path("b.mp4"), 1.0, 3.0, AssetType.VIDEO),
    ]

    with pytest.raises(ValidationError):
        _composer(media).compose(state, tmp_path / "out")


def test_cancellation(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(Path("a.mp4"), 0.0, 1.0, AssetType.VIDEO)
    ]
    cancel = threading.Event()
    cancel.set()

    with pytest.raises(ValidationError):
        _composer(media).compose(state, tmp_path / "out", cancel_event=cancel)
