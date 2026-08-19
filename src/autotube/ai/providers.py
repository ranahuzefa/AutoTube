"""OpenAI-compatible HTTP provider for AI keyword generation."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, Protocol

from ..exceptions import (
    AICancelledError,
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AIResponseError,
)
from ..constants import DEFAULT_AI_MAX_BACKOFF_SECONDS
from .config import AIConfig
from .models import AISegmentInput, AISegmentOutput
from .prompts import build_messages

_RETRYABLE_STATUS = {408, 500, 502, 503, 504}

SleepFunc = Callable[[float, threading.Event | None], None]


def default_sleep(delay: float, cancel_event: threading.Event | None = None) -> None:
    if cancel_event is not None:
        if cancel_event.wait(delay):
            raise AICancelledError("AI request cancelled.")
    else:
        time.sleep(delay)


class AIKeywordProvider(Protocol):
    def generate(
        self,
        segments: list[AISegmentInput],
        *,
        cancel_event: threading.Event | None = None,
    ) -> list[AISegmentOutput]:
        ...


class _RedactedHeaders(dict):
    """Header mapping whose repr masks Authorization values."""

    def __repr__(self) -> str:
        redacted = {
            key: "***" if key.lower() == "authorization" else value
            for key, value in self.items()
        }
        return repr(redacted)

    def __str__(self) -> str:
        return self.__repr__()


class AIHTTPClient:
    """Minimal stdlib JSON POST client with typed AI errors."""

    def post_json(
        self,
        url: str,
        payload: dict,
        *,
        headers: dict[str, str],
        timeout: float,
    ) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = _RedactedHeaders(headers)
        request = urllib.request.Request(
            url, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry_after = _parse_retry_after(exc.headers)
                raise AIRateLimitError(
                    f"AI provider rate limited: HTTP {exc.code}.",
                    retry_after=retry_after,
                ) from exc
            if exc.code in _RETRYABLE_STATUS:
                raise AIProviderError(
                    f"AI provider request failed: HTTP {exc.code}.", retryable=True
                ) from exc
            raise AIProviderError(
                f"AI provider request failed: HTTP {exc.code}.", retryable=False
            ) from exc
        except urllib.error.URLError as exc:
            raise AIProviderError(
                f"AI provider network error: {exc.reason}", retryable=True
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise AIProviderError("AI provider request timed out.", retryable=True) from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AIResponseError("Malformed AI provider response.") from exc

        if not isinstance(data, dict):
            raise AIResponseError("Malformed AI provider response.")
        return data


def _parse_retry_after(headers) -> float | None:
    value = headers.get("Retry-After") if headers else None
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


class OpenAICompatibleProvider:
    """Call an OpenAI-compatible chat completions endpoint via urllib."""

    def __init__(
        self,
        config: AIConfig,
        api_key: str | None = None,
        client: AIHTTPClient | None = None,
        sleep_func: SleepFunc = default_sleep,
    ) -> None:
        self.config = config
        self._api_key = api_key
        self._client = client or AIHTTPClient()
        self._sleep = sleep_func

    def _resolve_key(self) -> str:
        if self._api_key is not None:
            return self._api_key.strip()
        return os.environ.get(self.config.api_key_env_var, "").strip()

    def generate(
        self,
        segments: list[AISegmentInput],
        *,
        cancel_event: threading.Event | None = None,
    ) -> list[AISegmentOutput]:
        self._check_cancel(cancel_event)

        api_key = self._resolve_key()
        if not api_key:
            raise AIConfigurationError("AI API key is missing.")

        payload = {
            "model": self.config.model,
            "messages": build_messages(segments),
            "temperature": self.config.temperature,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.config.max_retries + 1):
            self._check_cancel(cancel_event)
            try:
                data = self._client.post_json(
                    self.config.base_url,
                    payload,
                    headers=headers,
                    timeout=self.config.timeout,
                )
                return self._parse_response(data)
            except AICancelledError:
                raise
            except AIRateLimitError as exc:
                if attempt >= self.config.max_retries:
                    raise
                delay = exc.retry_after if exc.retry_after is not None else _backoff(attempt)
                self._sleep(delay, cancel_event)
            except AIProviderError as exc:
                if not exc.retryable or attempt >= self.config.max_retries:
                    raise
                self._sleep(_backoff(attempt), cancel_event)
            except AIResponseError:
                raise

        raise AIProviderError(
            "AI provider failed after retries.", retryable=False
        )

    def _parse_response(self, data: dict) -> list[AISegmentOutput]:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AIResponseError("AI provider response has no choices.")
        first = choices[0]
        if not isinstance(first, dict):
            raise AIResponseError("AI provider choice is malformed.")
        message = first.get("message")
        if not isinstance(message, dict):
            raise AIResponseError("AI provider message is malformed.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIResponseError("AI provider content is empty.")

        parsed = _parse_content_json(content)
        segments = parsed.get("segments")
        if not isinstance(segments, list):
            raise AIResponseError("AI provider segments field is missing.")

        out: list[AISegmentOutput] = []
        for item in segments:
            if not isinstance(item, dict):
                continue
            segment_id = item.get("segment_id")
            if not isinstance(segment_id, str) or not segment_id:
                continue
            start = _as_float(item.get("start"))
            end = _as_float(item.get("end"))
            keywords = item.get("keywords")
            if not isinstance(keywords, list):
                continue
            keyword_strings = [k for k in keywords if isinstance(k, str)]
            out.append(
                AISegmentOutput(
                    segment_id=segment_id,
                    start=start,
                    end=end,
                    keywords=keyword_strings,
                )
            )
        return out

    @staticmethod
    def _check_cancel(cancel_event: threading.Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise AICancelledError("AI request cancelled.")


def _parse_content_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
        elif text.startswith("JSON"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIResponseError("AI provider content is not valid JSON.") from exc
    if not isinstance(data, dict):
        raise AIResponseError("AI provider content is not a JSON object.")
    return data


def _as_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _backoff(attempt: int) -> float:
    return min(2.0 ** attempt, DEFAULT_AI_MAX_BACKOFF_SECONDS)
