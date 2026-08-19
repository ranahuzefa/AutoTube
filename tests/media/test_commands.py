"""Tests for pure FFmpeg command builders."""

from __future__ import annotations

from autotube.media.commands import (
    build_compose_cmd,
    build_mix_audio_cmd,
    build_motion_filter,
    build_normalize_audio_cmd,
    build_normalize_video_cmd,
    build_scale_crop_pad_filter,
    build_trim_video_cmd,
)
from autotube.media.types import AudioSpec, FitPolicy, MotionEffect, VideoSpec


def _spec() -> VideoSpec:
    return VideoSpec(width=1280, height=720, fps=24)


def test_normalize_video_is_video_only() -> None:
    cmd = build_normalize_video_cmd("in.mp4", "out.mp4", _spec())
    assert "-an" in cmd
    assert "-c:v" in cmd
    assert "-c:a" not in cmd


def test_trim_video_is_video_only_and_uses_duration() -> None:
    cmd = build_trim_video_cmd("in.mp4", "out.mp4", _spec(), start=1.0, end=3.5)
    assert "-an" in cmd
    assert "-ss" in cmd
    assert cmd[cmd.index("-ss") + 1] == "1.000"
    assert cmd[cmd.index("-t") + 1] == "2.500"


def test_loop_video_is_video_only() -> None:
    from autotube.media.commands import build_loop_video_cmd

    cmd = build_loop_video_cmd("in.mp4", "out.mp4", _spec(), duration=4.0)
    assert "-stream_loop" in cmd
    assert "-an" in cmd


def test_normalize_audio_is_audio_only() -> None:
    cmd = build_normalize_audio_cmd("in.mp3", "out.m4a", AudioSpec())
    assert "-vn" in cmd
    assert "-c:a" in cmd
    assert "-c:v" not in cmd


def test_mix_audio_maps_final_mix() -> None:
    cmd = build_mix_audio_cmd("vo.mp3", "bg.mp3", "out.m4a", AudioSpec(), music_volume=0.25)
    assert "-filter_complex" in cmd
    assert "-map" in cmd
    assert "[aout]" in cmd
    assert "volume=0.25" in cmd[cmd.index("-filter_complex") + 1]


def test_compose_maps_only_video_from_clips_and_audio_input() -> None:
    cmd = build_compose_cmd("list.txt", "final.m4a", "out.mp4", _spec(), AudioSpec())
    assert "-f" in cmd and "concat" in cmd
    assert cmd[cmd.index("-map") + 1] == "0:v:0"
    assert "1:a:0" in cmd


def test_scale_contain_and_cover() -> None:
    contain = build_scale_crop_pad_filter(1280, 720, FitPolicy.CONTAIN)
    cover = build_scale_crop_pad_filter(1280, 720, FitPolicy.COVER)
    assert "decrease" in contain and "pad=" in contain
    assert "increase" in cover and "crop=" in cover


def test_motion_filter_preserves_fps() -> None:
    f = build_motion_filter(MotionEffect.ZOOM_IN, fps=24, duration=2.0, width=1280, height=720)
    assert "zoompan" in f
    assert "fps=24" in f
    assert "d=1" in f
    assert "s=1280x720" in f
