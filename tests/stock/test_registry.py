"""Tests for the stock provider registry."""

from __future__ import annotations

import pytest

from autotube.exceptions import ValidationError
from autotube.stock.providers import PexelsProvider, PixabayProvider
from autotube.stock.registry import (
    StockProviderRegistry,
    StockProviderSpec,
    default_stock_provider_registry,
)


def test_default_registry_contains_builtin_providers() -> None:
    registry = default_stock_provider_registry()
    assert registry.known_ids() == {"pexels", "pixabay"}


def test_pexels_spec_defaults() -> None:
    spec = default_stock_provider_registry().get("pexels")
    assert spec.display_name == "Pexels"
    assert spec.default_api_key_env_var == "PEXELS_API_KEY"
    assert spec.settings_key_field == "pexels_api_key"


def test_pixabay_spec_defaults() -> None:
    spec = default_stock_provider_registry().get("pixabay")
    assert spec.display_name == "Pixabay"
    assert spec.default_api_key_env_var == "PIXABAY_API_KEY"
    assert spec.settings_key_field == "pixabay_api_key"


def test_build_provider_pexels() -> None:
    provider = default_stock_provider_registry().build_provider("pexels", "key")
    assert isinstance(provider, PexelsProvider)


def test_build_provider_pixabay() -> None:
    provider = default_stock_provider_registry().build_provider("pixabay", "key")
    assert isinstance(provider, PixabayProvider)


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValidationError):
        default_stock_provider_registry().get("unknown")


def test_future_provider_registration() -> None:
    registry = StockProviderRegistry()

    class _FakeProvider:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def search(self, query, limit=3, *, timeout=15.0):
            return []

    registry.register(
        StockProviderSpec(
            provider_id="future",
            display_name="Future",
            default_api_key_env_var="FUTURE_KEY",
            adapter_factory=_FakeProvider,
        )
    )
    spec = registry.get("future")
    assert spec.display_name == "Future"
    provider = registry.build_provider("future", "abc")
    assert isinstance(provider, _FakeProvider)
    assert provider.api_key == "abc"
