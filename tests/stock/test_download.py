"""Tests for atomic downloads with mocked urlopen."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from autotube.exceptions import DownloadCancelledError, DownloadError
from autotube.stock.cache import AssetCache
from autotube.stock.download import DownloadManager
from autotube.stock.types import StockProvider, StockVideo


class _FakeResponse:
    def __init__(self, chunks):
        self._chunks = iter(chunks)

    def read(self, size):
        try:
            return next(self._chunks)
        except StopIteration:
            return b""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeOpener:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = 0

    def __call__(self, request, timeout):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.response


def _video(url="https://x/v.mp4"):
    return StockVideo(
        provider=StockProvider.PEXELS,
        video_id="abc",
        url=url,
        page_url="",
        width=1920,
        height=1080,
        duration=5.0,
    )


def test_success_and_atomic_rename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AssetCache(tmp_path / "cache")
    opener = _FakeOpener(_FakeResponse([b"hello", b"world"]))
    monkeypatch.setattr("urllib.request.urlopen", opener)
    manager = DownloadManager(cache, timeout=1, max_retries=1)
    result = manager.download(_video(), tmp_path / "dest")
    assert result.path.exists()
    assert result.path.read_bytes() == b"helloworld"
    assert list(result.path.parent.glob("*.part")) == []


def test_failure_cleans_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AssetCache(tmp_path / "cache")
    opener = _FakeOpener(exc=OSError("network down"))
    monkeypatch.setattr("urllib.request.urlopen", opener)
    manager = DownloadManager(cache, timeout=1, max_retries=1)
    with pytest.raises(DownloadError):
        manager.download(_video(), tmp_path / "dest")
    assert list((tmp_path / "dest").glob("*.part")) == []


def test_cancel_cleans_part_and_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AssetCache(tmp_path / "cache")
    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr("urllib.request.urlopen", _FakeOpener(_FakeResponse([b"data"])))
    manager = DownloadManager(cache, timeout=1, max_retries=1)
    with pytest.raises(DownloadCancelledError):
        manager.download(_video(), tmp_path / "dest", cancel_event=cancel)
    assert list((tmp_path / "dest").glob("*.part")) == []


def test_cache_hit_avoids_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = AssetCache(tmp_path / "cache")
    video = _video()
    cached = cache.path_for(video)
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"cached")
    opener = _FakeOpener(_FakeResponse([b"new"]))
    monkeypatch.setattr("urllib.request.urlopen", opener)
    manager = DownloadManager(cache, timeout=1, max_retries=1)
    result = manager.download(video, tmp_path / "dest")
    assert result.path == cached
    assert result.path.read_bytes() == b"cached"
    assert opener.calls == 0


def test_download_error_redacts_signed_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import urllib.error

    cache = AssetCache(tmp_path / "cache")
    manager = DownloadManager(cache, timeout=1, max_retries=1)

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 500, "Err", {}, None
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    video = _video(
        url="https://cdn.example.com/v.mp4?Signature=TOPSECRET&Expires=99999"
    )
    with pytest.raises(DownloadError) as exc:
        manager.download(video, tmp_path / "dest")
    assert "TOPSECRET" not in str(exc.value)
    assert "99999" not in str(exc.value)
