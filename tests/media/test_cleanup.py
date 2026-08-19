"""Tests for safe stale render-temp cleanup."""

from __future__ import annotations

import os
from pathlib import Path

from autotube.media.cleanup import cleanup_stale_render_temps


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def test_removes_orphan_media_partial(tmp_path: Path) -> None:
    p = tmp_path / ".final.ab12cd34.partial.mp4"
    _touch(p)
    assert cleanup_stale_render_temps(tmp_path) == 1
    assert not p.exists()


def test_removes_orphan_download_part(tmp_path: Path) -> None:
    p = tmp_path / "nested" / ".video.mp4.part"
    _touch(p)
    assert cleanup_stale_render_temps(tmp_path) == 1
    assert not p.exists()


def test_leaves_final_outputs_and_intermediates(tmp_path: Path) -> None:
    finals = [
        tmp_path / "final.mp4",
        tmp_path / "composed.mp4",
        tmp_path / "captioned.mp4",
        tmp_path / "burned.mp4",
        tmp_path / "base.mp4",
        tmp_path / "transition_run_0.mp4",
        tmp_path / "gap_1_2.mp4",
        tmp_path / "missing_3_4.mp4",
        tmp_path / "clips.txt",
        tmp_path / "captions.srt",
        tmp_path / "timeline.ass",
        tmp_path / "final_audio.m4a",
        tmp_path / "transition_sfx.m4a",
    ]
    for p in finals:
        _touch(p)
    assert cleanup_stale_render_temps(tmp_path) == 0
    for p in finals:
        assert p.exists()


def test_leaves_user_assets(tmp_path: Path) -> None:
    user_files = [
        tmp_path / "script.txt",
        tmp_path / "voiceover.mp3",
        tmp_path / "music.wav",
        tmp_path / "asset.mp4",
        tmp_path / "image.png",
    ]
    for p in user_files:
        _touch(p)
    assert cleanup_stale_render_temps(tmp_path) == 0
    for p in user_files:
        assert p.exists()


def test_leaves_storage_tmp(tmp_path: Path) -> None:
    p = tmp_path / ".settings.json.tmp"
    _touch(p)
    assert cleanup_stale_render_temps(tmp_path) == 0
    assert p.exists()


def test_noop_on_missing_root(tmp_path: Path) -> None:
    assert cleanup_stale_render_temps(tmp_path / "missing") == 0


def test_skips_symlink(tmp_path: Path) -> None:
    if os.name != "nt":
        target = tmp_path / ".real.ab12cd34.partial.mp4"
        _touch(target)
        link = tmp_path / "nested" / ".link.ab12cd34.partial.mp4"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        assert cleanup_stale_render_temps(tmp_path) == 1
        assert target.exists()
