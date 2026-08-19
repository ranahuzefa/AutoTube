"""Tests for StockWorkflow state transitions."""

from __future__ import annotations

from pathlib import Path

from autotube.models import Project, RenderSettings
from autotube.state import PipelineStage, ProjectState, SegmentState, StageStatus
from autotube.stock.keywords import LocalKeywordService
from autotube.stock.workflow import StockWorkflow


class _FakeManager:
    def __init__(self):
        self.calls = 0

    def resolve_segment(self, segment, filter, destination_dir, *, cancel_event=None):
        self.calls += 1
        segment.selected_clip = {"local_path": str(destination_dir / f"{segment.segment_id}.mp4")}
        segment.error = None


def _state(tmp_path: Path) -> ProjectState:
    project = Project(name="Test", voiceover_path=tmp_path / "voice.mp3")
    return ProjectState(project=project, render_settings=RenderSettings())


def test_runs_keywords_and_assets(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.segments = [SegmentState.new("the ocean waves", 0.0, 2.0)]
    workflow = StockWorkflow(
        keyword_service=LocalKeywordService(),
        stock_manager=_FakeManager(),
    )
    result = workflow.run(state)
    assert result.stage(PipelineStage.KEYWORDS_READY).status == StageStatus.COMPLETED
    assert result.stage(PipelineStage.ASSETS_READY).status == StageStatus.COMPLETED
    assert result.segments[0].keywords
    assert result.segments[0].selected_clip is not None


def test_skips_completed(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.segments = [SegmentState.new("ocean", 0.0, 1.0)]
    state.stage(PipelineStage.KEYWORDS_READY).status = StageStatus.COMPLETED
    state.stage(PipelineStage.ASSETS_READY).status = StageStatus.COMPLETED
    manager = _FakeManager()
    workflow = StockWorkflow(keyword_service=LocalKeywordService(), stock_manager=manager)
    workflow.run(state)
    assert manager.calls == 0


def test_force_reruns(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.segments = [SegmentState.new("ocean", 0.0, 1.0)]
    state.stage(PipelineStage.KEYWORDS_READY).status = StageStatus.COMPLETED
    state.stage(PipelineStage.ASSETS_READY).status = StageStatus.COMPLETED
    manager = _FakeManager()
    workflow = StockWorkflow(keyword_service=LocalKeywordService(), stock_manager=manager)
    workflow.run(state, force=True)
    assert manager.calls == 1
