"""Unit tests for PipelineOrchestrator with injected fakes."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from autotube.exceptions import AutoTubeError, ValidationError
from autotube.models import Project, RenderSettings
from autotube.services.orchestrator import PipelineOrchestrator
from autotube.state import (
    PipelineStage,
    ProjectState,
    SegmentState,
    SegmentStatus,
    StageStatus,
    STAGE_ORDER,
)
from autotube.storage import ProjectStore


class _FakeStore:
    def __init__(self):
        self.saves = 0

    def save(self, state, path):
        self.saves += 1


class _FakeTranscriptionWorkflow:
    def __init__(self):
        self.calls = 0

    def run(self, state, *, force=False, cancel_event=None):
        self.calls += 1
        state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED
        state.stage(PipelineStage.SEGMENTS_READY).status = StageStatus.COMPLETED
        if not state.segments:
            state.segments = [SegmentState.new("hello", 0.0, 1.0)]
        return state


class _FakeStockWorkflow:
    def __init__(self):
        self.calls = 0

    def run(self, state, *, force=False, cancel_event=None):
        self.calls += 1
        state.stage(PipelineStage.KEYWORDS_READY).status = StageStatus.COMPLETED
        state.stage(PipelineStage.ASSETS_READY).status = StageStatus.COMPLETED
        for seg in state.segments:
            seg.keywords = ["hello"]
            seg.selected_clip = {"local_path": "stock.mp4"}
        return state


class _FakeMedia:
    def __init__(self):
        self.calls = []

    def process_clip(self, asset, segment, spec, output_dir, motion=None, cancel_event=None):
        self.calls.append(("process_clip", str(asset)))
        from types import SimpleNamespace

        return SimpleNamespace(path=Path(f"{segment.segment_id}.mp4"))

    def compose_video_only(self, list_file, destination, spec, cancel_event=None):
        self.calls.append(("compose_video_only", str(list_file)))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"video")
        return destination

    def mix_audio(self, voiceover, destination, music=None, music_volume=None, cancel_event=None):
        self.calls.append(("mix_audio", str(voiceover)))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"audio")
        return destination

    def render_captions(self, video, srt, destination, spec, cancel_event=None):
        self.calls.append(("render_captions", str(video)))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"video")
        return destination

    def mux_video_audio(self, video, audio, destination, cancel_event=None):
        self.calls.append(("mux_video_audio", str(video)))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"final")
        return destination

    def probe_video(self, path):
        from autotube.media.types import MediaInfo, StreamInfo

        return MediaInfo(
            path=Path(path),
            duration=2.0,
            streams=[
                StreamInfo(index=0, codec_type="video", width=1920, height=1080, fps=30.0),
                StreamInfo(index=1, codec_type="audio"),
            ],
        )


def _state(tmp_path: Path) -> ProjectState:
    project = Project(name="Test", voiceover_path=tmp_path / "voice.mp3")
    (tmp_path / "voice.mp3").write_bytes(b"fake")
    state = ProjectState(project=project, render_settings=RenderSettings())
    state.segments = [
        SegmentState.new("hello", 0.0, 1.0),
    ]
    for seg in state.segments:
        seg.selected_clip = {"local_path": "stock.mp4"}
        seg.keywords = ["hello"]
    for stage in (
        PipelineStage.TRANSCRIBED,
        PipelineStage.SEGMENTS_READY,
        PipelineStage.KEYWORDS_READY,
        PipelineStage.ASSETS_READY,
    ):
        state.stage(stage).status = StageStatus.COMPLETED
    return state


def _orchestrator(tmp_path: Path, fake_media, fake_store):
    return PipelineOrchestrator(
        transcription_workflow=_FakeTranscriptionWorkflow(),
        stock_workflow=_FakeStockWorkflow(),
        media_service=fake_media,
        store=fake_store,
        project_path=tmp_path / "project.json",
    )


def test_runs_stages_in_order(tmp_path: Path) -> None:
    media = _FakeMedia()
    store = _FakeStore()
    orch = _orchestrator(tmp_path, media, store)
    state = _state(tmp_path)

    orch.run(state)

    for stage in STAGE_ORDER:
        assert state.stage(stage).status == StageStatus.COMPLETED

    names = [c[0] for c in media.calls]
    assert names == [
        "process_clip",
        "compose_video_only",
        "mix_audio",
        "render_captions",
        "mux_video_audio",
    ]
    assert store.saves == 5


def test_skips_completed_stages(tmp_path: Path) -> None:
    media = _FakeMedia()
    store = _FakeStore()
    orch = _orchestrator(tmp_path, media, store)
    state = _state(tmp_path)
    for stage in STAGE_ORDER:
        state.stage(stage).status = StageStatus.COMPLETED

    orch.run(state)
    assert media.calls == []
    assert store.saves == 0


def test_force_resets_and_reruns(tmp_path: Path) -> None:
    media = _FakeMedia()
    store = _FakeStore()
    orch = _orchestrator(tmp_path, media, store)
    state = _state(tmp_path)
    for stage in STAGE_ORDER:
        state.stage(stage).status = StageStatus.COMPLETED

    orch.run(state, force=True)
    assert media.calls
    assert store.saves == 7
    assert state.segments[0].selected_clip["processed_path"]


def test_cancellation_before_stage_stops(tmp_path: Path) -> None:
    media = _FakeMedia()
    store = _FakeStore()
    orch = _orchestrator(tmp_path, media, store)
    state = _state(tmp_path)
    cancel = threading.Event()
    cancel.set()

    with pytest.raises(AutoTubeError):
        orch.run(state, cancel_event=cancel)

    # No stage should be saved as running/completed for CLIPS_READY onward.
    assert state.stage(PipelineStage.CLIPS_READY).status == StageStatus.PENDING
    assert media.calls == []
    assert store.saves == 0


def test_missing_local_path_fails_clips(tmp_path: Path) -> None:
    media = _FakeMedia()
    store = _FakeStore()
    orch = _orchestrator(tmp_path, media, store)
    state = _state(tmp_path)
    state.segments[0].selected_clip = {}

    with pytest.raises(ValidationError):
        orch.run(state)

    assert state.stage(PipelineStage.CLIPS_READY).status == StageStatus.FAILED


def test_failure_saves_and_stops(tmp_path: Path) -> None:
    class _FailingMedia(_FakeMedia):
        def process_clip(self, *a, **k):
            raise ValidationError("boom")

    media = _FailingMedia()
    store = _FakeStore()
    orch = _orchestrator(tmp_path, media, store)
    state = _state(tmp_path)

    with pytest.raises(ValidationError):
        orch.run(state)

    assert state.stage(PipelineStage.CLIPS_READY).status == StageStatus.FAILED
    assert state.stage(PipelineStage.COMPOSED).status == StageStatus.PENDING
    assert store.saves == 1


def test_segment_processed_path_persisted(tmp_path: Path) -> None:
    media = _FakeMedia()
    store = _FakeStore()
    orch = _orchestrator(tmp_path, media, store)
    state = _state(tmp_path)
    orch.run(state)
    seg = state.segments[0]
    assert seg.selected_clip["processed_path"]
    assert seg.status == SegmentStatus.PROCESSED
