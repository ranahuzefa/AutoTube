"""Tests for AI dataclasses."""

from __future__ import annotations

from autotube.ai.models import AISegmentInput, AISegmentOutput, BatchKeywordResult
from autotube.state import KeywordSource


def test_input_model() -> None:
    item = AISegmentInput("a", "current", 0.0, 1.0, previous_text="prev", next_text="next")
    assert item.segment_id == "a"
    assert item.previous_text == "prev"
    assert item.next_text == "next"


def test_output_model() -> None:
    item = AISegmentOutput("a", 0.0, 1.0, ["ocean", "waves"])
    assert item.keywords == ["ocean", "waves"]


def test_batch_result_model() -> None:
    result = BatchKeywordResult("a", ["ocean"], KeywordSource.AI)
    assert result.source == KeywordSource.AI
