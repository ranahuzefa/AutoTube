"""Tests for FFmpeg/FFprobe availability detection."""

from __future__ import annotations

import os
import sys

import pytest

from autotube.media.detection import (
    MediaTooling,
    _bundled_candidates,
    _first_existing,
    detect_media_tooling,
    require_media_tooling,
)


def test_detect_available_on_this_machine(monkeypatch) -> None:
    # The dev environment has ffmpeg/ffprobe on PATH, but do not assume it.
    monkeypatch.setattr(
        "autotube.media.detection._which",
        lambda name: f"C:/tools/{name}.exe",
    )
    tooling = detect_media_tooling()
    assert tooling.available
    assert tooling.missing_names() == []


def test_detect_missing_both(monkeypatch) -> None:
    monkeypatch.setattr("autotube.media.detection._which", lambda name: None)
    monkeypatch.setattr("autotube.media.detection._bundled_candidates", lambda name: [])
    tooling = detect_media_tooling()
    assert not tooling.available
    assert set(tooling.missing_names()) == {"ffmpeg", "ffprobe"}


def test_detect_missing_ffprobe_only(monkeypatch) -> None:
    monkeypatch.setattr(
        "autotube.media.detection._which",
        lambda name: "C:/tools/ffmpeg.exe" if name == "ffmpeg" else None,
    )
    monkeypatch.setattr("autotube.media.detection._bundled_candidates", lambda name: [])
    tooling = detect_media_tooling()
    assert not tooling.available
    assert tooling.missing_names() == ["ffprobe"]


def test_require_raises_clear_error(monkeypatch) -> None:
    monkeypatch.setattr("autotube.media.detection._which", lambda name: None)
    monkeypatch.setattr("autotube.media.detection._bundled_candidates", lambda name: [])
    with pytest.raises(RuntimeError) as exc:
        require_media_tooling()
    message = str(exc.value)
    assert "ffmpeg" in message
    assert "ffprobe" in message
    assert "PATH" in message


def test_first_existing_prefers_first(tmp_path) -> None:
    existing = tmp_path / "a"
    existing.write_bytes(b"x")
    missing = tmp_path / "b"
    assert _first_existing([missing, existing]) == str(existing)
    assert _first_existing([missing]) is None


def test_media_tooling_missing_names() -> None:
    tooling = MediaTooling(ffmpeg="a", ffprobe=None)
    assert not tooling.available
    assert tooling.missing_names() == ["ffprobe"]


def test_bundled_candidates_empty_when_not_frozen() -> None:
    assert _bundled_candidates("ffmpeg") == []


def test_detect_uses_bundled_when_frozen(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("autotube.media.detection._which", lambda name: None)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "autotube.exe"), raising=False)

    suffix = ".exe" if os.name == "nt" else ""
    bundled_dir = tmp_path / "ffmpeg"
    bundled_dir.mkdir()
    ffmpeg_bin = bundled_dir / f"ffmpeg{suffix}"
    ffprobe_bin = bundled_dir / f"ffprobe{suffix}"
    ffmpeg_bin.write_bytes(b"x")
    ffprobe_bin.write_bytes(b"x")

    tooling = detect_media_tooling()

    assert tooling.ffmpeg == str(ffmpeg_bin)
    assert tooling.ffprobe == str(ffprobe_bin)
    assert tooling.available
