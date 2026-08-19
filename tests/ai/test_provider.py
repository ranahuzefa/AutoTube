"""Tests for the OpenAI-compatible provider with injected HTTP clients."""

from __future__ import annotations

import threading

import pytest

from autotube.ai.config import AIConfig
from autotube.ai.models import AISegmentInput
from autotube.ai.providers import AIHTTPClient, OpenAICompatibleProvider
from autotube.config import Settings
from autotube.exceptions import (
    AICancelledError,
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AIResponseError,
)


def _config(**kwargs) -> AIConfig:
    return AIConfig.from_settings(Settings(**kwargs))


def _input(segment_id="a") -> AISegmentInput:
    return AISegmentInput(segment_id=segment_id, text="ocean waves", start=0.0, end=1.0)


def _content_payload(segments):
    return {"choices": [{"message": {"content": _json_content(segments)}}]}


def _json_content(segments):
    import json

    return json.dumps({"segments": segments})


class _FakeClient:
    def __init__(self, payload=None, exc=None):
        self.payload = payload
        self.exc = exc
        self.calls = 0

    def post_json(self, url, payload, *, headers, timeout):
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return self.payload


def test_success() -> None:
    payload = _content_payload(
        [{"segment_id": "a", "start": 0.0, "end": 1.0, "keywords": ["ocean", "waves"]}]
    )
    provider = OpenAICompatibleProvider(_config(), api_key="key", client=_FakeClient(payload))
    out = provider.generate([_input()])
    assert out[0].segment_id == "a"
    assert out[0].keywords == ["ocean", "waves"]


def test_posts_to_openrouter_with_bearer_and_json_headers() -> None:
    captured = {}

    class _CapturingClient:
        def post_json(self, url, payload, *, headers, timeout):
            captured["url"] = url
            captured["payload"] = payload
            captured["headers"] = headers
            captured["timeout"] = timeout
            return _content_payload(
                [{"segment_id": "a", "start": 0.0, "end": 1.0, "keywords": ["ocean"]}]
            )

    provider = OpenAICompatibleProvider(_config(), api_key="key", client=_CapturingClient())
    provider.generate([_input()])
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer key"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["payload"]["model"] == "deepseek/deepseek-v4-flash-0731"
    assert "messages" in captured["payload"]
    assert "temperature" in captured["payload"]


def test_resolves_key_from_openrouter_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    provider = OpenAICompatibleProvider(_config(), client=_FakeClient())
    assert provider._resolve_key() == "env-key"


def test_headers_repr_redacts_authorization() -> None:
    from autotube.ai.providers import _RedactedHeaders

    headers = _RedactedHeaders({"Authorization": "Bearer secret", "Content-Type": "application/json"})
    assert "secret" not in repr(headers)
    assert "***" in repr(headers)
    assert "application/json" in repr(headers)


def test_missing_key_raises_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = OpenAICompatibleProvider(_config(), client=_FakeClient())
    with pytest.raises(AIConfigurationError):
        provider.generate([_input()])


def test_malformed_body_raises_response_error() -> None:
    provider = OpenAICompatibleProvider(
        _config(), api_key="key", client=_FakeClient({"unexpected": True})
    )
    with pytest.raises(AIResponseError):
        provider.generate([_input()])


def test_429_retry_after_exhausted() -> None:
    class _RateLimited:
        def post_json(self, url, payload, *, headers, timeout):
            raise AIRateLimitError("rate", retry_after=0.0)

    provider = OpenAICompatibleProvider(
        _config(ai_max_retries=1), api_key="key", client=_RateLimited(), sleep_func=lambda d, e: None
    )
    with pytest.raises(AIRateLimitError):
        provider.generate([_input()])


def test_retryable_provider_error_retries_then_raises() -> None:
    calls = {"n": 0}

    class _Flaky:
        def post_json(self, url, payload, *, headers, timeout):
            calls["n"] += 1
            raise AIProviderError("down", retryable=True)

    provider = OpenAICompatibleProvider(
        _config(ai_max_retries=2), api_key="key", client=_Flaky(), sleep_func=lambda d, e: None
    )
    with pytest.raises(AIProviderError):
        provider.generate([_input()])
    assert calls["n"] == 3


def test_non_retryable_error_does_not_retry() -> None:
    calls = {"n": 0}

    class _NonRetryable:
        def post_json(self, url, payload, *, headers, timeout):
            calls["n"] += 1
            raise AIProviderError("bad request", retryable=False)

    provider = OpenAICompatibleProvider(
        _config(ai_max_retries=3), api_key="key", client=_NonRetryable(), sleep_func=lambda d, e: None
    )
    with pytest.raises(AIProviderError):
        provider.generate([_input()])
    assert calls["n"] == 1


def test_cancellation_before_request() -> None:
    client = _FakeClient(_content_payload([]))
    provider = OpenAICompatibleProvider(_config(), api_key="key", client=client)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(AICancelledError):
        provider.generate([_input()], cancel_event=cancel)
    assert client.calls == 0


def test_cancellation_during_sleep() -> None:
    def _cancelling_sleep(delay, cancel_event):
        raise AICancelledError("cancelled")

    class _Flaky:
        def post_json(self, url, payload, *, headers, timeout):
            raise AIProviderError("down", retryable=True)

    provider = OpenAICompatibleProvider(
        _config(ai_max_retries=3), api_key="key", client=_Flaky(), sleep_func=_cancelling_sleep
    )
    with pytest.raises(AICancelledError):
        provider.generate([_input()])


def test_exception_message_does_not_contain_key() -> None:
    from autotube.ai.providers import _parse_retry_after

    assert _parse_retry_after({"Retry-After": "5"}) == 5.0
    assert _parse_retry_after({"Retry-After": "bad"}) is None
    assert _parse_retry_after({}) is None


def _dashscope_config() -> AIConfig:
    return AIConfig.from_settings(
        Settings(
            ai_enabled=True,
            ai_provider="dashscope",
            ai_model="qwen3.7-plus",
            ai_api_key_env_var="DASHSCOPE_API_KEY",
            ai_base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
    )


def test_dashscope_posts_to_dashscope_with_headers_and_payload() -> None:
    captured = {}

    class _CapturingClient:
        def post_json(self, url, payload, *, headers, timeout):
            captured["url"] = url
            captured["payload"] = payload
            captured["headers"] = headers
            captured["timeout"] = timeout
            return _content_payload(
                [{"segment_id": "a", "start": 0.0, "end": 1.0, "keywords": ["ocean"]}]
            )

    provider = OpenAICompatibleProvider(
        _dashscope_config(), api_key="key", client=_CapturingClient()
    )
    provider.generate([_input()])
    assert (
        captured["url"]
        == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
    )
    assert captured["headers"]["Authorization"] == "Bearer key"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["payload"]["model"] == "qwen3.7-plus"
    assert "messages" in captured["payload"]
    assert "temperature" in captured["payload"]


def test_dashscope_resolves_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "env-key")
    provider = OpenAICompatibleProvider(_dashscope_config(), client=_FakeClient())
    assert provider._resolve_key() == "env-key"


def test_dashscope_missing_key_raises_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    provider = OpenAICompatibleProvider(_dashscope_config(), client=_FakeClient())
    with pytest.raises(AIConfigurationError):
        provider.generate([_input()])


def test_dashscope_parses_qwen_response() -> None:
    payload = _content_payload(
        [{"segment_id": "a", "start": 0.0, "end": 1.0, "keywords": ["ocean", "waves"]}]
    )
    provider = OpenAICompatibleProvider(
        _dashscope_config(), api_key="key", client=_FakeClient(payload)
    )
    out = provider.generate([_input()])
    assert out[0].segment_id == "a"
    assert out[0].keywords == ["ocean", "waves"]


def test_dashscope_authorization_redaction() -> None:
    from autotube.ai.providers import _RedactedHeaders

    headers = _RedactedHeaders(
        {
            "Authorization": "Bearer secret-dashscope",
            "Content-Type": "application/json",
        }
    )
    assert "secret-dashscope" not in repr(headers)
    assert "***" in repr(headers)
