"""Real-FFmpeg timeline composer integration tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from autotube.media.service import FFmpegMediaService
from autotube.models import Project, RenderSettings
from autotube.state import PipelineStage, ProjectState, StageStatus
from autotube.timeline.composer import TimelineComposer
from autotube.timeline.types import (
    AssetType,
    SubtitleEntry,
    TimelineState,
    TimedVisualAsset,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def enabled() -> bool:
    return os.environ.get("AUTOTUBE_RUN_TIMELINE_RENDER_TESTS") == "1"


@pytest.fixture
def require_media(enabled: bool):
    if not enabled:
        pytest.skip("AUTOTUBE_RUN_TIMELINE_RENDER_TESTS not set")


def _make_image(path: Path) -> None:
    FFmpegMediaService().runner.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x360", "-frames:v", "1", str(path)]
    )


def _make_audio(path: Path, duration: float) -> None:
    FFmpegMediaService().runner.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", f"{duration:.2f}", "-c:a", "aac", str(path)]
    )


def test_compose_full_timeline(tmp_path: Path, require_media) -> None:
    image = tmp_path / "img.png"
    _make_image(image)
    audio = tmp_path / "voice.m4a"
    _make_audio(audio, 3.0)

    state = ProjectState(
        project=Project(name="E2E", voiceover_path=audio),
        render_settings=RenderSettings(resolution="640x360", fps=30),
    )
    state.timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(source_path=image, start=0.0, end=2.0, asset_type=AssetType.IMAGE)
        ],
        subtitles=[
            SubtitleEntry(index=1, start=0.0, end=2.0, text="Hello", animation_preset="fade_in")
        ],
    )

    composer = TimelineComposer(FFmpegMediaService())
    final = composer.compose(state, tmp_path / "out")

    assert final.exists()
    info = FFmpegMediaService().probe_media(final)
    assert info.video_stream() is not None
    audio_streams = [s for s in info.streams if s.codec_type == "audio"]
    assert len(audio_streams) == 1
    assert info.duration is not None
    assert abs(info.duration - 3.0) < 1.0
