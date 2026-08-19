"""Tests for deterministic timeline staleness detection."""

from __future__ import annotations

from pathlib import Path

from autotube.models import Project, RenderSettings
from autotube.state import ProjectState
from autotube.timeline.staleness import (
    is_timeline_stale,
    timeline_input_fingerprint,
)
from autotube.timeline.types import (
    AssetType,
    ReplacementStatus,
    SubtitleEntry,
    TimelineItemStatus,
    TimelineState,
    TimedVisualAsset,
    TransitionEffectMode,
    TransitionSoundMode,
)


def _state(tmp_path: Path) -> ProjectState:
    return ProjectState(
        project=Project(name="T", voiceover_path=tmp_path / "voice.mp3"),
        render_settings=RenderSettings(resolution="640x360", fps=30),
    )


def _state_with_timeline(tmp_path: Path) -> ProjectState:
    state = _state(tmp_path)
    state.timeline = TimelineState(
        subtitles=[SubtitleEntry(index=1, start=0.0, end=1.0, text="Hi")],
        visual_assets=[
            TimedVisualAsset(
                source_path=Path("a.png"),
                start=0.0,
                end=1.0,
                asset_type=AssetType.IMAGE,
            )
        ],
    )
    return state


def test_fingerprint_changes_when_subtitle_changes(tmp_path: Path) -> None:
    state = _state_with_timeline(tmp_path)
    before = timeline_input_fingerprint(state)
    state.timeline.subtitles[0].text = "Bye"
    assert timeline_input_fingerprint(state) != before


def test_fingerprint_changes_when_asset_timing_changes(tmp_path: Path) -> None:
    state = _state_with_timeline(tmp_path)
    before = timeline_input_fingerprint(state)
    state.timeline.visual_assets[0].end = 2.0
    assert timeline_input_fingerprint(state) != before


def test_fingerprint_changes_when_asset_status_changes(tmp_path: Path) -> None:
    state = _state_with_timeline(tmp_path)
    before = timeline_input_fingerprint(state)
    state.timeline.visual_assets[0].status = TimelineItemStatus.MISSING
    assert timeline_input_fingerprint(state) != before


def test_fingerprint_changes_when_replacement_status_changes(tmp_path: Path) -> None:
    state = _state_with_timeline(tmp_path)
    before = timeline_input_fingerprint(state)
    state.timeline.visual_assets[0].replacement_status = ReplacementStatus.RESOLVED
    assert timeline_input_fingerprint(state) != before


def test_fingerprint_changes_when_resolution_changes(tmp_path: Path) -> None:
    state = _state_with_timeline(tmp_path)
    before = timeline_input_fingerprint(state)
    state.render_settings.resolution = "1280x720"
    assert timeline_input_fingerprint(state) != before


def test_stale_when_rendered_path_missing(tmp_path: Path) -> None:
    state = _state_with_timeline(tmp_path)
    assert is_timeline_stale(state)


def test_stale_when_final_file_missing(tmp_path: Path) -> None:
    state = _state_with_timeline(tmp_path)
    final = tmp_path / "final.mp4"
    state.timeline.rendered_path = str(final)
    state.timeline.rendered_fingerprint = timeline_input_fingerprint(state)
    assert is_timeline_stale(state)


def test_not_stale_when_fingerprint_matches(tmp_path: Path) -> None:
    state = _state_with_timeline(tmp_path)
    final = tmp_path / "final.mp4"
    final.write_bytes(b"video")
    state.timeline.rendered_path = str(final)
    state.timeline.rendered_fingerprint = timeline_input_fingerprint(state)
    assert not is_timeline_stale(state)


def test_stale_when_fingerprint_differs(tmp_path: Path) -> None:
    state = _state_with_timeline(tmp_path)
    final = tmp_path / "final.mp4"
    final.write_bytes(b"video")
    state.timeline.rendered_path = str(final)
    state.timeline.rendered_fingerprint = "different"
    assert is_timeline_stale(state)


def test_fingerprint_changes_for_each_transition_knob(tmp_path: Path) -> None:
    state = _state_with_timeline(tmp_path)
    base = timeline_input_fingerprint(state)

    settings = state.timeline.transition_settings
    settings.effect_mode = TransitionEffectMode.MANUAL
    assert timeline_input_fingerprint(state) != base

    settings.effect = "fade"
    assert timeline_input_fingerprint(state) != base

    settings.duration = 1.5
    assert timeline_input_fingerprint(state) != base

    settings.sound_folder = tmp_path / "sfx"
    assert timeline_input_fingerprint(state) != base

    settings.sound_mode = TransitionSoundMode.RANDOM
    assert timeline_input_fingerprint(state) != base

    settings.sound_volume = 0.5
    assert timeline_input_fingerprint(state) != base
