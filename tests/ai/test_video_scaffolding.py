"""Tests for AI video generation scaffolding."""

from __future__ import annotations

import pytest

from autotube.ai.video.config import AIVideoConfig
from autotube.ai.video.providers import GeneratedVideo
from autotube.ai.video.registry import (
    AIVideoProviderRegistry,
    AIVideoProviderSpec,
    default_ai_video_provider_registry,
)
from autotube.config import Settings
from autotube.exceptions import ValidationError


def test_default_registry_is_empty() -> None:
    registry = default_ai_video_provider_registry()
    assert registry.known_ids() == set()
    assert registry.list_all() == []


def test_config_defaults() -> None:
    config = AIVideoConfig.from_settings(Settings())
    assert config.enabled is False
    assert config.provider == ""
    assert config.timeout == 120.0


def test_config_errors_empty() -> None:
    assert AIVideoConfig.from_settings(Settings()).errors() == []


def test_config_errors_enabled_without_provider() -> None:
    config = AIVideoConfig.from_settings(Settings(ai_video_enabled=True))
    assert any("provider" in e for e in config.errors())


def test_future_provider_registration() -> None:
    registry = AIVideoProviderRegistry()

    class _FakeProvider:
        def __init__(self, config):
            self.config = config

        def generate(self, prompt, *, width=None, height=None, duration=None):
            return GeneratedVideo(url="https://x", prompt=prompt)

    registry.register(
        AIVideoProviderSpec(
            provider_id="future",
            display_name="Future",
            default_base_url="https://future.example/v1",
            default_model="future-model",
            default_api_key_env_var="FUTURE_VIDEO_KEY",
            adapter_factory=_FakeProvider,
        )
    )
    config = AIVideoConfig.from_settings(
        Settings(
            ai_video_enabled=True,
            ai_video_provider="future",
            ai_video_model="future-model",
            ai_video_api_key_env_var="FUTURE_VIDEO_KEY",
            ai_video_base_url="https://future.example/v1",
        )
    )
    provider = registry.build_provider(config)
    assert isinstance(provider, _FakeProvider)


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValidationError):
        default_ai_video_provider_registry().get("unknown")


def test_build_provider_without_adapter_raises() -> None:
    registry = AIVideoProviderRegistry()
    registry.register(
        AIVideoProviderSpec(
            provider_id="no-adapter",
            display_name="No Adapter",
            default_base_url="https://x",
            default_model="m",
            default_api_key_env_var="K",
        )
    )
    config = AIVideoConfig.from_settings(
        Settings(ai_video_enabled=True, ai_video_provider="no-adapter")
    )
    with pytest.raises(ValidationError):
        registry.build_provider(config)
