"""Tests for FFmpeg progress parsing."""

from __future__ import annotations

from autotube.media.progress import FFmpegProgressParser


def test_continue_emits_percent() -> None:
    emitted = []
    parser = FFmpegProgressParser(total_duration=10.0)
    cb = lambda p, f, r: emitted.append((p, f, r))
    parser.parse_line("frame=100", cb)
    parser.parse_line("fps=25.0", cb)
    parser.parse_line("out_time_us=5000000", cb)
    assert (50.0, 100, 25.0) in emitted


def test_end_emits_100() -> None:
    emitted = []
    cb = lambda p, f, r: emitted.append((p, f, r))
    parser = FFmpegProgressParser(total_duration=10.0)
    parser.parse_line("progress=end", cb)
    assert (100.0, 0, 0.0) in emitted


def test_percent_clamped() -> None:
    emitted = []
    cb = lambda p, f, r: emitted.append((p, f, r))
    parser = FFmpegProgressParser(total_duration=1.0)
    parser.parse_line("out_time_us=5000000", cb)
    assert emitted[-1][0] == 100.0


def test_malformed_line_ignored() -> None:
    parser = FFmpegProgressParser(total_duration=10.0)
    assert parser.parse_line("not a progress line") == {}


def test_unknown_keys_tolerated() -> None:
    parser = FFmpegProgressParser(total_duration=10.0)
    snapshot = parser.parse_line("some_key=value")
    assert snapshot == {"some_key": "value"}
