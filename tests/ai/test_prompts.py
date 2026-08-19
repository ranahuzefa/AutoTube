"""Tests for AI prompt construction."""

from __future__ import annotations

import json

from autotube.ai.models import AISegmentInput
from autotube.ai.prompts import (
    SYSTEM_PROMPT,
    build_ai_inputs,
    build_messages,
    build_user_prompt,
)
from autotube.state import SegmentState


def test_system_prompt_mentions_stock_sites_and_schema() -> None:
    assert "Pexels" in SYSTEM_PROMPT
    assert "Pixabay" in SYSTEM_PROMPT
    assert "segments" in SYSTEM_PROMPT
    assert "hashtags" in SYSTEM_PROMPT


def test_build_ai_inputs_sets_context() -> None:
    segments = [
        SegmentState.new("one", 0.0, 1.0),
        SegmentState.new("two", 1.0, 2.0),
        SegmentState.new("three", 2.0, 3.0),
    ]
    inputs = build_ai_inputs(segments)
    assert inputs[0].previous_text is None
    assert inputs[0].next_text == "two"
    assert inputs[1].previous_text == "one"
    assert inputs[1].text == "two"
    assert inputs[1].next_text == "three"
    assert inputs[2].next_text is None


def test_build_user_prompt_current_is_primary() -> None:
    item = AISegmentInput("a", "current text", 1.0, 2.0, previous_text="prev", next_text="next")
    data = json.loads(build_user_prompt([item]))
    entry = data["segments"][0]
    assert entry["current"] == "current text"
    assert entry["previous"] == "prev"
    assert entry["next"] == "next"


def test_build_messages() -> None:
    messages = build_messages([AISegmentInput("a", "text", 0.0, 1.0)])
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
