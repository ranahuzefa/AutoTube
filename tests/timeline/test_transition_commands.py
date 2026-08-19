"""Tests for transition FFmpeg command builders."""

from __future__ import annotations

from pathlib import Path

from autotube.media.commands import (
    build_mix_audio_cmd,
    build_transition_run_cmd,
    build_transition_sfx_cmd,
)
from autotube.media.types import AudioSpec, VideoSpec


def _video() -> VideoSpec:
    return VideoSpec(width=640, height=360, fps=30)


def test_transition_run_offsets_and_tpad() -> None:
    cmd = build_transition_run_cmd(
        [Path("a.mp4"), Path("b.mp4"), Path("c.mp4")],
        [2.0, 3.0, 4.0],
        ["fade", "wipeleft"],
        0.5,
        Path("out.mp4"),
        _video(),
    )
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "tpad=start_mode=clone:start_duration=0.500" in fc
    assert "xfade=transition=fade:duration=0.500:offset=1.500" in fc
    assert "xfade=transition=wipeleft:duration=0.500:offset=4.500" in fc
    assert "-an" in cmd


def test_transition_run_rejects_mismatched_counts() -> None:
    import pytest

    with pytest.raises(ValueError):
        build_transition_run_cmd(
            [Path("a.mp4")], [1.0], [], 0.5, Path("o.mp4"), _video()
        )
    with pytest.raises(ValueError):
        build_transition_run_cmd(
            [Path("a.mp4"), Path("b.mp4")],
            [1.0],
            ["fade"],
            0.5,
            Path("o.mp4"),
            _video(),
        )


def test_sfx_command_delay_and_trim() -> None:
    cmd = build_transition_sfx_cmd(
        [(Path("a.wav"), 2.0), (Path("b.wav"), 4.0)],
        5.0,
        Path("sfx.m4a"),
        AudioSpec(),
        transition_duration=0.5,
    )
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "adelay=1500|1500" in fc
    assert "adelay=3500|3500" in fc
    assert "atrim=duration=0.500" in fc
    assert "amix=inputs=2" in fc
    assert "-t" in cmd
    assert cmd[cmd.index("-t") + 1] == "5.000"


def test_mix_audio_no_sfx_unchanged() -> None:
    voice = Path("vo.mp3")
    music = Path("bg.mp3")
    cmd = build_mix_audio_cmd(voice, music, Path("out.m4a"), AudioSpec(), 0.2)
    assert cmd == build_mix_audio_cmd(voice, music, Path("out.m4a"), AudioSpec(), 0.2, sfx=None)


def test_mix_audio_sfx_no_music() -> None:
    cmd = build_mix_audio_cmd(
        Path("vo.mp3"),
        None,
        Path("out.m4a"),
        AudioSpec(),
        0.2,
        sfx=Path("sfx.m4a"),
        sfx_volume=0.5,
    )
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "volume=0.5" in fc
    assert "normalize=0" in fc


def test_mix_audio_sfx_with_music_two_stage() -> None:
    cmd = build_mix_audio_cmd(
        Path("vo.mp3"),
        Path("bg.mp3"),
        Path("out.m4a"),
        AudioSpec(),
        0.2,
        sfx=Path("sfx.m4a"),
        sfx_volume=0.5,
    )
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "normalize=1" in fc
    assert "normalize=0" in fc
    assert "amix=inputs=2" in fc
