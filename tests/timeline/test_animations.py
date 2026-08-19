"""Tests for animation preset registry and Apply-to-All."""

from __future__ import annotations

import pytest

from autotube.exceptions import ValidationError
from autotube.timeline.animations import (
    AnimationKind,
    AnimationPreset,
    AnimationPresetRegistry,
    apply_preset_to_all,
)
from autotube.timeline.types import SubtitleEntry


def test_registry_lookup_and_list() -> None:
    registry = AnimationPresetRegistry()
    registry.register(AnimationPreset("fade_in", "Fade In", AnimationKind.SIMPLE_FILTER))
    assert registry.get("fade_in").name == "Fade In"
    assert len(registry.list_all()) == 1


def test_register_custom_preset() -> None:
    registry = AnimationPresetRegistry()
    preset = AnimationPreset("custom", "Custom", AnimationKind.TEXT_ANIMATION)
    registry.register(preset)
    assert registry.get("custom") is preset


def test_unknown_preset() -> None:
    registry = AnimationPresetRegistry()
    with pytest.raises(ValidationError):
        registry.get("missing")


def test_apply_to_all() -> None:
    subtitles = [
        SubtitleEntry(index=1, start=0.0, end=1.0, text="A"),
        SubtitleEntry(index=2, start=1.0, end=2.0, text="B"),
    ]
    registry = AnimationPresetRegistry()
    registry.register(AnimationPreset("fade_in", "Fade In", AnimationKind.SIMPLE_FILTER))
    apply_preset_to_all(subtitles, "fade_in", registry)
    assert all(s.animation_preset == "fade_in" for s in subtitles)
