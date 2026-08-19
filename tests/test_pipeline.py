"""Tests for the state-aware pipeline orchestrator."""

from __future__ import annotations

from autotube.services import Pipeline
from autotube.state import PipelineStage, ProjectState, StageStatus


def test_empty_registry_marks_stage_failed_not_completed() -> None:
    state = ProjectState()
    Pipeline().run(state)
    assert state.stage(PipelineStage.TRANSCRIBED).status == StageStatus.FAILED
    assert state.stage(PipelineStage.TRANSCRIBED).error == (
        "Service not available for stage 'transcribed'."
    )
    assert state.last_error is not None


def test_completed_stage_is_skipped() -> None:
    state = ProjectState()
    state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED

    Pipeline().run(state)
    # Still completed, next pending stage becomes the unavailable failed stage.
    assert state.stage(PipelineStage.TRANSCRIBED).status == StageStatus.COMPLETED
    assert state.stage(PipelineStage.SEGMENTS_READY).status == StageStatus.FAILED


def test_force_reruns_completed_stage() -> None:
    state = ProjectState()
    state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED

    Pipeline().run(state, force=True)
    assert state.stage(PipelineStage.TRANSCRIBED).status == StageStatus.FAILED


def test_registered_runner_completes_and_records_artifacts() -> None:
    def runner(state: ProjectState):
        return ["clip1.mp4", "clip2.mp4"]

    pipeline = Pipeline()
    pipeline.register(PipelineStage.TRANSCRIBED, runner)

    state = ProjectState()
    pipeline.run(state)

    assert state.stage(PipelineStage.TRANSCRIBED).status == StageStatus.COMPLETED
    assert state.stage(PipelineStage.TRANSCRIBED).artifacts[-2:] == [
        __import__("pathlib").Path("clip1.mp4"),
        __import__("pathlib").Path("clip2.mp4"),
    ]
