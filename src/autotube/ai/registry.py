"""Configuration-driven AI provider registry.

This is a small in-process catalog of AI provider specifications. Adding a
future provider requires a new ``AIProviderSpec``, registration in
``default_ai_provider_registry``, and provider-specific tests. It must not
require changes to the keyword engine, stock workflow, or local fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..constants import (
    AI_PROVIDER_DASHSCOPE,
    AI_PROVIDER_OPENROUTER,
    DASHSCOPE_API_KEY_ENV_VAR,
    DASHSCOPE_DEFAULT_BASE_URL,
    DASHSCOPE_DEFAULT_MODEL,
    DASHSCOPE_DISPLAY_NAME,
    DEFAULT_AI_API_KEY_ENV_VAR,
    DEFAULT_AI_BASE_URL,
    DEFAULT_AI_MODEL,
)
from ..exceptions import ValidationError
from .config import AIConfig
from .providers import AIKeywordProvider, OpenAICompatibleProvider

ProviderFactory = Callable[[AIConfig], AIKeywordProvider]


@dataclass(frozen=True)
class AIProviderSpec:
    """Static configuration for one external AI provider."""

    provider_id: str
    display_name: str
    default_base_url: str
    default_model: str
    default_api_key_env_var: str
    adapter_factory: ProviderFactory | None = None
    extra_settings: dict[str, Any] = field(default_factory=dict)


class AIProviderRegistry:
    """Register and construct AI keyword providers by ID."""

    def __init__(self) -> None:
        self._specs: dict[str, AIProviderSpec] = {}

    def register(self, spec: AIProviderSpec) -> None:
        if not spec.provider_id.strip():
            raise ValidationError("AI provider ID must be set.")
        self._specs[spec.provider_id] = spec

    def get(self, provider_id: str) -> AIProviderSpec:
        try:
            return self._specs[provider_id]
        except KeyError as exc:
            raise ValidationError(f"Unsupported AI provider: {provider_id!r}.") from exc

    def known_ids(self) -> set[str]:
        return set(self._specs)

    def list_all(self) -> list[AIProviderSpec]:
        return list(self._specs.values())

    def build_provider(self, config: AIConfig) -> AIKeywordProvider:
        spec = self.get(config.provider)
        factory = spec.adapter_factory or OpenAICompatibleProvider
        return factory(config)


_DEFAULT_REGISTRY: AIProviderRegistry | None = None


def default_ai_provider_registry() -> AIProviderRegistry:
    """Return the cached default registry with built-in providers."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = _build_default_registry()
    return _DEFAULT_REGISTRY


def _build_default_registry() -> AIProviderRegistry:
    registry = AIProviderRegistry()
    registry.register(
        AIProviderSpec(
            provider_id=AI_PROVIDER_OPENROUTER,
            display_name="OpenRouter",
            default_base_url=DEFAULT_AI_BASE_URL,
            default_model=DEFAULT_AI_MODEL,
            default_api_key_env_var=DEFAULT_AI_API_KEY_ENV_VAR,
        )
    )
    registry.register(
        AIProviderSpec(
            provider_id=AI_PROVIDER_DASHSCOPE,
            display_name=DASHSCOPE_DISPLAY_NAME,
            default_base_url=DASHSCOPE_DEFAULT_BASE_URL,
            default_model=DASHSCOPE_DEFAULT_MODEL,
            default_api_key_env_var=DASHSCOPE_API_KEY_ENV_VAR,
        )
    )
    return registry
