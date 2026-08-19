"""Tests for stock scoring and filtering."""

from __future__ import annotations

from autotube.stock.scoring import StockScorer, filter_candidates
from autotube.stock.types import StockFilter, StockProvider, StockVideo


def _video(width, height, duration, url="https://x/v.mp4"):
    return StockVideo(
        provider=StockProvider.PEXELS,
        video_id=str(width),
        url=url,
        page_url="",
        width=width,
        height=height,
        duration=duration,
        title=None,
    )


def test_filters_portrait_when_landscape_target() -> None:
    f = StockFilter(1920, 1080, 1280, 720, 1.0, 60.0, "landscape")
    videos = [_video(1080, 1920, 10.0), _video(1920, 1080, 10.0)]
    assert [v.video_id for v in filter_candidates(videos, f)] == ["1920"]


def test_filters_low_resolution() -> None:
    f = StockFilter(1920, 1080, 1280, 720, 1.0, 60.0, "landscape")
    videos = [_video(640, 360, 10.0), _video(1280, 720, 10.0)]
    assert [v.video_id for v in filter_candidates(videos, f)] == ["1280"]


def test_filters_duration() -> None:
    f = StockFilter(1920, 1080, 1280, 720, 3.0, 30.0, "landscape")
    videos = [_video(1920, 1080, 1.0), _video(1920, 1080, 10.0)]
    assert [v.video_id for v in filter_candidates(videos, f)] == ["1920"]


def test_scoring_prefers_landscape_hd_long_enough() -> None:
    f = StockFilter(1920, 1080, 1280, 720, 3.0, 60.0, "landscape")
    scorer = StockScorer()
    good = _video(1920, 1080, 10.0)
    bad = _video(1080, 1920, 2.0)
    assert scorer.score(good, f) > scorer.score(bad, f)
