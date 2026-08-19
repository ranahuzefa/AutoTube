"""Tests for StockManager fallback, download, and failure behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from autotube.exceptions import ProviderError
from autotube.state import SegmentState
from autotube.stock.cache import AssetCache
from autotube.stock.download import DownloadManager
from autotube.stock.manager import StockManager
from autotube.stock.types import StockFilter, StockProvider, StockVideo


class _FakeMedia:
    def probe_video(self, path):
        from types import SimpleNamespace

        return SimpleNamespace(video_stream=lambda: SimpleNamespace())


class _Provider:
    def __init__(self, name, videos=None, exc=None):
        self.name = name
        self.videos = videos or []
        self.exc = exc
        self.calls = 0

    def search(self, query, limit=3, *, timeout=15.0, target_width=1920, target_height=1080):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.videos


def _video(provider, id="1", url="https://x/v.mp4"):
    return StockVideo(
        provider=provider,
        video_id=id,
        url=url,
        page_url="",
        width=1920,
        height=1080,
        duration=10.0,
    )


def test_fallback_to_second_provider(tmp_path: Path) -> None:
    first = _Provider(StockProvider.PEXELS, exc=ProviderError("down"))
    second = _Provider(StockProvider.PIXABAY, videos=[_video(StockProvider.PIXABAY, "2")])
    manager = StockManager(
        [first, second],
        DownloadManager(AssetCache(tmp_path)),
        AssetCache(tmp_path),
        _FakeMedia(),
    )
    segment = SegmentState.new("ocean", 0.0, 1.0)
    video = manager.find_asset(segment, "ocean", StockFilter(1920, 1080, 1280, 720, 1.0, 60.0))
    assert video.video_id == "2"
    assert first.calls == 1
    assert second.calls == 1


def test_no_fake_asset_when_all_providers_fail(tmp_path: Path) -> None:
    first = _Provider(StockProvider.PEXELS, exc=ProviderError("down"))
    second = _Provider(StockProvider.PIXABAY, exc=ProviderError("also down"))
    manager = StockManager(
        [first, second],
        DownloadManager(AssetCache(tmp_path)),
        AssetCache(tmp_path),
        _FakeMedia(),
    )
    segment = SegmentState.new("ocean", 0.0, 1.0)
    with pytest.raises(Exception):
        manager.find_asset(segment, "ocean", StockFilter(1920, 1080, 1280, 720, 1.0, 60.0))


def test_resolve_segment_sets_local_path(tmp_path: Path) -> None:
    provider = _Provider(StockProvider.PEXELS, videos=[_video(StockProvider.PEXELS, "3")])
    cache = AssetCache(tmp_path / "cache")
    # Pre-populate cache so no real download/network is attempted.
    video = _video(StockProvider.PEXELS, "3")
    cached = cache.path_for(video)
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"fake video")

    manager = StockManager(
        [provider],
        DownloadManager(cache),
        cache,
        _FakeMedia(),
    )
    segment = SegmentState.new("ocean", 0.0, 1.0)
    segment.keywords = ["ocean"]
    manager.resolve_segment(
        segment, StockFilter(1920, 1080, 1280, 720, 1.0, 60.0), tmp_path / "dest"
    )
    assert segment.selected_clip is not None
    assert segment.selected_clip["local_path"] == str(cached)
