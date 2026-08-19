"""Tests for transcription config."""

from __future__ import annotations

from autotube.models import RenderSettings
from autotube.transcription.config import TranscriptionConfig


def test_defaults() -> None:
    config = TranscriptionConfig()
    assert config.model == "base"
    assert config.device == "auto"
    assert config.compute_type == "auto"
    assert config.vad_filter is True
    assert config.min_segment_duration == 1.0
    assert config.max_segment_duration == 8.0


def test_from_render_settings() -> None:
    config = TranscriptionConfig.from_render_settings(
        RenderSettings(whisper_model="tiny")
    )
    assert config.model == "tiny"


def test_roundtrip() -> None:
    config = TranscriptionConfig(model="small", device="cpu", compute_type="int8")
    assert TranscriptionConfig.from_dict(config.to_dict()) == config
