"""Tests for the transcription workflow resume behavior."""

from __future__ import annotations

from pathlib import Path

from autotube.models import Project, RenderSettings
from autotube.state import (
    PipelineStage,
    ProjectState,
    SegmentState,
    StageStatus,
    TranscriptionInfo,
)
from autotube.transcription.workflow import TranscriptionWorkflow


class _FakeService:
    def __init__(self, segments):
        self.segments = segments
        self.calls = 0

    def transcribe_with_config(self, *args, **kwargs):
        self.calls += 1
        from autotube.transcription.service import TranscriptionResult

        return TranscriptionResult(
            segments=self.segments,
            language="en",
            language_probability=0.9,
            duration=2.0,
            model="base",
            device="cpu",
            compute_type="int8",
        )


def _state(tmp_path: Path) -> ProjectState:
    project = Project(name="Test", voiceover_path=tmp_path / "voice.mp3")
    (tmp_path / "voice.mp3").write_bytes(b"fake")
    return ProjectState(project=project, render_settings=RenderSettings())


def test_runs_transcription_and_segmentation(tmp_path: Path) -> None:
    service = _FakeService([SegmentState.new("hello world", 0.0, 2.0)])
    workflow = TranscriptionWorkflow(service=service)
    state = _state(tmp_path)
    result = workflow.run(state)
    assert service.calls == 1
    assert result.stage(PipelineStage.TRANSCRIBED).status == StageStatus.COMPLETED
    assert result.stage(PipelineStage.SEGMENTS_READY).status == StageStatus.COMPLETED
    assert result.transcription is not None
    assert result.segments


def test_skips_completed_stages(tmp_path: Path) -> None:
    service = _FakeService([SegmentState.new("hello", 0.0, 2.0)])
    workflow = TranscriptionWorkflow(service=service)
    state = _state(tmp_path)
    state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED
    state.stage(PipelineStage.SEGMENTS_READY).status = StageStatus.COMPLETED
    state.segments = [SegmentState.new("hello", 0.0, 2.0)]
    result = workflow.run(state)
    assert service.calls == 0


def test_force_reruns_both(tmp_path: Path) -> None:
    service = _FakeService([SegmentState.new("hello", 0.0, 2.0)])
    workflow = TranscriptionWorkflow(service=service)
    state = _state(tmp_path)
    state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED
    state.stage(PipelineStage.SEGMENTS_READY).status = StageStatus.COMPLETED
    state.segments = [SegmentState.new("hello", 0.0, 2.0)]
    workflow.run(state, force=True)
    assert service.calls == 1


def test_failed_segmentation_reruns_only_segments(tmp_path: Path) -> None:
    service = _FakeService([SegmentState.new("hello", 0.0, 2.0)])
    workflow = TranscriptionWorkflow(service=service)
    state = _state(tmp_path)
    state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED
    state.stage(PipelineStage.SEGMENTS_READY).status = StageStatus.FAILED
    state.segments = [SegmentState.new("hello", 0.0, 2.0)]
    state.transcription = TranscriptionInfo(language="en", duration=2.0)
    workflow.run(state)
    assert service.calls == 0
    assert state.stage(PipelineStage.SEGMENTS_READY).status == StageStatus.COMPLETED
