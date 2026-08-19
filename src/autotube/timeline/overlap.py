"""Overlap detection for timeline items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OverlapPair:
    first: Any
    second: Any


def find_overlaps(items: list) -> list[OverlapPair]:
    """Return overlapping pairs among items with ``start``/``end`` attributes."""
    ordered = sorted(items, key=lambda item: (item.start, item.end))
    overlaps: list[OverlapPair] = []
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            a = ordered[i]
            b = ordered[j]
            if b.start >= a.end:
                break
            overlaps.append(OverlapPair(a, b))
    return overlaps
