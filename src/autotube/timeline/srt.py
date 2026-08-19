"""SRT import and parsing."""

from __future__ import annotations

from pathlib import Path

from ..exceptions import ValidationError
from .types import SubtitleEntry


def _parse_timestamp(value: str) -> float:
    try:
        hours, minutes, seconds = value.strip().split(":")
        secs, millis = seconds.split(",")
        return int(hours) * 3600 + int(minutes) * 60 + int(secs) + int(millis) / 1000
    except (ValueError, AttributeError) as exc:
        raise ValidationError(f"Invalid SRT timestamp: {value!r}") from exc


class SRTParser:
    """Parse standard SRT content into subtitle entries."""

    def parse(self, text: str) -> list[SubtitleEntry]:
        entries: list[SubtitleEntry] = []
        blocks = text.strip().split("\n\n")
        if blocks == [""]:
            return entries

        for block in blocks:
            lines = [line.rstrip("\r") for line in block.split("\n") if line.strip()]
            if not lines:
                continue

            try:
                index = int(lines[0])
            except ValueError as exc:
                raise ValidationError(f"Invalid SRT index: {lines[0]!r}") from exc

            if " --> " not in lines[1]:
                raise ValidationError(f"Invalid SRT timing line: {lines[1]!r}")

            start_raw, end_raw = lines[1].split(" --> ", 1)
            start = _parse_timestamp(start_raw)
            end = _parse_timestamp(end_raw)

            if start < 0:
                raise ValidationError("SRT start must be >= 0.")
            if end <= start:
                raise ValidationError("SRT end must be greater than start.")

            subtitle_text = " ".join(lines[2:]).strip()
            if not subtitle_text:
                raise ValidationError(f"SRT entry {index} has empty text.")

            entries.append(
                SubtitleEntry(index=index, start=start, end=end, text=subtitle_text)
            )

        entries.sort(key=lambda e: e.start)
        return entries

    def parse_file(self, path: Path) -> list[SubtitleEntry]:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValidationError(f"Cannot read SRT file {path}: {exc}") from exc
        return self.parse(text)
