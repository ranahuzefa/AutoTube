"""Tests for media metadata dataclasses."""

from __future__ import annotations

from pathlib import Path

import pytest

from autotube.exceptions import MediaError
from autotube.media.types import MediaInfo, StreamInfo


def test_stream_info_roundtrip() -> None:
    stream = StreamInfo(
        index=0,
        codec_type="video",
        codec_name="h264",
        width=1920,
        height=1080,
        fps=30.0,
        pix_fmt="yuv420p",
        duration=2.5,
    )
    assert StreamInfo.from_dict(stream.to_dict()) == stream


def test_media_info_roundtrip() -> None:
    info = MediaInfo(
        path=Path("clip.mp4"),
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
        duration=2.5,
        bit_rate=1000000,
        streams=[StreamInfo(index=0, codec_type="video")],
    )
    assert MediaInfo.from_dict(info.to_dict()) == info


def test_require_video_missing_raises() -> None:
    info = MediaInfo(path=Path("x.mp3"), streams=[StreamInfo(index=0, codec_type="audio")])
    with pytest.raises(MediaError):
        info.require_video()


def test_require_audio_missing_raises() -> None:
    info = MediaInfo(path=Path("x.mp4"), streams=[StreamInfo(index=0, codec_type="video")])
    with pytest.raises(MediaError):
        info.require_audio()
