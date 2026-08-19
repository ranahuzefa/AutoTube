"""Stock asset download manager."""

from __future__ import annotations

import os
import random
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ..exceptions import DownloadCancelledError, DownloadError
from ..redaction import redact_url
from .cache import AssetCache
from .types import StockProvider, StockVideo

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
_CHUNK_SIZE = 64 * 1024


@dataclass
class DownloadResult:
    path: Path
    url: str
    bytes_written: int
    source: StockProvider


class DownloadManager:
    def __init__(
        self,
        cache: AssetCache | None = None,
        *,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        self.cache = cache or AssetCache(Path("stock_cache"))
        self.timeout = timeout
        self.max_retries = max_retries

    def download(
        self,
        video: StockVideo,
        destination_dir: Path,
        *,
        cancel_event: threading.Event | None = None,
    ) -> DownloadResult:
        if not video.url:
            raise DownloadError(f"No URL for stock asset {video.video_id}")

        cached = self.cache.get(video)
        if cached is not None:
            return DownloadResult(
                path=cached,
                url=video.url,
                bytes_written=cached.stat().st_size,
                source=video.provider,
            )

        destination_dir.mkdir(parents=True, exist_ok=True)
        final_path = self.cache.path_for(video)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = final_path.with_name(f".{final_path.name}.part")

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._check_cancel(cancel_event)
            try:
                bytes_written = self._download_once(video.url, tmp_path, cancel_event)
                os.replace(tmp_path, final_path)
                return DownloadResult(
                    path=final_path,
                    url=video.url,
                    bytes_written=bytes_written,
                    source=video.provider,
                )
            except DownloadCancelledError:
                self._cleanup(tmp_path)
                raise
            except DownloadError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    self._cleanup(tmp_path)
                    time.sleep(min(2.0 ** (attempt - 1), 8.0) + random.uniform(0, 0.5))
                else:
                    self._cleanup(tmp_path)
            except Exception as exc:  # noqa: BLE001 - wrap unknown failures
                last_error = DownloadError(f"Download failed: {exc}")
                self._cleanup(tmp_path)
                break

        raise DownloadError(
            f"Download failed for {video.video_id} after {self.max_retries} attempts: {last_error}"
        )

    def _download_once(
        self,
        url: str,
        tmp_path: Path,
        cancel_event: threading.Event | None,
    ) -> int:
        request = urllib.request.Request(url, headers={"User-Agent": "AutoTubeCreator/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                written = 0
                with open(tmp_path, "wb") as out:
                    while True:
                        self._check_cancel(cancel_event)
                        chunk = response.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        out.write(chunk)
                        written += len(chunk)
                    out.flush()
                    os.fsync(out.fileno())
                return written
        except urllib.error.HTTPError as exc:
            if exc.code in _RETRYABLE_STATUS:
                raise DownloadError(
                    f"HTTP {exc.code} for {redact_url(url)}"
                ) from exc
            raise DownloadError(f"HTTP {exc.code} for {redact_url(url)}") from exc
        except urllib.error.URLError as exc:
            raise DownloadError(
                f"Network error for {redact_url(url)}: {exc.reason}"
            ) from exc

    @staticmethod
    def _cleanup(path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

    @staticmethod
    def _check_cancel(cancel_event: threading.Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelledError("Download cancelled.")
