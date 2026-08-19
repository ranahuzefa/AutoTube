"""Authoritative START--END filename timestamp parsing (Windows-safe).

The on-disk format is ``MMSS--MMSS.ext`` or ``HHMMSS--HHMMSS.ext``:

- ``0001--0002.png``  = 00:01 -> 00:02
- ``0015--0016.mp4``  = 00:15 -> 00:16
- ``0130--0135.mp4``  = 01:30 -> 01:35
- ``010005--010012.mp4`` = 01:00:05 -> 01:00:12

No ``:``, ``>``, ``<``, or any other Windows-reserved filename character is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..exceptions import ValidationError
from .constants import SUPPORTED_VISUAL_EXTENSIONS


@dataclass
class TimestampFilename:
    start: float
    end: float
    extension: str


def _parse_compact_time(value: str) -> float:
    if not value.isdigit():
        raise ValidationError(f"Invalid timestamp component: {value!r}")

    if len(value) == 4:
        hours = 0
        minutes = int(value[0:2])
        seconds = int(value[2:4])
    elif len(value) == 6:
        hours = int(value[0:2])
        minutes = int(value[2:4])
        seconds = int(value[4:6])
    else:
        raise ValidationError(
            f"Timestamp component must be MMSS or HHMMSS: {value!r}"
        )

    if not (0 <= minutes <= 59 and 0 <= seconds <= 59):
        raise ValidationError(f"Invalid timestamp component: {value!r}")

    return hours * 3600 + minutes * 60 + seconds


def parse_timestamp_filename(name: str) -> TimestampFilename:
    path = Path(name)
    extension = path.suffix.lower()
    if extension not in SUPPORTED_VISUAL_EXTENSIONS:
        raise ValidationError(f"Unsupported visual asset extension: {extension!r}")

    stem = path.stem
    if stem.count("--") != 1:
        raise ValidationError(
            f"Invalid visual asset filename (expected START--END.ext): {name!r}"
        )

    start_raw, end_raw = stem.split("--", 1)
    start = _parse_compact_time(start_raw)
    end = _parse_compact_time(end_raw)

    if start < 0:
        raise ValidationError(f"Asset start must be >= 0: {name!r}")
    if end <= start:
        raise ValidationError(f"Asset end must be greater than start: {name!r}")

    return TimestampFilename(start=start, end=end, extension=extension)
