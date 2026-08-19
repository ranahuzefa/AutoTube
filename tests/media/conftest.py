"""Shared fixtures for media tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from autotube.media.ffmpeg_runner import FFmpegRunner


@pytest.fixture
def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


@pytest.fixture
def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


@pytest.fixture
def media_available(ffmpeg_available: bool, ffprobe_available: bool) -> bool:
    return ffmpeg_available and ffprobe_available


@pytest.fixture
def require_media(media_available: bool):
    if not media_available:
        pytest.skip("ffmpeg/ffprobe not available")
