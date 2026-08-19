"""Tests for the resumable state machine."""

from __future__ import annotations

import pytest

from autotube.state import (
    PipelineStage,
    ProjectState,
    SegmentState,
    StageStatus,
    STAGE_ORDER,
)


def test_stage_order_maps_master_workflow() -> None:
    assert [s.value for s in STAGE_ORDER] == [
        "transcribed",
        "segments_ready",
        "keywords_ready",
        "assets_ready",
        "clips_ready",
        "composed",
        "audio_ready",
        "captions_ready",
        "completed",
    ]


def test_new_state_has_all_stages_pending() -> None:
    state = ProjectState()
    assert list(state.stages.keys()) == list(STAGE_ORDER)
    assert all(s.status == StageStatus.PENDING for s in state.stages.values())


def test_next_pending_stage_is_first() -> None:
    state = ProjectState()
    assert state.next_pending_stage() == PipelineStage.TRANSCRIBED


def test_completed_stages_are_skipped() -> None:
    state = ProjectState()
    state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED
    assert state.next_pending_stage() == PipelineStage.SEGMENTS_READY


def test_failed_stage_is_resumable() -> None:
    state = ProjectState()
    state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED
    state.stage(PipelineStage.SEGMENTS_READY).status = StageStatus.FAILED
    assert state.next_pending_stage() == PipelineStage.SEGMENTS_READY


def test_force_restarts_completed() -> None:
    state = ProjectState()
    state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED
    assert state.next_pending_stage(force=True) == PipelineStage.TRANSCRIBED


def test_state_roundtrip_preserves_segments_and_errors() -> None:
    state = ProjectState()
    state.segments.append(SegmentState.new("Hello world", start=0.0, end=1.5))
    state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED
    state.stage(PipelineStage.SEGMENTS_READY).status = StageStatus.FAILED
    state.stage(PipelineStage.SEGMENTS_READY).error = "boom"
    state.last_error = "boom"

    restored = ProjectState.from_dict(state.to_dict())
    assert restored.project_id == state.project_id
    assert restored.segments == state.segments
    assert restored.stage(PipelineStage.SEGMENTS_READY).error == "boom"
    assert restored.last_error == "boom"


def test_is_complete() -> None:
    state = ProjectState()
    for stage in STAGE_ORDER:
        state.stage(stage).status = StageStatus.COMPLETED
    assert state.is_complete()
