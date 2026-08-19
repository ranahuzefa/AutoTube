"""Tests for overlap detection."""

from __future__ import annotations

from types import SimpleNamespace

from autotube.timeline.overlap import find_overlaps


def _item(start, end, name):
    return SimpleNamespace(start=start, end=end, name=name)


def test_no_overlap() -> None:
    items = [_item(0, 1, "a"), _item(1, 2, "b")]
    assert find_overlaps(items) == []


def test_overlap_detected() -> None:
    items = [_item(10, 15, "a"), _item(12, 18, "b")]
    overlaps = find_overlaps(items)
    assert len(overlaps) == 1
    assert {overlaps[0].first.name, overlaps[0].second.name} == {"a", "b"}


def test_partial_overlap() -> None:
    items = [_item(0, 5, "a"), _item(4, 6, "b"), _item(10, 12, "c")]
    overlaps = find_overlaps(items)
    assert len(overlaps) == 1
