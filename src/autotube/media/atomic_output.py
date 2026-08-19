"""Atomic temporary-output management for FFmpeg-generated files."""

from __future__ import annotations

import os
import secrets
from pathlib import Path


class ManagedTempOutput:
    """Context manager that hands FFmpeg a temp path and atomically renames it.

    The temp file lives in the destination directory so ``os.replace`` stays on
    the same volume. On success the temp file is renamed into place; on error it
    is removed.
    """

    def __init__(self, destination: Path) -> None:
        self.destination = destination
        self._temp: Path | None = None

    def __enter__(self) -> Path:
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        suffix = self.destination.suffix or ".mp4"
        token = secrets.token_hex(4)
        self._temp = self.destination.parent / f".{self.destination.stem}.{token}.partial{suffix}"
        return self._temp

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._temp is None:
            return False
        try:
            if exc_type is None:
                os.replace(self._temp, self.destination)
        finally:
            if self._temp.exists():
                try:
                    os.unlink(self._temp)
                except OSError:
                    pass
        return False
