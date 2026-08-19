"""Tests for the AI provider registry."""

from __future__ import annotations

import pytest

from autotube.ai.config import AIConfig
from autotube.ai.providers import OpenAICompatibleProvider
from autotube.ai.registry import (
    AIProviderRegistry,
    AIProviderSpec,
    default_ai_provider_registry,
)
from autotube.config import Settings
from autotube.exceptions import ValidationError


def test_default_registry_contains_builtin_providers() -> None:
    registry = default_ai_provider_registry()
    assert registry.known_ids() == {"openai_compatible", "dashscope"}


def test_openrouter_spec_defaults() -> None:
    spec = default_ai_provider_registry().get("openai_compatible")
    assert spec.display_name == "OpenRouter"
    assert spec.default_model == "deepseek/deepseek-v4-flash-0731"
    assert spec.default_api_key_env_var == "OPENROUTER_API_KEY"
    assert spec.default_base_url == "https://openrouter.ai/api/v1/chat/completions"


def test_dashscope_spec_defaults() -> None:
    spec = default_ai_provider_registry().get("dashscope")
    assert spec.display_name == "Alibaba Cloud DashScope"
    assert spec.default_model == "qwen3.7-plus"
    assert spec.default_api_key_env_var == "DASHSCOPE_API_KEY"
    assert (
        spec.default_base_url
        == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
    )


def test_build_provider_openrouter() -> None:
    config = AIConfig.from_settings(Settings(ai_enabled=True))
    provider = default_ai_provider_registry().build_provider(config)
    assert isinstance(provider, OpenAICompatibleProvider)


def test_build_provider_dashscope() -> None:
    config = AIConfig.from_settings(
        Settings(
            ai_enabled=True,
            ai_provider="dashscope",
            ai_model="qwen3.7-plus",
            ai_api_key_env_var="DASHSCOPE_API_KEY",
            ai_base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
    )
    provider = default_ai_provider_registry().build_provider(config)
    assert isinstance(provider, OpenAICompatibleProvider)


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValidationError):
        default_ai_provider_registry().get("unknown")


def test_future_provider_registration() -> None:
    registry = AIProviderRegistry()
    registry.register(
        AIProviderSpec(
            provider_id="future",
            display_name="Future",
            default_base_url="https://future.example/v1",
            default_model="future-model",
            default_api_key_env_var="FUTURE_KEY",
        )
    )
    spec = registry.get("future")
    assert spec.display_name == "Future"
    config = AIConfig.from_settings(
        Settings(
            ai_enabled=True,
            ai_provider="future",
            ai_model="future-model",
            ai_api_key_env_var="FUTURE_KEY",
            ai_base_url="https://future.example/v1",
        )
    )
    assert isinstance(registry.build_provider(config), OpenAICompatibleProvider)
