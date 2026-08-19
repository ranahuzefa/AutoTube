"""Tests for SRT parsing."""

from __future__ import annotations

import pytest

from autotube.exceptions import ValidationError
from autotube.timeline.srt import SRTParser


def test_parse_single_entry() -> None:
    text = "1\n00:00:02,000 --> 00:00:04,000\nMost retirees make this mistake\n"
    entries = SRTParser().parse(text)
    assert len(entries) == 1
    assert entries[0].index == 1
    assert entries[0].start == 2.0
    assert entries[0].end == 4.0
    assert entries[0].text == "Most retirees make this mistake"


def test_parse_multiple_entries_sorted() -> None:
    text = (
        "2\n00:00:04,000 --> 00:00:06,000\nSecond\n\n"
        "1\n00:00:02,000 --> 00:00:04,000\nFirst\n"
    )
    entries = SRTParser().parse(text)
    assert [e.index for e in entries] == [1, 2]


def test_empty_input() -> None:
    assert SRTParser().parse("") == []
    assert SRTParser().parse("   \n") == []


def test_malformed_timestamp() -> None:
    with pytest.raises(ValidationError):
        SRTParser().parse("1\nnot a time\nText\n")


def test_end_before_start() -> None:
    with pytest.raises(ValidationError):
        SRTParser().parse("1\n00:00:05,000 --> 00:00:02,000\nText\n")


def test_empty_subtitle_text() -> None:
    with pytest.raises(ValidationError):
        SRTParser().parse("1\n00:00:02,000 --> 00:00:04,000\n\n")


def test_overlapping_subtitles_allowed() -> None:
    text = (
        "1\n00:00:02,000 --> 00:00:05,000\nOne\n\n"
        "2\n00:00:03,000 --> 00:00:06,000\nTwo\n"
    )
    entries = SRTParser().parse(text)
    assert len(entries) == 2
