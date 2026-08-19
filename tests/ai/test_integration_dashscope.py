"""Opt-in real DashScope/Qwen AI provider integration test.

Skipped unless AUTOTUBE_RUN_AI_TESTS=1 and DASHSCOPE_API_KEY is present.
"""

from __future__ import annotations

import os

import pytest

from autotube.ai.config import AIConfig
from autotube.ai.models import AISegmentInput
from autotube.ai.providers import OpenAICompatibleProvider
from autotube.config import Settings

pytestmark = [pytest.mark.integration, pytest.mark.ai]


@pytest.fixture
def ai_enabled() -> bool:
    return os.environ.get("AUTOTUBE_RUN_AI_TESTS") == "1"


@pytest.fixture
def require_ai(ai_enabled: bool):
    if not ai_enabled:
        pytest.skip("AI integration tests not enabled")


def test_dashscope_generate(require_ai) -> None:
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not key:
        pytest.skip("DASHSCOPE_API_KEY not set")

    config = AIConfig.from_settings(
        Settings(
            ai_enabled=True,
            ai_provider="dashscope",
            ai_model="qwen3.7-plus",
            ai_api_key_env_var="DASHSCOPE_API_KEY",
            ai_base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
    )
    provider = OpenAICompatibleProvider(config, api_key=key)
    inputs = [
        AISegmentInput(
            segment_id="a", text="a sunset over the ocean", start=0.0, end=2.0
        )
    ]
    outputs = provider.generate(inputs)
    assert isinstance(outputs, list)
    assert outputs
    assert outputs[0].segment_id == "a"
    assert outputs[0].keywords
