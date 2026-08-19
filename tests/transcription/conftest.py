"""Transcription test fixtures."""

from __future__ import annotations

import os

import pytest


def _whisper_importable() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture
def whisper_enabled() -> bool:
    return (
        os.environ.get("AUTOTUBE_RUN_WHISPER_TESTS") == "1"
        and _whisper_importable()
    )


@pytest.fixture
def require_whisper(whisper_enabled: bool):
    if not whisper_enabled:
        pytest.skip("real faster-whisper tests not enabled")
