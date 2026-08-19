"""Stock service layer: keywords, providers, download, cache, workflow."""

from .cache import AssetCache
from .download import DownloadManager, DownloadResult
from .factory import build_stock_providers
from .keywords import LocalKeywordService, normalize_keywords
from .manager import StockManager
from .providers import PexelsProvider, PixabayProvider
from .registry import (
    StockProviderRegistry,
    StockProviderSpec,
    default_stock_provider_registry,
)
from .scoring import StockScorer, filter_candidates
from .types import (
    StockFilter,
    StockProvider,
    StockSearchResult,
    StockVideo,
)
from .workflow import StockWorkflow

__all__ = [
    "AssetCache",
    "DownloadManager",
    "DownloadResult",
    "LocalKeywordService",
    "PexelsProvider",
    "PixabayProvider",
    "StockFilter",
    "StockManager",
    "StockProvider",
    "StockProviderRegistry",
    "StockProviderSpec",
    "StockScorer",
    "StockSearchResult",
    "StockVideo",
    "StockWorkflow",
    "build_stock_providers",
    "default_stock_provider_registry",
    "filter_candidates",
    "normalize_keywords",
]
