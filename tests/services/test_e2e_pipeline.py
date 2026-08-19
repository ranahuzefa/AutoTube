"""End-to-end pipeline test using real FFmpeg only (no network/keys/models)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from autotube.media.service import FFmpegMediaService
from autotube.models import Project, RenderSettings
from autotube.services.orchestrator import PipelineOrchestrator
from autotube.state import (
    PipelineStage,
    ProjectState,
    SegmentState,
    StageStatus,
)
from autotube.storage import ProjectStore

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


def _make_video(path: Path, duration: float, size: str = "320x180") -> None:
    from autotube.media.ffmpeg_runner import FFmpegRunner

    FFmpegRunner().run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=size={size}:rate=30",
            "-t", f"{duration:.2f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(path),
        ]
    )


def _make_audio(path: Path, duration: float) -> None:
    from autotube.media.ffmpeg_runner import FFmpegRunner

    FFmpegRunner().run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
            "-t", f"{duration:.2f}",
            "-c:a", "aac",
            str(path),
        ]
    )


@pytest.fixture
def e2e_enabled() -> bool:
    return os.environ.get("AUTOTUBE_RUN_E2E_TESTS") == "1"


@pytest.fixture
def require_e2e(e2e_enabled: bool):
    if not e2e_enabled:
        pytest.skip("AUTOTUBE_RUN_E2E_TESTS not set")


def test_full_pipeline_from_clips(tmp_path: Path, require_e2e) -> None:
    voice = tmp_path / "voice.wav"
    stock1 = tmp_path / "stock1.mp4"
    stock2 = tmp_path / "stock2.mp4"
    _make_audio(voice, 2.0)
    _make_video(stock1, 1.0)
    _make_video(stock2, 1.0)

    project = Project(
        name="E2E",
        voiceover_path=voice,
        music_path=None,
    )
    state = ProjectState(
        project=project,
        render_settings=RenderSettings(resolution="320x180", fps=30),
    )
    seg1 = SegmentState.new("hello", 0.0, 1.0)
    seg2 = SegmentState.new("world", 1.0, 2.0)
    seg1.keywords = ["hello"]
    seg2.keywords = ["world"]
    seg1.selected_clip = {"local_path": str(stock1)}
    seg2.selected_clip = {"local_path": str(stock2)}
    state.segments = [seg1, seg2]
    state.transcription = None

    for stage in (
        PipelineStage.TRANSCRIBED,
        PipelineStage.SEGMENTS_READY,
        PipelineStage.KEYWORDS_READY,
        PipelineStage.ASSETS_READY,
    ):
        state.stage(stage).status = StageStatus.COMPLETED

    orchestrator = PipelineOrchestrator(
        transcription_workflow=_SkipTranscription(),
        stock_workflow=_SkipStock(),
        media_service=FFmpegMediaService(),
        store=ProjectStore(),
        project_path=tmp_path / "project.json",
    )

    result = orchestrator.run(state)

    for stage in (
        PipelineStage.CLIPS_READY,
        PipelineStage.COMPOSED,
        PipelineStage.AUDIO_READY,
        PipelineStage.CAPTIONS_READY,
        PipelineStage.COMPLETED,
    ):
        assert result.stage(stage).status == StageStatus.COMPLETED

    final = result.stage(PipelineStage.COMPLETED).artifacts[-1]
    assert final.exists()

    info = FFmpegMediaService().probe_media(final)
    assert info.video_stream() is not None
    assert info.audio_stream() is not None
    assert len([s for s in info.streams if s.codec_type == "audio"]) == 1

    # Resume: no media work should happen on a re-run without force.
    before = final.stat().st_mtime_ns
    orchestrator.run(result)
    assert final.stat().st_mtime_ns == before
