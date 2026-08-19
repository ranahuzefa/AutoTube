"""faster-whisper model loading with deterministic caching."""

from __future__ import annotations

import threading
from typing import Any

from ..exceptions import TranscriptionModelError
from .config import TranscriptionConfig
from .device import DeviceDetector


class WhisperModelLoader:
    """Load and cache faster-whisper models by configuration."""

    def __init__(self, cache: dict[tuple, Any] | None = None) -> None:
        self._cache = cache if cache is not None else {}
        self._lock = threading.Lock()
        self._detector = DeviceDetector()

    def get(self, config: TranscriptionConfig) -> Any:
        """Return a cached or newly loaded model for ``config``.

        The returned model is shared and read-only. Do not run two simultaneous
        ``transcribe()`` calls on the same instance.
        """
        device = self._detector.detect(config.device, config.compute_type)
        key = (
            config.model,
            device.device,
            device.compute_type,
            int(config.cpu_threads),
            config.download_root or "",
        )

        with self._lock:
            if key in self._cache:
                return self._cache[key]

            try:
                from faster_whisper import WhisperModel  # lazy import
            except ImportError as exc:
                raise TranscriptionModelError(
                    "faster-whisper is not installed."
                ) from exc

            try:
                model = WhisperModel(
                    config.model,
                    device=device.device,
                    compute_type=device.compute_type,
                    cpu_threads=config.cpu_threads,
                    download_root=config.download_root,
                )
            except Exception as exc:  # noqa: BLE001 - wrap all load failures
                raise TranscriptionModelError(
                    f"Failed to load whisper model {config.model!r}: {exc}"
                ) from exc

            self._cache[key] = model
            return model
