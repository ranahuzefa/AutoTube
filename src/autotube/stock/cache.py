"""Local asset cache and safe filenames."""

from __future__ import annotations

import os
from pathlib import Path

from .constants import safe_filename
from .types import StockProvider, StockVideo


class AssetCache:
    """Cache downloaded assets under ``root/<provider>/<safe_id>.mp4``."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, video: StockVideo) -> Path:
        provider = safe_filename(video.provider.value)
        asset_id = safe_filename(video.video_id)
        return self.root / provider / f"{asset_id}.mp4"

    def get(self, video: StockVideo) -> Path | None:
        path = self.path_for(video)
        return path if path.exists() else None

    def contains(self, video: StockVideo) -> bool:
        return self.get(video) is not None

    def put(self, video: StockVideo, source_path: Path) -> Path:
        destination = self.path_for(video)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source_path, destination)
        return destination
