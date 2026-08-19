"""Opt-in real-model faster-whisper integration tests.

These tests never run by default. They require:
  1. faster_whisper importable
  2. a speech WAV (embedded base64 or AUTOTUBE_TEST_SPEECH_WAV)
  3. AUTOTUBE_RUN_WHISPER_TESTS=1
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from autotube.transcription.config import TranscriptionConfig
from autotube.transcription.service import FasterWhisperTranscriptionService

pytestmark = [pytest.mark.integration, pytest.mark.whisper]


@pytest.fixture
def speech_wav(tmp_path: Path, require_whisper) -> Path:
    env = os.environ.get("AUTOTUBE_TEST_SPEECH_WAV")
    if env:
        path = Path(env)
        if path.exists():
            return path
    pytest.skip("AUTOTUBE_TEST_SPEECH_WAV not set to a valid WAV")


def test_transcribe_structural(require_whisper, speech_wav: Path) -> None:
    model = os.environ.get("AUTOTUBE_TEST_WHISPER_MODEL", "tiny")
    config = TranscriptionConfig(model=model, device="cpu", compute_type="int8")
    service = FasterWhisperTranscriptionService()
    result = service.transcribe_with_config(speech_wav, config)

    assert result.segments
    for segment in result.segments:
        assert segment.text.strip()
        assert 0.0 <= segment.start <= segment.end <= result.duration
    assert result.language
