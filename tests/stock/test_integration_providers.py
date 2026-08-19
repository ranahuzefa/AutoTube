"""Optional provider integration test, gated by env vars."""

from __future__ import annotations

import os

import pytest

from autotube.stock.providers import PexelsProvider, PixabayProvider

pytestmark = [pytest.mark.integration, pytest.mark.stock]


@pytest.fixture
def stock_enabled() -> bool:
    return os.environ.get("AUTOTUBE_RUN_STOCK_TESTS") == "1"


@pytest.fixture
def require_stock(stock_enabled: bool):
    if not stock_enabled:
        pytest.skip("stock integration tests not enabled")


def test_pexels_search(require_stock) -> None:
    key = os.environ.get("AUTOTUBE_PEXELS_API_KEY", "")
    if not key:
        pytest.skip("AUTOTUBE_PEXELS_API_KEY not set")
    provider = PexelsProvider(key)
    videos = provider.search("ocean", limit=2)
    assert isinstance(videos, list)


def test_pixabay_search(require_stock) -> None:
    key = os.environ.get("AUTOTUBE_PIXABAY_API_KEY", "")
    if not key:
        pytest.skip("AUTOTUBE_PIXABAY_API_KEY not set")
    provider = PixabayProvider(key)
    videos = provider.search("forest", limit=2)
    assert isinstance(videos, list)


def test_build_stock_providers_from_env(require_stock) -> None:
    from autotube.config import Settings
    from autotube.stock.factory import build_stock_providers

    pexels_key = os.environ.get("PEXELS_API_KEY", "")
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
    if not pexels_key and not pixabay_key:
        pytest.skip("PEXELS_API_KEY and PIXABAY_API_KEY not set")

    providers = build_stock_providers(Settings())
    names = [type(p) for p in providers]
    if pexels_key:
        assert PexelsProvider in names
    if pixabay_key:
        assert PixabayProvider in names
