"""Unit tests for timeline-aware PipelineOrchestrator with fakes."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from autotube.exceptions import MissingVisualAssetsError, ValidationError
from autotube.models import Project, RenderSettings
from autotube.services.orchestrator import PipelineOrchestrator
from autotube.state import (
    PipelineStage,
    ProjectState,
    SegmentState,
    StageStatus,
)
from autotube.timeline.composer import TimelineComposer
from autotube.timeline.types import (
    AssetType,
    TimelineState,
    TimedVisualAsset,
)


class _FakeStore:
    def __init__(self):
        self.saves = 0

    def save(self, state, path):
        self.saves += 1


class _FakeTranscriptionWorkflow:
    def run(self, state, *, force=False, cancel_event=None):
        state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED
        state.stage(PipelineStage.SEGMENTS_READY).status = StageStatus.COMPLETED
        return state


class _FakeStockWorkflow:
    def run(self, state, *, force=False, cancel_event=None):
        state.stage(PipelineStage.KEYWORDS_READY).status = StageStatus.COMPLETED
        state.stage(PipelineStage.ASSETS_READY).status = StageStatus.COMPLETED
        return state


class _FakeProcessor:
    def __init__(self):
        self.calls = 0

    def process(self, asset, spec, output_dir, *, cancel_event=None):
        self.calls += 1
        path = Path(f"processed_{self.calls}.mp4")
        asset.processed_path = path
        return path


class _FakeMedia:
    def __init__(self):
        self.calls = []

    def probe_audio(self, path):
        from types import SimpleNamespace

        return SimpleNamespace(duration=2.0)

    def probe_media(self, path):
        from types import SimpleNamespace

        return SimpleNamespace(
            streams=[
                SimpleNamespace(codec_type="video", width=640, height=360, fps=30.0),
                SimpleNamespace(codec_type="audio"),
            ],
            video_stream=lambda: SimpleNamespace(width=640, height=360, fps=30.0),
            audio_stream=lambda: SimpleNamespace(codec_type="audio"),
            duration=2.0,
        )

    def probe_video(self, path):
        from types import SimpleNamespace

        return SimpleNamespace(
            streams=[
                SimpleNamespace(codec_type="video", width=640, height=360, fps=30.0),
                SimpleNamespace(codec_type="audio"),
            ],
            video_stream=lambda: SimpleNamespace(width=640, height=360, fps=30.0),
            audio_stream=lambda: SimpleNamespace(codec_type="audio"),
            duration=2.0,
        )

    def render_captions(self, video, srt, destination, spec, *, cancel_event=None):
        self.calls.append(("render_captions", str(destination)))
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"video")
        return destination

    def black_segment(self, destination, spec, duration, *, cancel_event=None):
        self.calls.append(("black_segment", duration))
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"black")
        return destination

    def compose_video_only(self, list_file, destination, spec, *, cancel_event=None):
        self.calls.append(("compose_video_only", str(destination)))
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"video")
        return destination

    def mix_audio(self, voiceover, destination, music=None, music_volume=None, *, cancel_event=None):
        self.calls.append(("mix_audio", str(destination)))
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"audio")
        return destination

    def overlay_subtitles(self, video, ass, destination, spec, *, cancel_event=None):
        self.calls.append(("overlay_subtitles", str(destination)))
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"video")
        return destination

    def mux_video_audio(self, video, audio, destination, *, cancel_event=None):
        self.calls.append(("mux_video_audio", str(destination)))
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"final")
        return destination


def _state(tmp_path: Path, with_missing: bool = False) -> ProjectState:
    state = ProjectState(
        project=Project(name="T", voiceover_path=tmp_path / "voice.mp3"),
        render_settings=RenderSettings(resolution="640x360", fps=30),
    )
    (tmp_path / "voice.mp3").write_bytes(b"fake")
    state.timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(
                source_path=tmp_path / "a.png",
                start=0.0,
                end=1.0,
                asset_type=AssetType.IMAGE,
            )
        ]
    )
    if with_missing:
        state.timeline.visual_assets.append(
            TimedVisualAsset(start=1.0, end=2.0, asset_type=AssetType.IMAGE)
        )
    return state


def _orchestrator(tmp_path: Path, media: _FakeMedia) -> PipelineOrchestrator:
    composer = TimelineComposer(media)
    composer.processor = _FakeProcessor()
    return PipelineOrchestrator(
        transcription_workflow=_FakeTranscriptionWorkflow(),
        stock_workflow=_FakeStockWorkflow(),
        media_service=media,
        store=_FakeStore(),
        project_path=tmp_path / "project.json",
        timeline_composer=composer,
    )


def test_timeline_skips_early_stages_and_renders(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    orch = _orchestrator(tmp_path, media)

    orch.run(state)

    for stage in (
        PipelineStage.TRANSCRIBED,
        PipelineStage.SEGMENTS_READY,
        PipelineStage.KEYWORDS_READY,
        PipelineStage.ASSETS_READY,
    ):
        assert state.stage(stage).status == StageStatus.SKIPPED

    for stage in (
        PipelineStage.CLIPS_READY,
        PipelineStage.COMPOSED,
        PipelineStage.AUDIO_READY,
        PipelineStage.CAPTIONS_READY,
        PipelineStage.COMPLETED,
    ):
        assert state.stage(stage).status == StageStatus.COMPLETED

    assert state.stage(PipelineStage.COMPLETED).artifacts[-1].name == "final.mp4"
    assert state.timeline.rendered_path == str(
        state.render_settings.output_dir / "final.mp4"
    )
    assert state.timeline.rendered_fingerprint is not None
    assert any(name == "mux_video_audio" for name, _ in media.calls)


def test_no_timeline_content_falls_back_to_stock(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    state.timeline = TimelineState()

    # Stock path needs a segment/selected clip.
    state.segments = [SegmentState.new("hello", 0.0, 1.0)]
    state.segments[0].selected_clip = {"local_path": "stock.mp4"}
    state.segments[0].keywords = ["hello"]
    for stage in (
        PipelineStage.TRANSCRIBED,
        PipelineStage.SEGMENTS_READY,
        PipelineStage.KEYWORDS_READY,
        PipelineStage.ASSETS_READY,
    ):
        state.stage(stage).status = StageStatus.COMPLETED

    # Stock path uses media.process_clip; add it.
    def process_clip(asset, segment, spec, output_dir, motion=None, cancel_event=None):
        from types import SimpleNamespace

        return SimpleNamespace(path=Path(f"{segment.segment_id}.mp4"))

    media.process_clip = process_clip

    orch = _orchestrator(tmp_path, media)
    orch.run(state)

    assert state.stage(PipelineStage.CLIPS_READY).status == StageStatus.COMPLETED
    assert state.stage(PipelineStage.COMPOSED).status == StageStatus.COMPLETED


def test_validation_mode_fails_on_missing_slot(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path, with_missing=True)
    orch = _orchestrator(tmp_path, media)

    with pytest.raises(MissingVisualAssetsError):
        orch.run(state, allow_missing=False)

    assert state.stage(PipelineStage.CLIPS_READY).status == StageStatus.FAILED
    assert "MISSING VISUAL ASSETS" in state.stage(PipelineStage.CLIPS_READY).error


def test_continue_mode_renders_missing_slot(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path, with_missing=True)
    orch = _orchestrator(tmp_path, media)

    orch.run(state, allow_missing=True)

    assert state.stage(PipelineStage.CLIPS_READY).status == StageStatus.COMPLETED
    assert state.stage(PipelineStage.COMPOSED).status == StageStatus.COMPLETED
    assert state.stage(PipelineStage.COMPLETED).status == StageStatus.COMPLETED
    assert any(name == "black_segment" for name, _ in media.calls)


def test_force_preserves_timeline_content(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    orch = _orchestrator(tmp_path, media)

    orch.run(state, force=True)

    assert len(state.timeline.visual_assets) == 1
    assert state.timeline.visual_assets[0].start == 0.0
    assert state.timeline.visual_assets[0].end == 1.0


def test_cancellation_before_timeline_stage(tmp_path: Path) -> None:
    media = _FakeMedia()
    state = _state(tmp_path)
    orch = _orchestrator(tmp_path, media)
    cancel = threading.Event()
    cancel.set()

    with pytest.raises(Exception):
        orch.run(state, cancel_event=cancel)

    assert state.stage(PipelineStage.CLIPS_READY).status == StageStatus.PENDING
