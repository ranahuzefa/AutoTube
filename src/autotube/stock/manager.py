"""Stock search, download, and cache orchestration."""

from __future__ import annotations

import threading
from pathlib import Path

from ..exceptions import ProviderError, StockError
from ..media.service import FFmpegMediaService
from ..state import SegmentState
from .cache import AssetCache
from .download import DownloadManager
from .providers import StockProviderProtocol
from .scoring import StockScorer, filter_candidates
from .types import StockFilter, StockVideo


class StockManager:
    """Find and download the best stock asset for a segment."""

    def __init__(
        self,
        providers: list[StockProviderProtocol],
        downloader: DownloadManager,
        cache: AssetCache,
        media_service: FFmpegMediaService | None = None,
    ) -> None:
        self.providers = providers
        self.downloader = downloader
        self.cache = cache
        self.media_service = media_service or FFmpegMediaService()
        self.scorer = StockScorer()

    def find_asset(
        self,
        segment: SegmentState,
        query: str,
        filter: StockFilter,
        *,
        cancel_event: threading.Event | None = None,
    ) -> StockVideo:
        candidates: list[StockVideo] = []
        errors: list[str] = []

        for provider in self.providers:
            if cancel_event is not None and cancel_event.is_set():
                raise StockError("Stock search cancelled.")
            try:
                results = provider.search(
                    query,
                    limit=3,
                    timeout=15.0,
                    target_width=filter.width,
                    target_height=filter.height,
                )
            except ProviderError as exc:
                errors.append(str(exc))
                continue

            candidates.extend(results)
            if candidates:
                break

        if not candidates:
            raise StockError(
                "No stock provider returned usable candidates."
                + (f" Errors: {errors}" if errors else "")
            )

        suitable = filter_candidates(candidates, filter)
        if not suitable:
            raise StockError("No stock candidate matched the target format filters.")

        suitable.sort(key=lambda v: self.scorer.score(v, filter, query), reverse=True)
        return suitable[0]

    def download_asset(
        self,
        video: StockVideo,
        destination_dir: Path,
        *,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        result = self.downloader.download(
            video, destination_dir, cancel_event=cancel_event
        )

        # Validate with the existing media layer.
        self.media_service.probe_video(result.path)

        video.local_path = str(result.path)
        return result.path

    def resolve_segment(
        self,
        segment: SegmentState,
        filter: StockFilter,
        destination_dir: Path,
        *,
        cancel_event: threading.Event | None = None,
    ) -> None:
        if not segment.keywords:
            segment.error = "No keywords available for stock search."
            return

        query = " ".join(segment.keywords[:2])
        try:
            video = self.find_asset(
                segment, query, filter, cancel_event=cancel_event
            )
            local_path = self.download_asset(
                video, destination_dir, cancel_event=cancel_event
            )
            segment.selected_clip = video.to_dict()
            segment.selected_clip["local_path"] = str(local_path)
            segment.error = None
        except StockError as exc:
            segment.error = str(exc)
