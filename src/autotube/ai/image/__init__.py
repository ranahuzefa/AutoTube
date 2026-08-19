"""AI image generation scaffolding."""

from .config import AIImageConfig
from .providers import GeneratedImage, ImageGenerationProvider
from .registry import (
    AIImageProviderRegistry,
    AIImageProviderSpec,
    default_ai_image_provider_registry,
)

__all__ = [
    "AIImageConfig",
    "AIImageProviderRegistry",
    "AIImageProviderSpec",
    "GeneratedImage",
    "ImageGenerationProvider",
    "default_ai_image_provider_registry",
]
