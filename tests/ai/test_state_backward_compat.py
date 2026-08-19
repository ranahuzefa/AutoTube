"""Tests for backward-compatible SegmentState keyword source."""

from __future__ import annotations

from autotube.state import KeywordSource, ProjectState, SegmentState


def test_missing_keyword_source_defaults_local() -> None:
    data = SegmentState.new("hello", 0.0, 1.0).to_dict()
    data.pop("keyword_source")
    restored = SegmentState.from_dict(data)
    assert restored.keyword_source == KeywordSource.LOCAL


def test_project_roundtrip_with_ai_source() -> None:
    state = ProjectState()
    seg = SegmentState.new("ocean", 0.0, 1.0)
    seg.keywords = ["ocean"]
    seg.keyword_source = KeywordSource.AI
    state.segments = [seg]
    restored = ProjectState.from_dict(state.to_dict())
    assert restored.segments[0].keyword_source == KeywordSource.AI


def test_old_shape_segment_loads() -> None:
    data = {
        "segment_id": "fixed",
        "text": "hello",
        "start": 0.0,
        "end": 1.0,
        "keywords": [],
        "selected_clip": None,
        "status": "pending",
        "error": None,
        "words": [],
    }
    restored = SegmentState.from_dict(data)
    assert restored.keyword_source == KeywordSource.LOCAL
