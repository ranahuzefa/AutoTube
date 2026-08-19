"""AI keyword service factory."""

from __future__ import annotations

from ..config import Settings
from ..stock.keywords import LocalKeywordService
from .config import AIConfig
from .engine import AIKeywordEngine
from .registry import default_ai_provider_registry


def build_keyword_service(settings: Settings):
    """Return a keyword service: AI when enabled, else deterministic local."""
    config = AIConfig.from_settings(settings)
    if not config.enabled:
        return LocalKeywordService()
    provider = default_ai_provider_registry().build_provider(config)
    return AIKeywordEngine(config=config, provider=provider)
