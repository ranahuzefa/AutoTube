"""Tests for stock metadata in ProjectState."""

from __future__ import annotations

from autotube.state import ProjectState, SegmentState
from autotube.stock.types import StockProvider, StockVideo


def test_selected_clip_roundtrip_with_local_path() -> None:
    state = ProjectState()
    seg = SegmentState.new("ocean", 0.0, 1.0)
    video = StockVideo(
        provider=StockProvider.PEXELS,
        video_id="123",
        url="https://x/v.mp4",
        page_url="",
        width=1920,
        height=1080,
        duration=10.0,
        local_path="C:/cache/pexels/123.mp4",
    )
    seg.selected_clip = video.to_dict()
    state.segments = [seg]

    restored = ProjectState.from_dict(state.to_dict())
    assert restored.segments[0].selected_clip["local_path"] == "C:/cache/pexels/123.mp4"
    assert restored.segments[0].selected_clip["provider"] == "pexels"
