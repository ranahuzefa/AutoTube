"""Deterministic local keyword generation."""

from __future__ import annotations

import re

from ..constants import DEFAULT_STOCK_MAX_KEYWORDS
from ..state import SegmentState
from .constants import STOPWORDS

_TOKEN_RE = re.compile(r"[^a-zA-Z0-9]+")


def normalize_keywords(
    keywords: list[str], max_keywords: int = DEFAULT_STOCK_MAX_KEYWORDS
) -> list[str]:
    """Trim, lowercase, deduplicate, and bound a keyword list."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in keywords:
        token = (raw or "").strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= max_keywords:
            break
    return out


class LocalKeywordService:
    """Generate visual keywords locally without network or randomness."""

    def generate_keywords(self, segment: SegmentState) -> list[str]:
        text = (segment.text or "").strip().lower()
        if not text:
            return []

        tokens = [t for t in _TOKEN_RE.split(text) if t]
        keywords = [
            t
            for t in tokens
            if t not in STOPWORDS and len(t) > 1 and not t.isdigit()
        ]
        keywords = normalize_keywords(keywords)

        if len(keywords) < 2:
            fallback = " ".join(tokens).strip()
            if fallback:
                return [fallback[:80]]
            return []

        return keywords
