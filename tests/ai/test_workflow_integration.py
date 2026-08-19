"""Tests for StockWorkflow keyword-source integration."""

from __future__ import annotations

from pathlib import Path

from autotube.ai.config import AIConfig
from autotube.ai.engine import AIKeywordEngine
from autotube.ai.models import AISegmentOutput
from autotube.config import Settings
from autotube.models import Project, RenderSettings
from autotube.state import KeywordSource, PipelineStage, ProjectState, SegmentState, StageStatus
from autotube.stock.keywords import LocalKeywordService
from autotube.stock.workflow import StockWorkflow


class _FakeManager:
    def __init__(self):
        self.calls = 0

    def resolve_segment(self, segment, filter, destination_dir, *, cancel_event=None):
        self.calls += 1
        segment.selected_clip = {"local_path": str(destination_dir / f"{segment.segment_id}.mp4")}
        segment.error = None


class _FakeProvider:
    def generate(self, segments, *, cancel_event=None):
        return [
            AISegmentOutput(s.segment_id, s.start, s.end, ["ocean", "waves"])
            for s in segments
        ]


def _state(tmp_path: Path) -> ProjectState:
    project = Project(name="Test", voiceover_path=tmp_path / "voice.mp3")
    state = ProjectState(project=project, render_settings=RenderSettings())
    state.segments = [SegmentState.new("the ocean waves", 0.0, 2.0)]
    return state


def test_local_workflow_sets_local_source(tmp_path: Path) -> None:
    state = _state(tmp_path)
    workflow = StockWorkflow(
        keyword_service=LocalKeywordService(), stock_manager=_FakeManager()
    )
    result = workflow.run(state)
    assert result.segments[0].keyword_source == KeywordSource.LOCAL
    assert result.segments[0].keywords


def test_ai_workflow_sets_ai_source(tmp_path: Path) -> None:
    state = _state(tmp_path)
    config = AIConfig.from_settings(Settings(ai_enabled=True))
    engine = AIKeywordEngine(config=config, provider=_FakeProvider())
    workflow = StockWorkflow(keyword_service=engine, stock_manager=_FakeManager())
    result = workflow.run(state)
    assert result.segments[0].keyword_source == KeywordSource.AI
    assert result.segments[0].keywords == ["ocean", "waves"]


def test_ai_failure_falls_back_local(tmp_path: Path) -> None:
    state = _state(tmp_path)
    config = AIConfig.from_settings(Settings(ai_enabled=True, ai_max_retries=0))

    class _FailingProvider:
        def generate(self, segments, *, cancel_event=None):
            raise RuntimeError("boom")

    engine = AIKeywordEngine(config=config, provider=_FailingProvider())
    workflow = StockWorkflow(keyword_service=engine, stock_manager=_FakeManager())
    result = workflow.run(state)
    assert result.segments[0].keyword_source == KeywordSource.LOCAL
    assert result.segments[0].keywords
