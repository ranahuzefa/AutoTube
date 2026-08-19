"""Tests for asset cache and safe filenames."""

from __future__ import annotations

from pathlib import Path

from autotube.stock.cache import AssetCache
from autotube.stock.constants import safe_filename
from autotube.stock.types import StockProvider, StockVideo


def test_safe_filename_sanitizes_invalid_chars() -> None:
    assert safe_filename('a<b>c:"d/\\e|f?g*h') == "a_b_c__d__e_f_g_h"


def test_safe_filename_strips_trailing_dots_and_spaces() -> None:
    assert safe_filename("video... ") == "video"


def test_safe_filename_hashes_empty_result() -> None:
    assert safe_filename("???") != ""


def test_cache_path_deterministic() -> None:
    cache = AssetCache(Path("root"))
    video = StockVideo(
        provider=StockProvider.PEXELS,
        video_id="abc",
        url="https://x/v.mp4",
        page_url="",
        width=1920,
        height=1080,
        duration=5.0,
    )
    p1 = cache.path_for(video)
    p2 = cache.path_for(video)
    assert p1 == p2
    assert p1 == Path("root") / "pexels" / "abc.mp4"


def test_cache_get_contains_put(tmp_path: Path) -> None:
    cache = AssetCache(tmp_path / "cache")
    video = StockVideo(
        provider=StockProvider.PIXABAY,
        video_id="xyz",
        url="https://x/v.mp4",
        page_url="",
        width=1280,
        height=720,
        duration=5.0,
    )
    assert cache.get(video) is None
    assert not cache.contains(video)

    src = tmp_path / "downloaded.mp4"
    src.write_bytes(b"data")
    final = cache.put(video, src)
    assert final.exists()
    assert cache.contains(video)
    assert cache.get(video) == final
