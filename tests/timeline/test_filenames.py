"""Tests for timestamp filename parsing (Windows-safe compact format)."""

from __future__ import annotations

import pytest

from autotube.exceptions import ValidationError
from autotube.timeline.filenames import parse_timestamp_filename


def test_mm_ss() -> None:
    parsed = parse_timestamp_filename("0001--0002.png")
    assert parsed.start == 1.0
    assert parsed.end == 2.0
    assert parsed.extension == ".png"


def test_hh_mm_ss() -> None:
    parsed = parse_timestamp_filename("0130--0135.mp4")
    assert parsed.start == 90.0
    assert parsed.end == 95.0


def test_six_digit_hhmmss() -> None:
    parsed = parse_timestamp_filename("010005--010012.mp4")
    assert parsed.start == 3605.0
    assert parsed.end == 3612.0


def test_ten_minutes() -> None:
    parsed = parse_timestamp_filename("1005--1012.mp4")
    assert parsed.start == 605.0
    assert parsed.end == 612.0


def test_invalid_range() -> None:
    with pytest.raises(ValidationError):
        parse_timestamp_filename("0130--0120.mp4")


def test_missing_separator() -> None:
    with pytest.raises(ValidationError):
        parse_timestamp_filename("0130.mp4")


def test_invalid_minutes() -> None:
    with pytest.raises(ValidationError):
        parse_timestamp_filename("9999--10000.png")


def test_invalid_seconds() -> None:
    with pytest.raises(ValidationError):
        parse_timestamp_filename("0060--0061.png")


def test_non_numeric() -> None:
    with pytest.raises(ValidationError):
        parse_timestamp_filename("abcd--efgh.mp4")


def test_wrong_component_length() -> None:
    with pytest.raises(ValidationError):
        parse_timestamp_filename("1--2.mp4")


def test_unsupported_extension() -> None:
    with pytest.raises(ValidationError):
        parse_timestamp_filename("0001--0002.txt")
