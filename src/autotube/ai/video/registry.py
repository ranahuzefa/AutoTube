"""Configuration-driven AI video provider registry.

No concrete video providers are registered yet. Future providers register a
spec with an adapter factory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ...exceptions import ValidationError
from .config import AIVideoConfig
from .providers import VideoGenerationProvider

VideoProviderFactory = Callable[[AIVideoConfig], VideoGenerationProvider]


@dataclass(frozen=True)
class AIVideoProviderSpec:
    """Static configuration for one external AI video provider."""

    provider_id: str
    display_name: str
    default_base_url: str
    default_model: str
    default_api_key_env_var: str
    adapter_factory: VideoProviderFactory | None = None
    extra_settings: dict[str, Any] = field(default_factory=dict)


class AIVideoProviderRegistry:
    """Register and construct AI video providers by ID."""

    def __init__(self) -> None:
        self._specs: dict[str, AIVideoProviderSpec] = {}

    def register(self, spec: AIVideoProviderSpec) -> None:
        if not spec.provider_id.strip():
            raise ValidationError("AI video provider ID must be set.")
        self._specs[spec.provider_id] = spec

    def get(self, provider_id: str) -> AIVideoProviderSpec:
        try:
            return self._specs[provider_id]
        except KeyError as exc:
            raise ValidationError(
                f"Unsupported AI video provider: {provider_id!r}."
            ) from exc

    def known_ids(self) -> set[str]:
        return set(self._specs)

    def list_all(self) -> list[AIVideoProviderSpec]:
        return list(self._specs.values())

    def build_provider(self, config: AIVideoConfig) -> VideoGenerationProvider:
        spec = self.get(config.provider)
        if spec.adapter_factory is None:
            raise ValidationError(
                f"AI video provider {config.provider!r} has no adapter."
            )
        return spec.adapter_factory(config)


_DEFAULT_REGISTRY: AIVideoProviderRegistry | None = None


def default_ai_video_provider_registry() -> AIVideoProviderRegistry:
    """Return the cached default video provider registry."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = AIVideoProviderRegistry()
    return _DEFAULT_REGISTRY
