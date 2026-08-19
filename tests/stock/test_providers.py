"""Tests for stock providers with mocked HTTP."""

from __future__ import annotations

import json
import urllib.error

import pytest

from autotube.exceptions import ConfigurationError, ProviderError, RateLimitError
from autotube.stock.providers import (
    PexelsProvider,
    PixabayProvider,
    _HTTPClient,
    _select_file,
)


class _FakeClient:
    def __init__(self, payload=None, exc=None):
        self.payload = payload
        self.exc = exc

    def get_json(self, url, *, timeout, headers=None):
        if self.exc is not None:
            raise self.exc
        return self.payload


def test_missing_pexels_key() -> None:
    with pytest.raises(ConfigurationError):
        PexelsProvider("")


def test_missing_pixabay_key() -> None:
    with pytest.raises(ConfigurationError):
        PixabayProvider("")


def test_pexels_success() -> None:
    payload = {
        "videos": [
            {
                "id": 123,
                "url": "https://page",
                "duration": 10,
                "video_files": [
                    {"url": "https://x/a.mp4", "width": 1920, "height": 1080}
                ],
            }
        ]
    }
    provider = PexelsProvider("key", client=_FakeClient(payload))
    videos = provider.search("ocean")
    assert len(videos) == 1
    assert videos[0].url == "https://x/a.mp4"
    assert videos[0].local_path is None


def test_pexels_malformed_json() -> None:
    provider = PexelsProvider("key", client=_FakeClient({"unexpected": True}))
    assert provider.search("ocean") == []


def test_pexels_http_429(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.request

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError("url", 429, "Rate", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = PexelsProvider("key")
    with pytest.raises(RateLimitError):
        provider.search("ocean")


def test_pexels_http_500(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.request

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError("url", 500, "Err", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = PexelsProvider("key")
    with pytest.raises(ProviderError):
        provider.search("ocean")


def test_pixabay_success() -> None:
    payload = {
        "hits": [
            {
                "id": 456,
                "pageURL": "https://page",
                "duration": 8,
                "videos": [
                    {"url": "https://x/b.mp4", "width": 1280, "height": 720}
                ],
            }
        ]
    }
    provider = PixabayProvider("key", client=_FakeClient(payload))
    videos = provider.search("forest")
    assert len(videos) == 1
    assert videos[0].url == "https://x/b.mp4"


def test_pixabay_error_redacts_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.request

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError("url", 500, "Err", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = PixabayProvider("SUPER-SECRET-KEY")
    with pytest.raises(ProviderError) as exc:
        provider.search("forest")
    assert "SUPER-SECRET-KEY" not in str(exc.value)


def test_select_file_prefers_mp4_landscape_closest_resolution() -> None:
    files = [
        {"url": "https://x/portrait.mov", "width": 1080, "height": 1920},
        {"url": "https://x/landscape_high.mp4", "width": 2560, "height": 1440},
        {"url": "https://x/landscape_close.mp4", "width": 1920, "height": 1080},
        {"url": "https://x/landscape_low.mp4", "width": 640, "height": 360},
    ]
    best = _select_file(files, 1920, 1080)
    assert best["url"] == "https://x/landscape_close.mp4"


def test_select_file_rejects_no_usable_url() -> None:
    files = [
        {"url": "", "width": 1920, "height": 1080},
        {"url": "not-a-url", "width": 1920, "height": 1080},
    ]
    assert _select_file(files, 1920, 1080) is None


def test_select_file_rejects_all_portrait() -> None:
    files = [
        {"url": "https://x/a.mp4", "width": 1080, "height": 1920},
        {"url": "https://x/b.mp4", "width": 720, "height": 1280},
    ]
    assert _select_file(files, 1920, 1080) is None
