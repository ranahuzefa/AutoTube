"""Real-FFmpeg integration tests for missing timeline visual slots."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from autotube.exceptions import MissingVisualAssetsError
from autotube.media.service import FFmpegMediaService
from autotube.models import Project, RenderSettings
from autotube.services.orchestrator import PipelineOrchestrator
from autotube.state import PipelineStage, ProjectState, StageStatus
from autotube.storage import ProjectStore
from autotube.timeline.composer import TimelineComposer
from autotube.timeline.missing import build_missing_asset_report
from autotube.timeline.types import (
    AssetType,
    SubtitleEntry,
    TimelineState,
    TimedVisualAsset,
)

pytestmark = pytest.mark.integration


class _SkipTranscription:
    def run(self, state, *, force=False, cancel_event=None):
        state.stage(PipelineStage.TRANSCRIBED).status = StageStatus.COMPLETED
        state.stage(PipelineStage.SEGMENTS_READY).status = StageStatus.COMPLETED
        return state


class _SkipStock:
    def run(self, state, *, force=False, cancel_event=None):
        state.stage(PipelineStage.KEYWORDS_READY).status = StageStatus.COMPLETED
        state.stage(PipelineStage.ASSETS_READY).status = StageStatus.COMPLETED
        return state


@pytest.fixture
def enabled() -> bool:
    return os.environ.get("AUTOTUBE_RUN_TIMELINE_RENDER_TESTS") == "1"


@pytest.fixture
def require_media(enabled: bool):
    if not enabled:
        pytest.skip("AUTOTUBE_RUN_TIMELINE_RENDER_TESTS not set")


def _make_image(path: Path) -> None:
    FFmpegMediaService().runner.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=red:s=640x360",
            "-frames:v", "1",
            str(path),
        ]
    )


def _make_audio(path: Path, duration: float) -> None:
    FFmpegMediaService().runner.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
            "-t", f"{duration:.2f}",
            "-c:a", "aac",
            str(path),
        ]
    )


def _orchestrator(tmp_path: Path) -> PipelineOrchestrator:
    media = FFmpegMediaService()
    return PipelineOrchestrator(
        transcription_workflow=_SkipTranscription(),
        stock_workflow=_SkipStock(),
        media_service=media,
        store=ProjectStore(),
        project_path=tmp_path / "project.json",
        timeline_composer=TimelineComposer(media),
    )


def _state(tmp_path: Path) -> ProjectState:
    image = tmp_path / "img.png"
    _make_image(image)
    audio = tmp_path / "voice.m4a"
    _make_audio(audio, 3.0)

    state = ProjectState(
        project=Project(name="E2E", voiceover_path=audio),
        render_settings=RenderSettings(
            resolution="640x360", fps=30, output_dir=tmp_path / "out"
        ),
    )
    state.timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(
                source_path=image, start=0.0, end=2.0, asset_type=AssetType.IMAGE
            ),
            TimedVisualAsset(start=2.0, end=3.0, asset_type=AssetType.IMAGE),
        ],
        subtitles=[
            SubtitleEntry(index=1, start=0.0, end=3.0, text="Hello")
        ],
    )
    return state


def test_missing_slot_validation_mode(tmp_path: Path, require_media) -> None:
    state = _state(tmp_path)
    orch = _orchestrator(tmp_path)

    with pytest.raises(MissingVisualAssetsError):
        orch.run(state, allow_missing=False)

    assert state.stage(PipelineStage.CLIPS_READY).status == StageStatus.FAILED
    assert not (state.render_settings.output_dir / "final.mp4").exists()


def test_missing_slot_continue_mode_preserves_timing(tmp_path: Path, require_media) -> None:
    state = _state(tmp_path)
    orch = _orchestrator(tmp_path)

    result = orch.run(state, allow_missing=True)

    final = result.stage(PipelineStage.COMPLETED).artifacts[-1]
    assert final.exists()

    info = FFmpegMediaService().probe_media(final)
    assert info.video_stream() is not None
    assert len([s for s in info.streams if s.codec_type == "audio"]) == 1

    # Timeline duration remains unchanged (~3s).
    assert info.duration is not None
    assert abs(info.duration - 3.0) < 1.0

    # The missing slot is reported and not silently substituted.
    report = build_missing_asset_report(result.timeline)
    assert "MISSING VISUAL ASSETS" in report
    assert "00:02 -> 00:03" in report

    missing = [a for a in result.timeline.visual_assets if a.source_path is None]
    assert len(missing) == 1
    assert missing[0].processed_path is None

    # Subtitle/audio timing unchanged.
    assert result.timeline.subtitles[0].start == 0.0
    assert result.timeline.subtitles[0].end == 3.0
