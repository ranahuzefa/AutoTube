"""AI video generation scaffolding."""

from .config import AIVideoConfig
from .providers import GeneratedVideo, VideoGenerationProvider
from .registry import (
    AIVideoProviderRegistry,
    AIVideoProviderSpec,
    default_ai_video_provider_registry,
)

__all__ = [
    "AIVideoConfig",
    "AIVideoProviderRegistry",
    "AIVideoProviderSpec",
    "GeneratedVideo",
    "VideoGenerationProvider",
    "default_ai_video_provider_registry",
]
