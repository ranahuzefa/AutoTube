"""Tests for the AI keyword service factory."""

from __future__ import annotations

from autotube.ai.engine import AIKeywordEngine
from autotube.ai.factory import build_keyword_service
from autotube.config import Settings
from autotube.stock.keywords import LocalKeywordService


def test_disabled_returns_local() -> None:
    assert isinstance(build_keyword_service(Settings()), LocalKeywordService)


def test_enabled_returns_engine() -> None:
    assert isinstance(build_keyword_service(Settings(ai_enabled=True)), AIKeywordEngine)


def test_enabled_dashscope_returns_engine() -> None:
    service = build_keyword_service(
        Settings(
            ai_enabled=True,
            ai_provider="dashscope",
            ai_model="qwen3.7-plus",
            ai_api_key_env_var="DASHSCOPE_API_KEY",
            ai_base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
    )
    assert isinstance(service, AIKeywordEngine)
