"""Dataclasses for AI keyword generation."""

from __future__ import annotations

from dataclasses import dataclass

from ..state import KeywordSource


@dataclass
class AISegmentInput:
    """One transcript segment with optional neighboring context."""

    segment_id: str
    text: str
    start: float
    end: float
    previous_text: str | None = None
    next_text: str | None = None


@dataclass
class AISegmentOutput:
    """Parsed AI output for one segment before validation."""

    segment_id: str
    start: float
    end: float
    keywords: list[str]


@dataclass
class BatchKeywordResult:
    """Validated, per-segment outcome returned to the stock workflow."""

    segment_id: str
    keywords: list[str]
    source: KeywordSource
