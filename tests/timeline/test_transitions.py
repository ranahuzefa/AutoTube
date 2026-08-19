"""Unit tests for pure transition planning and selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from autotube.exceptions import ValidationError
from autotube.timeline.transitions import (
    applicable_boundaries,
    default_transition_effect_registry,
    scan_sound_folder,
    select_effects,
    select_sounds,
    validate_transition_settings,
)
from autotube.timeline.types import (
    AssetType,
    TimelineItemStatus,
    TimelineState,
    TimedVisualAsset,
    TransitionEffectMode,
    TransitionSettings,
    TransitionSoundMode,
)


def _asset(start: float, end: float, missing: bool = False) -> TimedVisualAsset:
    return TimedVisualAsset(
        source_path=None if missing else Path(f"a_{start}.png"),
        start=start,
        end=end,
        asset_type=AssetType.IMAGE,
        status=TimelineItemStatus.MISSING if missing else TimelineItemStatus.READY,
    )


def _timeline() -> TimelineState:
    return TimelineState(
        visual_assets=[
            _asset(0.0, 2.0),
            _asset(2.0, 4.0),
            _asset(5.0, 6.0),
        ]
    )


def test_boundaries_ignore_gaps_and_missing() -> None:
    timeline = _timeline()
    timeline.visual_assets.append(_asset(6.0, 8.0, missing=True))
    boundaries = applicable_boundaries(timeline)
    assert [b.time for b in boundaries] == [2.0]


def test_boundary_requires_adjacency() -> None:
    timeline = _timeline()
    timeline.visual_assets[1].start = 2.0001
    assert applicable_boundaries(timeline) == []


def test_manual_effect_applied_to_all() -> None:
    boundaries = applicable_boundaries(_timeline())
    settings = TransitionSettings(
        effect_mode=TransitionEffectMode.MANUAL, effect="wipeleft", duration=0.5
    )
    effects = select_effects(boundaries, settings, "project")
    assert effects == ["wipeleft"]


def test_random_effect_deterministic() -> None:
    boundaries = applicable_boundaries(_timeline())
    settings = TransitionSettings(
        effect_mode=TransitionEffectMode.RANDOM, duration=0.5
    )
    first = select_effects(boundaries, settings, "project")
    second = select_effects(boundaries, settings, "project")
    assert first == second


def test_none_effect_empty() -> None:
    boundaries = applicable_boundaries(_timeline())
    assert select_effects(boundaries, TransitionSettings(), "project") == []


def test_sequential_sounds_cycle() -> None:
    folder = Path("sounds")
    boundaries = applicable_boundaries(_timeline())
    settings = TransitionSettings(
        sound_mode=TransitionSoundMode.SEQUENTIAL, sound_folder=folder, duration=0.5
    )
    # Patch scan to avoid filesystem dependency.
    import autotube.timeline.transitions as mod

    files = [Path("a.mp3"), Path("b.wav")]
    original = mod.scan_sound_folder
    mod.scan_sound_folder = lambda f: files
    try:
        result = select_sounds(boundaries, settings, "project")
    finally:
        mod.scan_sound_folder = original
    assert result == [files[0]]


def test_random_sounds_deterministic() -> None:
    folder = Path("sounds")
    boundaries = applicable_boundaries(_timeline())
    settings = TransitionSettings(
        sound_mode=TransitionSoundMode.RANDOM, sound_folder=folder, duration=0.5
    )
    import autotube.timeline.transitions as mod

    files = [Path("a.mp3"), Path("b.wav"), Path("c.mp3")]
    original = mod.scan_sound_folder
    mod.scan_sound_folder = lambda f: files
    try:
        first = select_sounds(boundaries, settings, "project")
        second = select_sounds(boundaries, settings, "project")
    finally:
        mod.scan_sound_folder = original
    assert first == second


def test_scan_sound_folder_sorted_and_filtered(tmp_path: Path) -> None:
    for name in ["c.mp3", "a.wav", "b.txt", "d.mp4"]:
        (tmp_path / name).write_bytes(b"x")
    assert [p.name for p in scan_sound_folder(tmp_path)] == ["a.wav", "c.mp3"]


def test_validation_rejects_bad_combos() -> None:
    with pytest.raises(ValidationError):
        validate_transition_settings(TransitionSettings(duration=0))
    with pytest.raises(ValidationError):
        validate_transition_settings(TransitionSettings(sound_volume=1.5))
    with pytest.raises(ValidationError):
        validate_transition_settings(
            TransitionSettings(effect_mode=TransitionEffectMode.MANUAL, effect=None)
        )
    with pytest.raises(ValidationError):
        validate_transition_settings(
            TransitionSettings(sound_mode=TransitionSoundMode.RANDOM, sound_folder=None)
        )


def test_validation_rejects_duration_at_boundary() -> None:
    boundaries = applicable_boundaries(_timeline())
    settings = TransitionSettings(effect_mode=TransitionEffectMode.RANDOM, duration=2.0)
    with pytest.raises(ValidationError):
        select_effects(boundaries, settings, "project")


def test_registry_lists_curated_effects() -> None:
    registry = default_transition_effect_registry()
    ids = registry.ids()
    assert "fade" in ids
    assert "fadeblack" in ids
    assert "wipeleft" in ids
    assert "zoomin" in ids
