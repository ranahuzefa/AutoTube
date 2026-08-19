"""Tests for AI image generation scaffolding."""

from __future__ import annotations

import pytest

from autotube.ai.image.config import AIImageConfig
from autotube.ai.image.providers import GeneratedImage
from autotube.ai.image.registry import (
    AIImageProviderRegistry,
    AIImageProviderSpec,
    default_ai_image_provider_registry,
)
from autotube.config import Settings
from autotube.exceptions import ValidationError


def test_default_registry_is_empty() -> None:
    registry = default_ai_image_provider_registry()
    assert registry.known_ids() == set()
    assert registry.list_all() == []


def test_config_defaults() -> None:
    config = AIImageConfig.from_settings(Settings())
    assert config.enabled is False
    assert config.provider == ""
    assert config.timeout == 60.0


def test_config_errors_empty() -> None:
    assert AIImageConfig.from_settings(Settings()).errors() == []


def test_config_errors_enabled_without_provider() -> None:
    config = AIImageConfig.from_settings(Settings(ai_image_enabled=True))
    assert any("provider" in e for e in config.errors())


def test_future_provider_registration() -> None:
    registry = AIImageProviderRegistry()

    class _FakeProvider:
        def __init__(self, config):
            self.config = config

        def generate(self, prompt, *, width=None, height=None):
            return GeneratedImage(url="https://x", prompt=prompt)

    registry.register(
        AIImageProviderSpec(
            provider_id="future",
            display_name="Future",
            default_base_url="https://future.example/v1",
            default_model="future-model",
            default_api_key_env_var="FUTURE_IMAGE_KEY",
            adapter_factory=_FakeProvider,
        )
    )
    config = AIImageConfig.from_settings(
        Settings(
            ai_image_enabled=True,
            ai_image_provider="future",
            ai_image_model="future-model",
            ai_image_api_key_env_var="FUTURE_IMAGE_KEY",
            ai_image_base_url="https://future.example/v1",
        )
    )
    provider = registry.build_provider(config)
    assert isinstance(provider, _FakeProvider)


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValidationError):
        default_ai_image_provider_registry().get("unknown")


def test_build_provider_without_adapter_raises() -> None:
    registry = AIImageProviderRegistry()
    registry.register(
        AIImageProviderSpec(
            provider_id="no-adapter",
            display_name="No Adapter",
            default_base_url="https://x",
            default_model="m",
            default_api_key_env_var="K",
        )
    )
    config = AIImageConfig.from_settings(
        Settings(ai_image_enabled=True, ai_image_provider="no-adapter")
    )
    with pytest.raises(ValidationError):
        registry.build_provider(config)
