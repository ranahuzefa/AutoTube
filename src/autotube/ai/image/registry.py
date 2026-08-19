"""Configuration-driven AI image provider registry.

No concrete image providers are registered yet. Future providers register a
``StockProviderSpec``-style spec with an adapter factory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ...exceptions import ValidationError
from .config import AIImageConfig
from .providers import ImageGenerationProvider

ImageProviderFactory = Callable[[AIImageConfig], ImageGenerationProvider]


@dataclass(frozen=True)
class AIImageProviderSpec:
    """Static configuration for one external AI image provider."""

    provider_id: str
    display_name: str
    default_base_url: str
    default_model: str
    default_api_key_env_var: str
    adapter_factory: ImageProviderFactory | None = None
    extra_settings: dict[str, Any] = field(default_factory=dict)


class AIImageProviderRegistry:
    """Register and construct AI image providers by ID."""

    def __init__(self) -> None:
        self._specs: dict[str, AIImageProviderSpec] = {}

    def register(self, spec: AIImageProviderSpec) -> None:
        if not spec.provider_id.strip():
            raise ValidationError("AI image provider ID must be set.")
        self._specs[spec.provider_id] = spec

    def get(self, provider_id: str) -> AIImageProviderSpec:
        try:
            return self._specs[provider_id]
        except KeyError as exc:
            raise ValidationError(
                f"Unsupported AI image provider: {provider_id!r}."
            ) from exc

    def known_ids(self) -> set[str]:
        return set(self._specs)

    def list_all(self) -> list[AIImageProviderSpec]:
        return list(self._specs.values())

    def build_provider(self, config: AIImageConfig) -> ImageGenerationProvider:
        spec = self.get(config.provider)
        if spec.adapter_factory is None:
            raise ValidationError(
                f"AI image provider {config.provider!r} has no adapter."
            )
        return spec.adapter_factory(config)


_DEFAULT_REGISTRY: AIImageProviderRegistry | None = None


def default_ai_image_provider_registry() -> AIImageProviderRegistry:
    """Return the cached default image provider registry."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = AIImageProviderRegistry()
    return _DEFAULT_REGISTRY
