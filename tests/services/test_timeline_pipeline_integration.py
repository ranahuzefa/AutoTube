"""Real-FFmpeg timeline pipeline integration tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from autotube.media.service import FFmpegMediaService
from autotube.models import Project, RenderSettings
from autotube.services.orchestrator import PipelineOrchestrator
from autotube.state import PipelineStage, ProjectState, StageStatus
from autotube.storage import ProjectStore
from autotube.timeline.composer import TimelineComposer
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
            "-f", "lavfi", "-i", "color=c=blue:s=640x360",
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


def _project_state(tmp_path: Path, voice: Path) -> ProjectState:
    return ProjectState(
        project=Project(name="E2E", voiceover_path=voice),
        render_settings=RenderSettings(
            resolution="640x360", fps=30, output_dir=tmp_path / "out"
        ),
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


def test_full_timeline_pipeline(tmp_path: Path, require_media) -> None:
    image = tmp_path / "img.png"
    _make_image(image)
    audio = tmp_path / "voice.m4a"
    _make_audio(audio, 2.0)

    state = _project_state(tmp_path, audio)
    state.timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(
                source_path=image, start=0.0, end=2.0, asset_type=AssetType.IMAGE
            )
        ],
        subtitles=[
            SubtitleEntry(index=1, start=0.0, end=2.0, text="Hello", animation_preset="fade_in")
        ],
    )

    orch = _orchestrator(tmp_path)
    result = orch.run(state)

    for stage in (
        PipelineStage.TRANSCRIBED,
        PipelineStage.SEGMENTS_READY,
        PipelineStage.KEYWORDS_READY,
        PipelineStage.ASSETS_READY,
    ):
        assert result.stage(stage).status == StageStatus.SKIPPED

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
    audio_streams = [s for s in info.streams if s.codec_type == "audio"]
    assert len(audio_streams) == 1
    assert result.timeline.rendered_path == str(final)
    assert result.timeline.rendered_fingerprint is not None


def test_timeline_resume_no_rerender(tmp_path: Path, require_media) -> None:
    image = tmp_path / "img.png"
    _make_image(image)
    audio = tmp_path / "voice.m4a"
    _make_audio(audio, 2.0)

    state = _project_state(tmp_path, audio)
    state.timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(
                source_path=image, start=0.0, end=2.0, asset_type=AssetType.IMAGE
            )
        ]
    )

    orch = _orchestrator(tmp_path)
    result = orch.run(state)
    final = result.stage(PipelineStage.COMPLETED).artifacts[-1]
    before = final.stat().st_mtime_ns

    orch.run(result)
    assert final.stat().st_mtime_ns == before


def test_timeline_stale_output_rerenders(tmp_path: Path, require_media) -> None:
    image = tmp_path / "img.png"
    _make_image(image)
    audio = tmp_path / "voice.m4a"
    _make_audio(audio, 2.0)

    state = _project_state(tmp_path, audio)
    state.timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(
                source_path=image, start=0.0, end=2.0, asset_type=AssetType.IMAGE
            )
        ],
        subtitles=[
            SubtitleEntry(index=1, start=0.0, end=2.0, text="Hello")
        ],
    )

    orch = _orchestrator(tmp_path)
    result = orch.run(state)
    final = result.stage(PipelineStage.COMPLETED).artifacts[-1]
    before = final.stat().st_mtime_ns

    state.timeline.subtitles[0].text = "World"
    orch.run(state)
    assert final.stat().st_mtime_ns != before
