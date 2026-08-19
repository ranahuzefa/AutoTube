"""Tests for deterministic local keyword generation."""

from __future__ import annotations

from autotube.state import SegmentState
from autotube.stock.keywords import LocalKeywordService, normalize_keywords


def test_generates_deterministic_keywords() -> None:
    service = LocalKeywordService()
    seg = SegmentState.new("a beautiful sunset over the ocean", 0.0, 1.0)
    assert service.generate_keywords(seg) == service.generate_keywords(seg)


def test_drops_stopwords_and_short_tokens() -> None:
    service = LocalKeywordService()
    seg = SegmentState.new("the cat and a dog are running", 0.0, 1.0)
    keywords = service.generate_keywords(seg)
    assert "the" not in keywords
    assert "and" not in keywords
    assert "a" not in keywords
    assert keywords


def test_fallback_when_too_few_keywords() -> None:
    service = LocalKeywordService()
    seg = SegmentState.new("the and", 0.0, 1.0)
    keywords = service.generate_keywords(seg)
    assert keywords
    assert len(keywords) <= 1


def test_empty_text_returns_empty() -> None:
    service = LocalKeywordService()
    seg = SegmentState.new("", 0.0, 1.0)
    assert service.generate_keywords(seg) == []


def test_normalize_keywords_dedupes_and_bounds() -> None:
    assert normalize_keywords(["  Cat ", "cat", "Dog", "Bird", "Fish", "Fox"], 4) == [
        "cat",
        "dog",
        "bird",
        "fish",
    ]
