"""AI video generation provider interface.

This module defines the structural contract for future text-to-video providers.
No concrete provider is implemented yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeneratedVideo:
    """A generated video reference returned by a video provider."""

    url: str
    prompt: str
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    provider: str = ""


class VideoGenerationProvider(Protocol):
    """Structural interface for text-to-video providers."""

    def generate(
        self,
        prompt: str,
        *,
        width: int | None = None,
        height: int | None = None,
        duration: float | None = None,
    ) -> GeneratedVideo:
        ...
