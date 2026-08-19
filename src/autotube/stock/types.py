"""Stock dataclasses and serialization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..models import RenderSettings


class StockProvider(str, Enum):
    PEXELS = "pexels"
    PIXABAY = "pixabay"


@dataclass
class StockVideo:
    provider: StockProvider
    video_id: str
    url: str
    page_url: str
    width: int
    height: int
    duration: float
    preview_image_url: str | None = None
    title: str | None = None
    local_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.value,
            "video_id": self.video_id,
            "url": self.url,
            "page_url": self.page_url,
            "width": self.width,
            "height": self.height,
            "duration": self.duration,
            "preview_image_url": self.preview_image_url,
            "title": self.title,
            "local_path": self.local_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StockVideo":
        return cls(
            provider=StockProvider(data.get("provider", StockProvider.PEXELS.value)),
            video_id=str(data["video_id"]),
            url=str(data["url"]),
            page_url=str(data.get("page_url", "")),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            duration=float(data.get("duration", 0.0)),
            preview_image_url=data.get("preview_image_url"),
            title=data.get("title"),
            local_path=data.get("local_path"),
        )


@dataclass
class StockSearchResult:
    provider: StockProvider
    query: str
    videos: list[StockVideo]


@dataclass
class StockFilter:
    width: int
    height: int
    min_width: int
    min_height: int
    min_duration: float
    max_duration: float
    orientation: str = "landscape"

    @classmethod
    def from_render_settings(cls, settings: RenderSettings) -> "StockFilter":
        width, height = _parse_resolution(settings.resolution)
        min_width, min_height = _parse_resolution("1280x720")
        return cls(
            width=width,
            height=height,
            min_width=min_width,
            min_height=min_height,
            min_duration=1.0,
            max_duration=60.0,
            orientation="landscape" if width > height else "portrait",
        )


def _parse_resolution(resolution: str) -> tuple[int, int]:
    width, height = resolution.lower().split("x")
    return int(width), int(height)
