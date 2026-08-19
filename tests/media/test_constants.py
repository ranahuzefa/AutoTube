"""Tests for media constants and spec factories."""

from __future__ import annotations

from pathlib import Path

from autotube.media.constants import audio_spec_default, video_spec_from_render_settings
from autotube.media.types import FitPolicy
from autotube.models import RenderSettings


def test_video_spec_reads_render_settings_values() -> None:
    rs = RenderSettings(resolution="1280x720", fps=24)
    spec = video_spec_from_render_settings(rs)
    assert spec.width == 1280
    assert spec.height == 720
    assert spec.fps == 24
    assert spec.include_audio is False
    assert spec.fit == FitPolicy.CONTAIN


def test_audio_spec_defaults() -> None:
    spec = audio_spec_default()
    assert spec.codec == "aac"
    assert spec.sample_rate == 48000
    assert spec.channels == 2


def test_no_hardcoded_defaults_leak() -> None:
    rs = RenderSettings(resolution="640x360", fps=12)
    spec = video_spec_from_render_settings(rs)
    assert spec.width == 640
    assert spec.height == 360
    assert spec.fps == 12
