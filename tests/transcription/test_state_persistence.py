"""Tests for new Phase 3 state persistence fields."""

from __future__ import annotations

from autotube.state import (
    ProjectState,
    SegmentState,
    TranscriptionInfo,
    WordState,
)


def test_word_state_roundtrip() -> None:
    word = WordState("hello", 0.0, 1.0, 0.9)
    assert WordState.from_dict(word.to_dict()) == word


def test_segment_words_roundtrip() -> None:
    seg = SegmentState.new("hello world", 0.0, 1.0)
    seg.words = [WordState("hello", 0.0, 0.5, 0.9)]
    restored = SegmentState.from_dict(seg.to_dict())
    assert restored.words == seg.words


def test_segment_missing_words_defaults_empty() -> None:
    data = SegmentState.new("hello", 0.0, 1.0).to_dict()
    data.pop("words")
    restored = SegmentState.from_dict(data)
    assert restored.words == []


def test_project_transcription_roundtrip() -> None:
    state = ProjectState()
    state.transcription = TranscriptionInfo(language="en", duration=10.0)
    restored = ProjectState.from_dict(state.to_dict())
    assert restored.transcription.language == "en"
    assert restored.transcription.duration == 10.0


def test_project_missing_transcription_defaults_none() -> None:
    data = ProjectState().to_dict()
    data.pop("transcription")
    restored = ProjectState.from_dict(data)
    assert restored.transcription is None
