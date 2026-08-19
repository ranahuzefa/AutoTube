"""Pexels and Pixabay search providers using urllib."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol

from ..exceptions import ConfigurationError, ProviderError, RateLimitError
from ..redaction import redact_url
from .types import StockProvider, StockVideo

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class StockProviderProtocol(Protocol):
    name: StockProvider

    def search(
        self, query: str, limit: int = 3, *, timeout: float = 15.0
    ) -> list[StockVideo]:
        ...


class _HTTPClient:
    def get_json(self, url: str, *, timeout: float, headers: dict | None = None) -> dict:
        request = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise RateLimitError(
                    f"Rate limited by {redact_url(url)}: HTTP {exc.code}"
                ) from exc
            raise ProviderError(
                f"Provider request failed for {redact_url(url)}: HTTP {exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ProviderError(
                f"Provider request failed for {redact_url(url)}: {exc.reason}"
            ) from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProviderError(
                f"Malformed provider response for {redact_url(url)}"
            ) from exc

        if not isinstance(data, dict):
            raise ProviderError(f"Malformed provider response for {redact_url(url)}")
        return data


class PexelsProvider:
    name = StockProvider.PEXELS

    def __init__(self, api_key: str, client: _HTTPClient | None = None) -> None:
        if not api_key or not api_key.strip():
            raise ConfigurationError("Pexels API key is missing.")
        self.api_key = api_key.strip()
        self._client = client or _HTTPClient()

    def search(
        self,
        query: str,
        limit: int = 3,
        *,
        timeout: float = 15.0,
        target_width: int = 1920,
        target_height: int = 1080,
    ) -> list[StockVideo]:
        url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
            {"query": query, "per_page": limit}
        )
        data = self._client.get_json(
            url,
            timeout=timeout,
            headers={"Authorization": self.api_key},
        )
        return [
            self._parse_video(item, target_width, target_height)
            for item in data.get("videos", [])
        ]

    def _parse_video(
        self, item: dict, target_width: int, target_height: int
    ) -> StockVideo:
        video_id = str(item.get("id", ""))
        files = item.get("video_files") or []
        selected = _select_file(files, target_width, target_height)
        if selected is None:
            return StockVideo(
                provider=self.name,
                video_id=video_id,
                url="",
                page_url=item.get("url", ""),
                width=0,
                height=0,
                duration=float(item.get("duration") or 0.0),
            )

        return StockVideo(
            provider=self.name,
            video_id=video_id,
            url=selected["url"],
            page_url=item.get("url", ""),
            width=selected["width"],
            height=selected["height"],
            duration=float(item.get("duration") or 0.0),
            preview_image_url=item.get("image"),
            title=None,
        )


class PixabayProvider:
    name = StockProvider.PIXABAY

    def __init__(self, api_key: str, client: _HTTPClient | None = None) -> None:
        if not api_key or not api_key.strip():
            raise ConfigurationError("Pixabay API key is missing.")
        self.api_key = api_key.strip()
        self._client = client or _HTTPClient()

    def search(
        self,
        query: str,
        limit: int = 3,
        *,
        timeout: float = 15.0,
        target_width: int = 1920,
        target_height: int = 1080,
    ) -> list[StockVideo]:
        url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
            {"key": self.api_key, "q": query, "per_page": limit}
        )
        data = self._client.get_json(url, timeout=timeout)
        hits = data.get("hits", [])
        return [
            self._parse_video(item, target_width, target_height) for item in hits
        ]

    def _parse_video(
        self, item: dict, target_width: int, target_height: int
    ) -> StockVideo:
        video_id = str(item.get("id", ""))
        selected = _select_file(item.get("videos"), target_width, target_height)
        duration = float(item.get("duration") or 0.0)
        if selected is None:
            return StockVideo(
                provider=self.name,
                video_id=video_id,
                url="",
                page_url=item.get("pageURL", ""),
                width=0,
                height=0,
                duration=duration,
            )

        return StockVideo(
            provider=self.name,
            video_id=video_id,
            url=selected["url"],
            page_url=item.get("pageURL", ""),
            width=selected["width"],
            height=selected["height"],
            duration=duration,
            preview_image_url=None,
            title=None,
        )


def _select_file(
    files, target_width: int = 1920, target_height: int = 1080
) -> dict | None:
    """Apply the deterministic video-file selection policy."""
    if not files:
        return None

    eligible = []
    for f in files:
        if not isinstance(f, dict):
            continue
        url = f.get("url")
        if not _is_usable_video_url(url):
            continue
        width = _int(f.get("width"))
        height = _int(f.get("height"))
        eligible.append((width, height, f))

    if not eligible:
        return None

    # Reject portrait/vertical files when target orientation is landscape.
    if target_width > target_height:
        landscape_eligible = [
            (w, h, f) for (w, h, f) in eligible if w > h
        ]
        if landscape_eligible:
            eligible = landscape_eligible
        else:
            return None

    def sort_key(entry):
        width, height, f = entry
        url = str(f.get("url", ""))
        mp4 = (
            0
            if url.lower().endswith(".mp4")
            else (1 if url.lower().endswith((".mov", ".m4v")) else 2)
        )
        landscape = 0 if width > height else 1
        resolution_distance = (
            abs(width - target_width) + abs(height - target_height)
            if width and height
            else 10_000_000
        )
        return (landscape, mp4, resolution_distance)

    eligible.sort(key=sort_key)
    _, _, best = eligible[0]
    return best


def _is_usable_video_url(url) -> bool:
    if not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return False
    lowered = url.lower()
    return lowered.endswith((".mp4", ".mov", ".m4v", ".webm"))


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
