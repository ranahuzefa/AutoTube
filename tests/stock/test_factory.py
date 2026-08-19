"""Tests for the stock provider factory and key resolution."""

from __future__ import annotations

import pytest

from autotube.config import Settings
from autotube.stock.factory import build_stock_providers
from autotube.stock.providers import PexelsProvider, PixabayProvider


def _types(providers) -> list[type]:
    return [type(p) for p in providers]


def test_default_order_uses_legacy_settings_keys(monkeypatch) -> None:
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUBE_PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUBE_PIXABAY_API_KEY", raising=False)
    providers = build_stock_providers(
        Settings(pexels_api_key="p", pixabay_api_key="q")
    )
    assert _types(providers) == [PexelsProvider, PixabayProvider]


def test_respects_configured_order(monkeypatch) -> None:
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUBE_PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUBE_PIXABAY_API_KEY", raising=False)
    providers = build_stock_providers(
        Settings(
            stock_providers=["pixabay", "pexels"],
            pexels_api_key="p",
            pixabay_api_key="q",
        )
    )
    assert _types(providers) == [PixabayProvider, PexelsProvider]


def test_skips_unconfigured_keys(monkeypatch) -> None:
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUBE_PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUBE_PIXABAY_API_KEY", raising=False)
    providers = build_stock_providers(Settings(pexels_api_key="p", pixabay_api_key=""))
    assert _types(providers) == [PexelsProvider]


def test_skips_unknown_ids(monkeypatch) -> None:
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUBE_PEXELS_API_KEY", raising=False)
    providers = build_stock_providers(
        Settings(stock_providers=["unknown", "pexels"], pexels_api_key="p")
    )
    assert _types(providers) == [PexelsProvider]


def test_standard_env_var_precedence(monkeypatch) -> None:
    monkeypatch.setenv("PEXELS_API_KEY", "env-key")
    monkeypatch.setenv("AUTOTUBE_PEXELS_API_KEY", "legacy-env")
    providers = build_stock_providers(Settings(pexels_api_key="stored-key"))
    assert isinstance(providers[0], PexelsProvider)
    assert providers[0].api_key == "env-key"


def test_legacy_env_override_precedence(monkeypatch) -> None:
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.setenv("AUTOTUBE_PEXELS_API_KEY", "legacy-env")
    providers = build_stock_providers(Settings(pexels_api_key="stored-key"))
    assert providers[0].api_key == "legacy-env"


def test_legacy_settings_fallback(monkeypatch) -> None:
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUBE_PEXELS_API_KEY", raising=False)
    providers = build_stock_providers(Settings(pexels_api_key="stored-key"))
    assert providers[0].api_key == "stored-key"


def test_empty_when_nothing_configured(monkeypatch) -> None:
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUBE_PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUBE_PIXABAY_API_KEY", raising=False)
    assert build_stock_providers(Settings()) == []
