"""Tests for stock dataclass serialization."""

from __future__ import annotations

from autotube.models import RenderSettings
from autotube.stock.types import (
    StockFilter,
    StockProvider,
    StockVideo,
)


def test_stock_provider_is_str_enum() -> None:
    assert isinstance(StockProvider.PEXELS, str)
    assert StockProvider.PEXELS.value == "pexels"


def test_stock_video_roundtrip() -> None:
    video = StockVideo(
        provider=StockProvider.PEXELS,
        video_id="123",
        url="https://example.com/video.mp4",
        page_url="https://example.com/video",
        width=1920,
        height=1080,
        duration=10.0,
        local_path="C:/cache/pexels/123.mp4",
    )
    assert StockVideo.from_dict(video.to_dict()) == video


def test_stock_video_missing_local_path_defaults_none() -> None:
    data = StockVideo(
        provider=StockProvider.PIXABAY,
        video_id="456",
        url="https://example.com/video.mp4",
        page_url="",
        width=1280,
        height=720,
        duration=5.0,
    ).to_dict()
    data.pop("local_path")
    assert StockVideo.from_dict(data).local_path is None


def test_stock_filter_from_render_settings() -> None:
    filter = StockFilter.from_render_settings(
        RenderSettings(resolution="1920x1080", fps=30)
    )
    assert filter.width == 1920
    assert filter.height == 1080
    assert filter.min_width == 1280
    assert filter.min_height == 720
    assert filter.orientation == "landscape"
