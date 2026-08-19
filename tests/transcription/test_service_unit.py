"""Unit tests for the transcription service using a fake model."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from autotube.exceptions import TranscriptionCancelledError
from autotube.transcription.config import TranscriptionConfig
from autotube.transcription.service import FasterWhisperTranscriptionService


class _FakeModel:
    def __init__(self, segments, info):
        self._segments = segments
        self._info = info

    def transcribe(self, *args, **kwargs):
        return iter(self._segments), self._info


class _FakeLoader:
    def __init__(self, model):
        self.model = model

    def get(self, config):
        return self.model


def _raw_segment(text, start, end, words=()):
    return SimpleNamespace(text=text, start=start, end=end, words=words)


def test_transcribe_basic(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"fake")
    model = _FakeModel(
        [_raw_segment("hello", 0.0, 1.0)],
        SimpleNamespace(language="en", language_probability=0.9),
    )
    service = FasterWhisperTranscriptionService(loader=_FakeLoader(model))
    result = service.transcribe_with_config(voice, TranscriptionConfig())
    assert len(result.segments) == 1
    assert result.segments[0].text == "hello"
    assert result.language == "en"


def test_transcribe_backward_compatible(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"fake")
    model = _FakeModel(
        [_raw_segment("hi", 0.0, 0.5)],
        SimpleNamespace(language="en", language_probability=0.9),
    )
    service = FasterWhisperTranscriptionService(loader=_FakeLoader(model))
    segments = service.transcribe(voice, "tiny")
    assert len(segments) == 1
    assert segments[0].text == "hi"


def test_cancel_before_model_load(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"fake")
    cancel = threading.Event()
    cancel.set()
    service = FasterWhisperTranscriptionService(loader=_FakeLoader(None))
    with pytest.raises(TranscriptionCancelledError):
        service.transcribe_with_config(voice, TranscriptionConfig(), cancel_event=cancel)


def test_cancel_between_segments(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"fake")
    cancel = threading.Event()

    model = _FakeModel(
        [
            _raw_segment("one", 0.0, 1.0),
            _raw_segment("two", 1.0, 2.0),
        ],
        SimpleNamespace(language="en", language_probability=0.9),
    )

    # Set cancel after first segment is yielded by the fake model.
    original_iter = iter(model._segments)

    def cancel_after_first():
        yield next(original_iter)
        cancel.set()
        yield next(original_iter)

    model.transcribe = lambda *a, **k: (cancel_after_first(), model._info)

    service = FasterWhisperTranscriptionService(loader=_FakeLoader(model))
    with pytest.raises(TranscriptionCancelledError):
        service.transcribe_with_config(voice, TranscriptionConfig(), cancel_event=cancel)


def test_progress_monotonic_and_complete(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"fake")
    model = _FakeModel(
        [_raw_segment("one", 0.0, 1.0), _raw_segment("two", 1.0, 2.0)],
        SimpleNamespace(language="en", language_probability=0.9),
    )
    service = FasterWhisperTranscriptionService(loader=_FakeLoader(model))
    emitted = []
    service.transcribe_with_config(
        voice, TranscriptionConfig(), progress=emitted.append
    )
    assert emitted[0] == 0.0
    assert emitted[-1] == 100.0
    assert emitted == sorted(emitted)
