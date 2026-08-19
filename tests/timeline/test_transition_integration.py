"""Real-FFmpeg transition integration tests.

Opt-in via ``AUTOTUBE_RUN_TRANSITION_TESTS=1`` and marked ``integration``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from autotube.media.constants import video_spec_from_render_settings
from autotube.media.service import FFmpegMediaService
from autotube.models import Project, RenderSettings
from autotube.state import ProjectState
from autotube.timeline.composer import TimelineComposer
from autotube.timeline.types import (
    AssetType,
    TimelineState,
    TimedVisualAsset,
    TransitionEffectMode,
    TransitionSettings,
    TransitionSoundMode,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def enabled() -> bool:
    return os.environ.get("AUTOTUBE_RUN_TRANSITION_TESTS") == "1"


@pytest.fixture
def require_transitions(enabled: bool):
    if not enabled:
        pytest.skip("AUTOTUBE_RUN_TRANSITION_TESTS not set")


def _make_image(service: FFmpegMediaService, path: Path, color: str = "red") -> None:
    service.runner.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s=640x360",
            "-frames:v", "1",
            str(path),
        ]
    )


def _make_audio(service: FFmpegMediaService, path: Path, duration: float) -> None:
    service.runner.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
            "-t", f"{duration:.2f}",
            "-c:a", "aac",
            str(path),
        ]
    )


def test_two_images_fade_preserves_duration(tmp_path: Path, require_transitions) -> None:
    service = FFmpegMediaService()
    img_a = tmp_path / "a.png"
    img_b = tmp_path / "b.png"
    _make_image(service, img_a, "red")
    _make_image(service, img_b, "blue")

    state = ProjectState(
        project=Project(name="T", voiceover_path=None),
        render_settings=RenderSettings(resolution="640x360", fps=30),
    )
    state.timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(img_a, 0.0, 2.0, AssetType.IMAGE),
            TimedVisualAsset(img_b, 2.0, 4.0, AssetType.IMAGE),
        ],
        transition_settings=TransitionSettings(
            effect_mode=TransitionEffectMode.MANUAL, effect="fade", duration=0.5
        ),
    )

    composer = TimelineComposer(service)
    spec = video_spec_from_render_settings(state.render_settings)
    output_dir = tmp_path / "out"
    composer.process_visual_assets(state, state.timeline, spec, output_dir)
    base = composer.build_base_track(
        state, state.timeline, spec, output_dir, None, None
    )
    info = service.probe_media(base)
    assert info.video_stream() is not None
    assert abs(info.duration - 4.0) < 0.5


def test_three_clips_exact_duration_and_streams(tmp_path: Path, require_transitions) -> None:
    service = FFmpegMediaService()
    img_a = tmp_path / "a.png"
    img_b = tmp_path / "b.png"
    img_c = tmp_path / "c.png"
    _make_image(service, img_a, "red")
    _make_image(service, img_b, "green")
    _make_image(service, img_c, "blue")

    state = ProjectState(
        project=Project(name="T", voiceover_path=None),
        render_settings=RenderSettings(resolution="640x360", fps=30),
    )
    state.timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(img_a, 0.0, 2.0, AssetType.IMAGE),
            TimedVisualAsset(img_b, 2.0, 4.0, AssetType.IMAGE),
            TimedVisualAsset(img_c, 4.0, 6.0, AssetType.IMAGE),
        ],
        transition_settings=TransitionSettings(
            effect_mode=TransitionEffectMode.MANUAL, effect="wipeleft", duration=0.5
        ),
    )

    composer = TimelineComposer(service)
    spec = video_spec_from_render_settings(state.render_settings)
    output_dir = tmp_path / "out"
    composer.process_visual_assets(state, state.timeline, spec, output_dir)
    base = composer.build_base_track(
        state, state.timeline, spec, output_dir, None, None
    )
    info = service.probe_media(base)
    assert abs(info.duration - 6.0) < 0.5
    assert len([s for s in info.streams if s.codec_type == "video"]) == 1
    assert len([s for s in info.streams if s.codec_type == "audio"]) == 0


def test_sfx_does_not_shift_voiceover_duration(tmp_path: Path, require_transitions) -> None:
    service = FFmpegMediaService()
    img_a = tmp_path / "a.png"
    img_b = tmp_path / "b.png"
    _make_image(service, img_a, "red")
    _make_image(service, img_b, "blue")

    voice = tmp_path / "voice.m4a"
    _make_audio(service, voice, 4.0)

    sfx_dir = tmp_path / "sfx"
    sfx_dir.mkdir()
    _make_audio(service, sfx_dir / "tone.m4a", 0.5)

    state = ProjectState(
        project=Project(name="T", voiceover_path=voice),
        render_settings=RenderSettings(resolution="640x360", fps=30),
    )
    state.timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(img_a, 0.0, 2.0, AssetType.IMAGE),
            TimedVisualAsset(img_b, 2.0, 4.0, AssetType.IMAGE),
        ],
        transition_settings=TransitionSettings(
            effect_mode=TransitionEffectMode.MANUAL,
            effect="fade",
            duration=0.5,
            sound_folder=sfx_dir,
            sound_mode=TransitionSoundMode.RANDOM,
            sound_volume=0.35,
        ),
    )

    composer = TimelineComposer(service)
    audio = composer.compose_audio(state, tmp_path / "out")
    info = service.probe_audio(audio)
    assert abs(info.duration - 4.0) < 0.5


def test_deterministic_rerender_same_selection(tmp_path: Path, require_transitions) -> None:
    from autotube.timeline.transitions import select_effects

    state = ProjectState()
    state.timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(Path("a.png"), 0.0, 2.0, AssetType.IMAGE),
            TimedVisualAsset(Path("b.png"), 2.0, 4.0, AssetType.IMAGE),
            TimedVisualAsset(Path("c.png"), 4.0, 6.0, AssetType.IMAGE),
        ],
        transition_settings=TransitionSettings(
            effect_mode=TransitionEffectMode.RANDOM, duration=0.5
        ),
    )
    from autotube.timeline.transitions import applicable_boundaries

    boundaries = applicable_boundaries(state.timeline)
    first = select_effects(boundaries, state.timeline.transition_settings, state.project_id)
    second = select_effects(boundaries, state.timeline.transition_settings, state.project_id)
    assert first == second
