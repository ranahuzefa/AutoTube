"""Tests for FFprobe JSON parsing."""

from __future__ import annotations

from pathlib import Path

from autotube.media.ffprobe import _parse_probe


def test_parse_video_and_audio_streams() -> None:
    data = {
        "format": {"format_name": "mov,mp4", "duration": "2.500000", "bit_rate": "1000000"},
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 320,
                "height": 180,
                "avg_frame_rate": "30/1",
                "pix_fmt": "yuv420p",
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "44100",
                "channels": 2,
            },
        ],
    }
    info = _parse_probe(data, Path("clip.mp4"))
    assert info.duration == 2.5
    assert info.video_stream().width == 320
    assert info.video_stream().fps == 30.0
    assert info.audio_stream().channels == 2


def test_parse_no_streams() -> None:
    info = _parse_probe({"streams": []}, Path("empty.mp4"))
    assert info.streams == []
    assert info.video_stream() is None
