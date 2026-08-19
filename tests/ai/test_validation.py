"""Tests for AI keyword validation."""

from __future__ import annotations

from autotube.ai.config import AIConfig
from autotube.ai.validation import validate_ai_keywords
from autotube.config import Settings


def _config(**kwargs) -> AIConfig:
    return AIConfig.from_settings(Settings(**kwargs))


def test_normalizes_and_dedupes() -> None:
    out = validate_ai_keywords(["  Cat ", "CAT", "Dog"], _config())
    assert out == ["cat", "dog"]


def test_bounds_max_keywords() -> None:
    out = validate_ai_keywords(
        ["cat", "dog", "bird", "fish", "fox"], _config(ai_max_keywords=3)
    )
    assert out == ["cat", "dog", "bird"]


def test_max_keyword_length() -> None:
    out = validate_ai_keywords(["a" * 100, "ok"], _config(ai_max_keyword_chars=10))
    assert out == ["ok"]


def test_strips_hashtags_and_punctuation() -> None:
    out = validate_ai_keywords(["#ocean", "!!!waves!!!"], _config())
    assert out == ["ocean", "waves"]


def test_drops_stopwords_and_filler() -> None:
    out = validate_ai_keywords(["the", "and", "of", "123"], _config())
    assert out == []


def test_keeps_multiword_phrases() -> None:
    out = validate_ai_keywords(["golden hour", "city skyline"], _config())
    assert out == ["golden hour", "city skyline"]
