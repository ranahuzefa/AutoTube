"""Optional AI generation: keyword, image, and video scaffolding."""

from .config import AIConfig
from .engine import AIKeywordEngine
from .factory import build_keyword_service
from .image import (
    AIImageConfig,
    AIImageProviderRegistry,
    AIImageProviderSpec,
    GeneratedImage,
    ImageGenerationProvider,
    default_ai_image_provider_registry,
)
from .models import AISegmentInput, AISegmentOutput, BatchKeywordResult
from .providers import AIKeywordProvider, OpenAICompatibleProvider
from .registry import (
    AIProviderRegistry,
    AIProviderSpec,
    default_ai_provider_registry,
)
from .video import (
    AIVideoConfig,
    AIVideoProviderRegistry,
    AIVideoProviderSpec,
    GeneratedVideo,
    VideoGenerationProvider,
    default_ai_video_provider_registry,
)

__all__ = [
    "AIConfig",
    "AIImageConfig",
    "AIImageProviderRegistry",
    "AIImageProviderSpec",
    "AIKeywordEngine",
    "AIKeywordProvider",
    "AIProviderRegistry",
    "AIProviderSpec",
    "AISegmentInput",
    "AISegmentOutput",
    "AIVideoConfig",
    "AIVideoProviderRegistry",
    "AIVideoProviderSpec",
    "BatchKeywordResult",
    "GeneratedImage",
    "GeneratedVideo",
    "ImageGenerationProvider",
    "OpenAICompatibleProvider",
    "VideoGenerationProvider",
    "build_keyword_service",
    "default_ai_image_provider_registry",
    "default_ai_provider_registry",
    "default_ai_video_provider_registry",
]
