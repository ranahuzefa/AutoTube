"""Tests for the guarded AI keyword engine."""

from __future__ import annotations

import threading

import pytest

from autotube.ai.config import AIConfig
from autotube.ai.engine import AIKeywordEngine
from autotube.ai.models import AISegmentOutput
from autotube.config import Settings
from autotube.exceptions import AICancelledError
from autotube.state import KeywordSource, SegmentState


def _config(**kwargs) -> AIConfig:
    return AIConfig.from_settings(Settings(**kwargs))


def _seg(segment_id, text="ocean waves", start=0.0, end=1.0) -> SegmentState:
    return SegmentState(segment_id=segment_id, text=text, start=start, end=end)


class _FakeProvider:
    def __init__(self, outputs=None, exc=None):
        self.outputs = outputs or []
        self.exc = exc
        self.calls = 0

    def generate(self, segments, *, cancel_event=None):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.outputs


def test_disabled_uses_local() -> None:
    engine = AIKeywordEngine(_config(ai_enabled=False), provider=_FakeProvider())
    results = engine.generate_keywords_batch([_seg("a", "ocean waves sunset")])
    assert results["a"].source == KeywordSource.LOCAL
    assert results["a"].keywords


def test_invalid_config_uses_local() -> None:
    engine = AIKeywordEngine(
        _config(ai_enabled=True, ai_model=""), provider=_FakeProvider()
    )
    results = engine.generate_keywords_batch([_seg("a")])
    assert results["a"].source == KeywordSource.LOCAL


def test_provider_failure_falls_back_local() -> None:
    engine = AIKeywordEngine(
        _config(ai_enabled=True, ai_max_retries=0),
        provider=_FakeProvider(exc=RuntimeError("boom")),
    )
    results = engine.generate_keywords_batch([_seg("a", "ocean waves")])
    assert results["a"].source == KeywordSource.LOCAL
    assert results["a"].keywords


def test_valid_ai_output() -> None:
    outputs = [AISegmentOutput("a", 0.0, 1.0, ["ocean", "waves", "ocean"])]
    engine = AIKeywordEngine(_config(ai_enabled=True), provider=_FakeProvider(outputs))
    results = engine.generate_keywords_batch([_seg("a")])
    assert results["a"].source == KeywordSource.AI
    assert results["a"].keywords == ["ocean", "waves"]


def test_missing_output_falls_back_local() -> None:
    engine = AIKeywordEngine(
        _config(ai_enabled=True), provider=_FakeProvider(outputs=[])
    )
    results = engine.generate_keywords_batch([_seg("a", "ocean waves")])
    assert results["a"].source == KeywordSource.LOCAL


def test_timestamp_mismatch_falls_back_local() -> None:
    outputs = [AISegmentOutput("a", 99.0, 100.0, ["ocean"])]
    engine = AIKeywordEngine(_config(ai_enabled=True), provider=_FakeProvider(outputs))
    results = engine.generate_keywords_batch([_seg("a")])
    assert results["a"].source == KeywordSource.LOCAL


def test_invalid_keywords_falls_back_local() -> None:
    outputs = [AISegmentOutput("a", 0.0, 1.0, ["the", "and", "of"])]
    engine = AIKeywordEngine(_config(ai_enabled=True), provider=_FakeProvider(outputs))
    results = engine.generate_keywords_batch([_seg("a")])
    assert results["a"].source == KeywordSource.LOCAL


def test_batching_respects_batch_size() -> None:
    outputs = [AISegmentOutput("a", 0.0, 1.0, ["ocean"]), AISegmentOutput("b", 1.0, 2.0, ["sky"])]
    provider = _FakeProvider(outputs)
    engine = AIKeywordEngine(_config(ai_enabled=True, ai_batch_size=1), provider=provider)
    results = engine.generate_keywords_batch([_seg("a", start=0.0), _seg("b", start=1.0, end=2.0)])
    assert provider.calls == 2
    assert results["a"].source == KeywordSource.AI
    assert results["b"].source == KeywordSource.AI


def test_single_segment_generate_keywords() -> None:
    outputs = [AISegmentOutput("a", 0.0, 1.0, ["ocean"])]
    engine = AIKeywordEngine(_config(ai_enabled=True), provider=_FakeProvider(outputs))
    assert engine.generate_keywords(_seg("a")) == ["ocean"]


def test_cancellation_propagates() -> None:
    engine = AIKeywordEngine(_config(ai_enabled=True), provider=_FakeProvider())
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(AICancelledError):
        engine.generate_keywords_batch([_seg("a")], cancel_event=cancel)


def test_dashscope_provider_failure_falls_back_local() -> None:
    engine = AIKeywordEngine(
        _config(
            ai_enabled=True,
            ai_provider="dashscope",
            ai_model="qwen3.7-plus",
            ai_api_key_env_var="DASHSCOPE_API_KEY",
            ai_base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        ),
        provider=_FakeProvider(exc=RuntimeError("boom")),
    )
    results = engine.generate_keywords_batch([_seg("a", "ocean waves")])
    assert results["a"].source == KeywordSource.LOCAL
    assert results["a"].keywords
