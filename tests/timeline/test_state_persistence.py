"""Tests for timeline state persistence."""

from __future__ import annotations

from autotube.state import ProjectState
from autotube.timeline.types import SubtitleEntry, TimelineState


def test_timeline_roundtrip() -> None:
    timeline = TimelineState(
        subtitles=[SubtitleEntry(index=1, start=0.0, end=1.0, text="Hi", animation_preset="fade_in")],
    )
    restored = TimelineState.from_dict(timeline.to_dict())
    assert restored.subtitles[0].text == "Hi"
    assert restored.subtitles[0].animation_preset == "fade_in"


def test_project_state_timeline_roundtrip() -> None:
    state = ProjectState()
    state.timeline = TimelineState(
        subtitles=[SubtitleEntry(index=1, start=0.0, end=1.0, text="Hi")]
    )
    restored = ProjectState.from_dict(state.to_dict())
    assert restored.timeline is not None
    assert restored.timeline.subtitles[0].text == "Hi"


def test_project_state_missing_timeline_defaults_none() -> None:
    data = ProjectState().to_dict()
    data.pop("timeline")
    restored = ProjectState.from_dict(data)
    assert restored.timeline is None
