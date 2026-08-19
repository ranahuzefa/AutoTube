"""Tests for AI config additions."""

from __future__ import annotations

import pytest

from autotube.ai.config import AIConfig
from autotube.config import Settings, validate_settings
from autotube.exceptions import ValidationError


def test_settings_ai_defaults() -> None:
    settings = Settings()
    assert settings.ai_enabled is False
    assert settings.ai_provider == "openai_compatible"
    assert settings.ai_model == "deepseek/deepseek-v4-flash-0731"
    assert settings.ai_api_key_env_var == "OPENROUTER_API_KEY"
    assert settings.ai_base_url == "https://openrouter.ai/api/v1/chat/completions"


def test_settings_ai_roundtrip() -> None:
    settings = Settings(
        ai_enabled=True,
        ai_provider="openai_compatible",
        ai_model="gpt-4o",
        ai_api_key_env_var="MY_KEY",
        ai_batch_size=4,
        ai_temperature=0.5,
        ai_max_retries=2,
    )
    restored = Settings.from_dict(settings.to_dict())
    assert restored.ai_enabled is True
    assert restored.ai_model == "gpt-4o"
    assert restored.ai_api_key_env_var == "MY_KEY"
    assert restored.ai_batch_size == 4
    assert restored.ai_temperature == 0.5
    assert restored.ai_max_retries == 2


def test_settings_ai_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOTUBE_AI_ENABLED", "true")
    monkeypatch.setenv("AUTOTUBE_AI_MODEL", "gpt-4o")
    monkeypatch.setenv("AUTOTUBE_AI_BATCH_SIZE", "5")
    monkeypatch.setenv("AUTOTUBE_AI_TIMEOUT", "12.5")
    from autotube.config import load_settings

    settings = load_settings()
    assert settings.ai_enabled is True
    assert settings.ai_model == "gpt-4o"
    assert settings.ai_batch_size == 5
    assert settings.ai_timeout == 12.5


def test_settings_to_dict_has_no_ai_key() -> None:
    data = Settings().to_dict()
    assert "ai_api_key" not in data
    assert "api_key" not in data


def test_legacy_ai_settings_migrate_to_openrouter() -> None:
    data = {
        "ai_model": "deepseek/deepseek-v4-flash",
        "ai_api_key_env_var": "COMMAND_CODE_API_KEY",
        "ai_base_url": "https://api.commandcode.ai/provider/v1/chat/completions",
    }
    settings = Settings.from_dict(data)
    assert settings.ai_model == "deepseek/deepseek-v4-flash-0731"
    assert settings.ai_api_key_env_var == "OPENROUTER_API_KEY"
    assert settings.ai_base_url == "https://openrouter.ai/api/v1/chat/completions"


def test_legacy_ai_settings_partial_migration() -> None:
    data = {
        "ai_model": "deepseek/deepseek-v4-flash",
        "ai_api_key_env_var": "CUSTOM_KEY_ENV",
        "ai_base_url": "https://custom.example.com/v1",
    }
    settings = Settings.from_dict(data)
    assert settings.ai_model == "deepseek/deepseek-v4-flash-0731"
    assert settings.ai_api_key_env_var == "CUSTOM_KEY_ENV"
    assert settings.ai_base_url == "https://custom.example.com/v1"


def test_custom_ai_settings_are_preserved() -> None:
    data = {
        "ai_model": "custom/model",
        "ai_api_key_env_var": "MY_KEY",
        "ai_base_url": "https://custom.example.com/v1",
    }
    settings = Settings.from_dict(data)
    assert settings.ai_model == "custom/model"
    assert settings.ai_api_key_env_var == "MY_KEY"
    assert settings.ai_base_url == "https://custom.example.com/v1"


def test_validate_settings_rejects_bad_ai_temperature() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(ai_temperature=3.0))


def test_validate_settings_rejects_bad_ai_batch_size() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(ai_batch_size=0))


def test_validate_settings_rejects_bad_ai_retries() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(ai_max_retries=-1))


def test_validate_settings_rejects_enabled_without_model() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(ai_enabled=True, ai_model=""))


def test_validate_settings_rejects_enabled_without_key_env() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(ai_enabled=True, ai_api_key_env_var=""))


def test_ai_config_from_settings() -> None:
    config = AIConfig.from_settings(Settings())
    assert config.enabled is False
    assert config.max_keywords == 6
    assert config.batch_size == 8


def test_ai_config_errors() -> None:
    assert AIConfig.from_settings(Settings()).errors() == []
    bad = AIConfig.from_settings(
        Settings(
            ai_enabled=True,
            ai_provider="unknown",
            ai_model="",
            ai_base_url="not-a-url",
        )
    )
    errors = bad.errors()
    assert any("provider" in e for e in errors)
    assert any("model" in e for e in errors)
    assert any("URL" in e for e in errors)


def test_dashscope_ai_settings_roundtrip() -> None:
    settings = Settings(
        ai_enabled=True,
        ai_provider="dashscope",
        ai_model="qwen3.7-plus",
        ai_api_key_env_var="DASHSCOPE_API_KEY",
        ai_base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
    )
    restored = Settings.from_dict(settings.to_dict())
    assert restored.ai_provider == "dashscope"
    assert restored.ai_model == "qwen3.7-plus"
    assert restored.ai_api_key_env_var == "DASHSCOPE_API_KEY"
    assert (
        restored.ai_base_url
        == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
    )


def test_ai_config_errors_accepts_dashscope() -> None:
    config = AIConfig.from_settings(
        Settings(
            ai_enabled=True,
            ai_provider="dashscope",
            ai_model="qwen3.7-plus",
            ai_api_key_env_var="DASHSCOPE_API_KEY",
            ai_base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
    )
    assert config.errors() == []


def test_ai_config_errors_rejects_unknown_provider() -> None:
    config = AIConfig.from_settings(
        Settings(
            ai_enabled=True,
            ai_provider="unknown",
            ai_model="qwen3.7-plus",
            ai_api_key_env_var="DASHSCOPE_API_KEY",
            ai_base_url="https://example.com/v1",
        )
    )
    errors = config.errors()
    assert any("provider" in e for e in errors)


def test_image_video_settings_roundtrip() -> None:
    settings = Settings(
        ai_image_enabled=True,
        ai_image_provider="img",
        ai_image_model="img-model",
        ai_image_api_key_env_var="IMG_KEY",
        ai_image_base_url="https://img.example/v1",
        ai_image_timeout=45.0,
        ai_video_enabled=True,
        ai_video_provider="vid",
        ai_video_model="vid-model",
        ai_video_api_key_env_var="VID_KEY",
        ai_video_base_url="https://vid.example/v1",
        ai_video_timeout=90.0,
    )
    restored = Settings.from_dict(settings.to_dict())
    assert restored.ai_image_enabled is True
    assert restored.ai_image_provider == "img"
    assert restored.ai_image_model == "img-model"
    assert restored.ai_image_timeout == 45.0
    assert restored.ai_video_enabled is True
    assert restored.ai_video_provider == "vid"
    assert restored.ai_video_timeout == 90.0


def test_validate_image_enabled_requires_fields() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(ai_image_enabled=True))


def test_validate_video_enabled_requires_fields() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(ai_video_enabled=True))


def test_validate_image_disabled_allows_empty_fields() -> None:
    validate_settings(Settings(ai_image_enabled=False))


def test_validate_video_timeout_positive() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(ai_video_timeout=0.0))


def test_validate_image_timeout_positive() -> None:
    with pytest.raises(ValidationError):
        validate_settings(Settings(ai_image_timeout=0.0))


def test_image_video_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOTUBE_AI_IMAGE_ENABLED", "true")
    monkeypatch.setenv("AUTOTUBE_AI_IMAGE_TIMEOUT", "33.3")
    monkeypatch.setenv("AUTOTUBE_AI_VIDEO_ENABLED", "true")
    monkeypatch.setenv("AUTOTUBE_AI_VIDEO_TIMEOUT", "44.4")
    from autotube.config import load_settings

    settings = load_settings()
    assert settings.ai_image_enabled is True
    assert settings.ai_image_timeout == 33.3
    assert settings.ai_video_enabled is True
    assert settings.ai_video_timeout == 44.4
