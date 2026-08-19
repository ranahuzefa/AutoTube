"""Validation of AI-generated keywords."""

from __future__ import annotations

import re

from ..stock.constants import STOPWORDS
from .config import AIConfig

_ALPHA_RE = re.compile(r"[a-zA-Z]")
_PUNCT_EDGE_RE = re.compile(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$")


def _strip_edge_punctuation(value: str) -> str:
    return _PUNCT_EDGE_RE.sub("", value).strip()


def validate_ai_keywords(raw: list[object], config: AIConfig) -> list[str]:
    """Normalize, filter, deduplicate, and bound AI keyword candidates."""
    seen: set[str] = set()
    out: list[str] = []

    for item in raw:
        value = _strip_edge_punctuation(str(item)).lower()
        if not value:
            continue
        if value.startswith("#"):
            value = value[1:].strip()
        if not value:
            continue
        if value.isdigit() or not _ALPHA_RE.search(value):
            continue
        if len(value) < 2:
            continue
        if len(value) > config.max_keyword_chars:
            continue
        if all(token in STOPWORDS for token in value.split()):
            continue
        if value in seen:
            continue

        seen.add(value)
        out.append(value)
        if len(out) >= config.max_keywords:
            break

    return out
