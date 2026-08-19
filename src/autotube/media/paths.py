"""Path and filter-argument quoting helpers for FFmpeg.

Because FFmpeg is invoked with ``shell=False`` and list arguments, ordinary input
and output paths need no shell quoting. Only paths embedded inside FFmpeg filter
strings (e.g. ``subtitles=...``) require escaping.
"""

from __future__ import annotations

from pathlib import Path


def to_ffmpeg_token(path: Path | str) -> str:
    """Convert a path to a normal FFmpeg argument token."""
    return str(path)


def escape_filter_path(path: Path | str) -> str:
    """Escape a path for use inside an FFmpeg filter expression.

    - Normalizes separators to forward slashes.
    - Escapes the Windows drive-letter colon (``C:`` -> ``C\\:``).
    - Doubles single quotes.
    """
    value = str(path).replace("\\", "/")
    if len(value) >= 2 and value[1] == ":":
        value = value[0] + "\\:" + value[2:]
    value = value.replace("'", "''")
    return value


def quote_filter_arg(value: str) -> str:
    """Wrap a filter argument in single quotes, escaping embedded quotes."""
    return "'" + value.replace("'", "''") + "'"
