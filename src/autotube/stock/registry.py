"""Configuration-driven stock provider registry.

This mirrors :mod:`autotube.ai.registry` for stock media providers. Adding a
future provider requires a new ``StockProviderSpec``, registration in
``default_stock_provider_registry``, and provider-specific tests. It must not
require changes to the CLI, GUI tabs, or ``StockManager``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..constants import (
    PEXELS_API_KEY_ENV_VAR,
    PIXABAY_API_KEY_ENV_VAR,
    STOCK_PROVIDER_PEXELS,
    STOCK_PROVIDER_PIXABAY,
)
from ..exceptions import ValidationError
from .providers import PexelsProvider, PixabayProvider, StockProviderProtocol

StockProviderFactory = Callable[[str], StockProviderProtocol]


@dataclass(frozen=True)
class StockProviderSpec:
    """Static configuration for one external stock provider."""

    provider_id: str
    display_name: str
    default_api_key_env_var: str
    adapter_factory: StockProviderFactory
    settings_key_field: str | None = None
    extra_settings: dict[str, Any] = field(default_factory=dict)


class StockProviderRegistry:
    """Register and construct stock providers by ID."""

    def __init__(self) -> None:
        self._specs: dict[str, StockProviderSpec] = {}

    def register(self, spec: StockProviderSpec) -> None:
        if not spec.provider_id.strip():
            raise ValidationError("Stock provider ID must be set.")
        self._specs[spec.provider_id] = spec

    def get(self, provider_id: str) -> StockProviderSpec:
        try:
            return self._specs[provider_id]
        except KeyError as exc:
            raise ValidationError(
                f"Unsupported stock provider: {provider_id!r}."
            ) from exc

    def known_ids(self) -> set[str]:
        return set(self._specs)

    def list_all(self) -> list[StockProviderSpec]:
        return list(self._specs.values())

    def build_provider(self, provider_id: str, api_key: str) -> StockProviderProtocol:
        spec = self.get(provider_id)
        return spec.adapter_factory(api_key)


_DEFAULT_REGISTRY: StockProviderRegistry | None = None


def default_stock_provider_registry() -> StockProviderRegistry:
    """Return the cached default registry with built-in providers."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = _build_default_registry()
    return _DEFAULT_REGISTRY


def _build_default_registry() -> StockProviderRegistry:
    registry = StockProviderRegistry()
    registry.register(
        StockProviderSpec(
            provider_id=STOCK_PROVIDER_PEXELS,
            display_name="Pexels",
            default_api_key_env_var=PEXELS_API_KEY_ENV_VAR,
            adapter_factory=PexelsProvider,
            settings_key_field="pexels_api_key",
        )
    )
    registry.register(
        StockProviderSpec(
            provider_id=STOCK_PROVIDER_PIXABAY,
            display_name="Pixabay",
            default_api_key_env_var=PIXABAY_API_KEY_ENV_VAR,
            adapter_factory=PixabayProvider,
            settings_key_field="pixabay_api_key",
        )
    )
    return registry
