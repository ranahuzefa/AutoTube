"""Tests for SRT generation."""

from __future__ import annotations

from types import SimpleNamespace

from autotube.media.captions import write_srt


def test_write_srt_formatting(tmp_path) -> None:
    segments = [
        SimpleNamespace(start=0.0, end=1.5, text="Hello"),
        SimpleNamespace(start=1.5, end=3.0, text="World"),
    ]
    path = write_srt(segments, tmp_path / "out.srt")
    content = path.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:01,500" in content
    assert "Hello" in content
    assert "World" in content
