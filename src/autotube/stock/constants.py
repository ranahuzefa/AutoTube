"""Stock keyword/download constants and helpers."""

from __future__ import annotations

import hashlib
import re

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def safe_filename(name: str, max_length: int = 120) -> str:
    """Return a Windows-safe filename derived from ``name``."""
    cleaned = INVALID_FILENAME_CHARS.sub("_", name)
    cleaned = cleaned.rstrip(". ")
    cleaned = cleaned.strip()
    if not cleaned:
        cleaned = hashlib.sha1(name.encode("utf-8", errors="replace")).hexdigest()[:16]
    if len(cleaned) > max_length:
        stem = cleaned[: max_length - 16].rstrip(". ")
        digest = hashlib.sha1(cleaned.encode("utf-8", errors="replace")).hexdigest()[:16]
        cleaned = f"{stem}_{digest}"
    return cleaned


# Small deterministic English stopword list used by local keyword generation.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "of", "to",
    "in", "on", "at", "by", "for", "with", "about", "into", "through",
    "during", "before", "after", "above", "below", "up", "down", "out",
    "off", "over", "under", "again", "further", "once", "here", "there",
    "when", "where", "why", "how", "all", "any", "both", "each", "few",
    "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "can", "will", "just",
    "should", "now", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "this", "that", "these",
    "those", "it", "its", "we", "you", "they", "them", "their", "he",
    "she", "his", "her", "what", "which", "who", "whom", "me", "my",
    "your", "our", "us", "i", "as", "from",
}
