"""Tests for FFmpeg filter path and quoting helpers."""

from __future__ import annotations

from pathlib import Path

from autotube.media.paths import escape_filter_path, quote_filter_arg, to_ffmpeg_token


def test_windows_drive_colon_escaped() -> None:
    assert escape_filter_path(r"C:\Users\me\video.mp4") == r"C\:/Users/me/video.mp4"


def test_backslashes_to_forward_slashes() -> None:
    assert escape_filter_path(r"a\b\c.srt") == "a/b/c.srt"


def test_single_quotes_doubled() -> None:
    assert escape_filter_path("/tmp/it's here.srt") == "/tmp/it''s here.srt"


def test_quote_filter_arg() -> None:
    assert quote_filter_arg("it's") == "'it''s'"


def test_to_ffmpeg_token_plain_string() -> None:
    assert to_ffmpeg_token(Path("out.mp4")) == str(Path("out.mp4"))
