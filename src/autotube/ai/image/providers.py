"""AI image generation provider interface.

This module defines the structural contract for future text-to-image providers.
No concrete provider is implemented yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeneratedImage:
    """A generated image reference returned by an image provider."""

    url: str
    prompt: str
    width: int | None = None
    height: int | None = None
    provider: str = ""


class ImageGenerationProvider(Protocol):
    """Structural interface for text-to-image providers."""

    def generate(
        self,
        prompt: str,
        *,
        width: int | None = None,
        height: int | None = None,
    ) -> GeneratedImage:
        ...
