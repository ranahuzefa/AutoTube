"""Unit tests for TimelineComposer pipeline-oriented methods."""

from __future__ import annotations

from pathlib import Path

import pytest

from autotube.exceptions import ValidationError
from autotube.models import Project, RenderSettings
from autotube.state import ProjectState
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

        return SimpleNamespace(duration=3.0)

    def probe_media(self, path):
        from types import SimpleNamespace

        return SimpleNamespace(
            streams=[
                SimpleNamespace(codec_type="video", width=640, height=360, fps=30.0),
                SimpleNamespace(codec_type="audio"),
            ],
            video_stream=lambda: SimpleNamespace(width=640, height=360, fps=30.0),
            duration=3.0,
        )

    def mix_audio(self, *a, **k):
        self.calls.append("mix_audio")
        return Path("final_audio.m4a")

    def overlay_subtitles(self, *a, **k):
        self.calls.append("overlay_subtitles")
        return Path("burned.mp4")

    def mux_video_audio(self, *a, **k):
        self.calls.append("mux_video_audio")
        return Path("final.mp4")

    def black_segment(self, destination, spec, duration, *, cancel_event=None):
        self.calls.append(("black_segment", duration))
        return Path(destination)

    def compose_video_only(self, *a, **k):
        self.calls.append("compose_video_only")
        return Path("base.mp4")


class _FakeProcessor:
    def process(self, asset, spec, output_dir, *, cancel_event=None):
        asset.processed_path = Path(f"processed_{asset.start}.mp4")
        return asset.processed_path


def _state(tmp_path: Path) -> ProjectState:
    state = ProjectState(
        project=Project(name="T", voiceover_path=tmp_path / "voice.mp3"),
        render_settings=RenderSettings(resolution="640x360", fps=30),
    )
    state.timeline = TimelineState()
    return state


def _composer(media: _FakeMedia) -> TimelineComposer:
    composer = TimelineComposer(media)
    composer.processor = _FakeProcessor()
    return composer


def test_pipeline_no_subtitles_no_overlay(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(
            source_path=Path("a.png"), start=0.0, end=1.0, asset_type=AssetType.IMAGE
        )
    ]

    _composer(media).compose_timeline_pipeline(state, tmp_path / "out")

    assert "overlay_subtitles" not in media.calls
    assert "mix_audio" in media.calls
    assert "mux_video_audio" in media.calls


def test_pipeline_with_subtitles_burns(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(
            source_path=Path("a.png"), start=0.0, end=2.0, asset_type=AssetType.IMAGE
        )
    ]
    state.timeline.subtitles = [
        SubtitleEntry(index=1, start=0.0, end=2.0, text="Hello")
    ]

    _composer(media).compose_timeline_pipeline(state, tmp_path / "out")

    assert "overlay_subtitles" in media.calls
    assert (tmp_path / "out" / "timeline.ass").exists()


def test_pipeline_sets_rendered_metadata(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(
            source_path=Path("a.png"), start=0.0, end=1.0, asset_type=AssetType.IMAGE
        )
    ]

    result = _composer(media).compose_timeline_pipeline(state, tmp_path / "out")

    assert result == Path("final.mp4")
    assert state.timeline.rendered_path == "final.mp4"
    assert state.timeline.rendered_fingerprint is not None
    assert state.timeline.rendered_at is not None


def test_pipeline_visual_asset_processed(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    asset = TimedVisualAsset(
        source_path=Path("a.png"), start=0.0, end=1.0, asset_type=AssetType.IMAGE
    )
    state.timeline.visual_assets = [asset]

    _composer(media).compose_timeline_pipeline(state, tmp_path / "out")

    assert asset.processed_path == Path("processed_0.0.mp4")
    assert asset.status.value == "ready"


def test_pipeline_missing_slot_black_segment(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(
            source_path=Path("a.png"), start=0.0, end=1.0, asset_type=AssetType.IMAGE
        ),
        TimedVisualAsset(start=1.0, end=2.0, asset_type=AssetType.IMAGE),
    ]

    _composer(media).compose_timeline_pipeline(
        state, tmp_path / "out", allow_missing=True
    )

    assert ("black_segment", 1.0) in media.calls


def test_legacy_compose_validation_mode(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(start=0.0, end=1.0, asset_type=AssetType.IMAGE)
    ]

    with pytest.raises(ValidationError):
        _composer(media).compose(state, tmp_path / "out")
