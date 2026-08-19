"""Stock provider factory with env-first API key resolution."""

from __future__ import annotations

import os

from ..config import Settings
from .providers import StockProviderProtocol
from .registry import StockProviderSpec, default_stock_provider_registry


def _resolve_api_key(spec: StockProviderSpec, settings: Settings) -> str:
    """Resolve a provider API key without logging or persisting it.

    Precedence: standard env var, then legacy ``AUTOTUBE_<FIELD>`` override,
    then the legacy persisted Settings field.
    """
    standard = os.environ.get(spec.default_api_key_env_var, "")
    if standard.strip():
        return standard.strip()

    if spec.settings_key_field:
        legacy_env = os.environ.get(
            f"AUTOTUBE_{spec.settings_key_field.upper()}", ""
        )
        if legacy_env.strip():
            return legacy_env.strip()
        return str(getattr(settings, spec.settings_key_field, "")).strip()

    return ""


def build_stock_providers(settings: Settings) -> list[StockProviderProtocol]:
    """Build enabled stock providers in ``settings.stock_providers`` order.

    Unknown provider IDs and providers with no resolvable API key are skipped.
    """
    registry = default_stock_provider_registry()
    providers: list[StockProviderProtocol] = []
    for provider_id in settings.stock_providers:
        if provider_id not in registry.known_ids():
            continue
        spec = registry.get(provider_id)
        api_key = _resolve_api_key(spec, settings)
        if not api_key:
            continue
        providers.append(registry.build_provider(provider_id, api_key))
    return providers
