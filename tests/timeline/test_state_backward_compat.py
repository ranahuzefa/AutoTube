"""Backward compatibility tests for additive TimelineState changes."""

from __future__ import annotations

from pathlib import Path

from autotube.state import ProjectState
from autotube.timeline.types import (
    ReplacementStatus,
    TimelineItemStatus,
    TimelineState,
    TimedVisualAsset,
    TransitionEffectMode,
    TransitionSettings,
    TransitionSoundMode,
)


def test_old_timed_visual_asset_loads() -> None:
    data = {
        "source_path": "C:/assets/img.png",
        "start": 0.0,
        "end": 2.0,
        "asset_type": "image",
        "status": "ready",
        "processed_path": None,
        "error": None,
    }
    asset = TimedVisualAsset.from_dict(data)
    assert asset.source_path == Path("C:/assets/img.png")
    assert asset.source == "manual"
    assert asset.description is None
    assert asset.replacement_status == ReplacementStatus.NONE


def test_old_timeline_state_loads() -> None:
    data = {
        "subtitles": [],
        "visual_assets": [
            {
                "source_path": "C:/assets/img.png",
                "start": 0.0,
                "end": 2.0,
                "asset_type": "image",
                "status": "ready",
                "processed_path": None,
                "error": None,
            }
        ],
        "animation_preset": None,
        "rendered_path": None,
    }
    timeline = TimelineState.from_dict(data)
    assert timeline.rendered_fingerprint is None
    assert timeline.rendered_at is None
    assert timeline.visual_assets[0].source == "manual"


def test_new_timeline_fields_roundtrip() -> None:
    timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(
                source_path=Path("a.png"),
                start=0.0,
                end=1.0,
                status=TimelineItemStatus.MISSING,
                replacement_status=ReplacementStatus.REQUIRED,
                description="sunset",
                source="ai",
            )
        ],
        rendered_fingerprint="abc123",
    )
    restored = TimelineState.from_dict(timeline.to_dict())
    assert restored.rendered_fingerprint == "abc123"
    assert restored.visual_assets[0].status == TimelineItemStatus.MISSING
    assert restored.visual_assets[0].replacement_status == ReplacementStatus.REQUIRED
    assert restored.visual_assets[0].description == "sunset"
    assert restored.visual_assets[0].source == "ai"


def test_project_state_timeline_roundtrip_with_new_fields() -> None:
    state = ProjectState()
    state.timeline = TimelineState(
        visual_assets=[
            TimedVisualAsset(
                source_path=None,
                start=5.0,
                end=10.0,
                status=TimelineItemStatus.MISSING,
                replacement_status=ReplacementStatus.REQUIRED,
            )
        ],
        rendered_fingerprint="hash",
    )
    restored = ProjectState.from_dict(state.to_dict())
    assert restored.timeline.visual_assets[0].start == 5.0
    assert restored.timeline.visual_assets[0].end == 10.0
    assert restored.timeline.rendered_fingerprint == "hash"


def test_old_timeline_without_transition_settings_loads_defaults() -> None:
    data = {
        "subtitles": [],
        "visual_assets": [],
        "animation_preset": None,
        "rendered_path": None,
    }
    timeline = TimelineState.from_dict(data)
    assert timeline.transition_settings == TransitionSettings()
    assert timeline.transition_settings.effect_mode == TransitionEffectMode.NONE
    assert timeline.transition_settings.sound_mode == TransitionSoundMode.NONE


def test_transition_settings_roundtrip() -> None:
    settings = TransitionSettings(
        effect_mode=TransitionEffectMode.MANUAL,
        effect="fade",
        duration=1.5,
        sound_folder=Path("C:/sfx"),
        sound_mode=TransitionSoundMode.SEQUENTIAL,
        sound_volume=0.5,
    )
    restored = TransitionSettings.from_dict(settings.to_dict())
    assert restored == settings
    assert restored.sound_folder == Path("C:/sfx")
