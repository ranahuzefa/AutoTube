"""Timeline-aware media processing reusing the existing FFmpeg layer."""

from __future__ import annotations

import threading
from pathlib import Path

from ..media.service import FFmpegMediaService
from ..media.types import VideoSpec
from .types import AssetType, TimedVisualAsset


class TimelineMediaProcessor:
    """Process timestamp-named local visual assets into video-only clips."""

    def __init__(self, media_service: FFmpegMediaService) -> None:
        self.media_service = media_service

    def process(
        self,
        asset: TimedVisualAsset,
        spec: VideoSpec,
        output_dir: Path,
        *,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        duration = asset.end - asset.start
        if duration <= 0:
            raise ValueError("Asset duration must be positive.")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / f"{asset.source_path.stem}.mp4"

        if asset.asset_type == AssetType.IMAGE:
            return self.media_service.normalize_image(
                asset.source_path,
                destination,
                spec,
                duration,
                cancel_event=cancel_event,
            )

        info = self.media_service.probe_video(asset.source_path)
        source_duration = info.duration or 0.0

        if source_duration > duration:
            return self.media_service.trim_video(
                asset.source_path,
                destination,
                spec,
                start=0.0,
                end=duration,
                cancel_event=cancel_event,
            )
        return self.media_service.loop_video(
            asset.source_path,
            destination,
            spec,
            duration,
            cancel_event=cancel_event,
        )
