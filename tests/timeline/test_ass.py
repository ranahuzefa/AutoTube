"""Tests for ASS subtitle generation."""

from __future__ import annotations

import pytest

from autotube.exceptions import ValidationError
from autotube.timeline.animations import AnimationPresetRegistry
from autotube.timeline.ass import ASSGenerator
from autotube.timeline.types import SubtitleEntry


def _registry() -> AnimationPresetRegistry:
    registry = AnimationPresetRegistry()
    from autotube.timeline.animations import (
        AnimationKind,
        AnimationPreset,
    )

    for preset_id, kind in [
        ("fade_in", AnimationKind.SIMPLE_FILTER),
        ("fade_out", AnimationKind.SIMPLE_FILTER),
        ("fade_in_out", AnimationKind.SIMPLE_FILTER),
        ("slide_up", AnimationKind.SIMPLE_FILTER),
        ("slide_down", AnimationKind.SIMPLE_FILTER),
        ("scale_in", AnimationKind.SIMPLE_FILTER),
        ("word_pop", AnimationKind.TEXT_ANIMATION),
        ("typewriter", AnimationKind.TEXT_ANIMATION),
        ("word_by_word", AnimationKind.TEXT_ANIMATION),
        ("character_by_character", AnimationKind.TEXT_ANIMATION),
        ("highlight", AnimationKind.TEXT_ANIMATION),
        ("blur_to_sharp", AnimationKind.TEXT_ANIMATION),
    ]:
        registry.register(AnimationPreset(preset_id, preset_id, kind))
    return registry


def test_header_and_playres() -> None:
    ass = ASSGenerator(_registry()).generate(
        [SubtitleEntry(index=1, start=0.0, end=1.0, text="Hi")], 640, 360
    )
    assert "ScriptType: v4.00+" in ass
    assert "PlayResX: 640" in ass
    assert "PlayResY: 360" in ass


def test_fade_in_tag() -> None:
    ass = ASSGenerator(_registry()).generate(
        [SubtitleEntry(index=1, start=0.0, end=1.0, text="Hi", animation_preset="fade_in")],
        640,
        360,
    )
    assert r"{\fad(500,0)}" in ass


def test_word_by_word_splits() -> None:
    ass = ASSGenerator(_registry()).generate(
        [
            SubtitleEntry(
                index=1,
                start=0.0,
                end=2.0,
                text="one two three",
                animation_preset="word_by_word",
            )
        ],
        640,
        360,
    )
    assert ass.count("Dialogue:") == 3  # 3 word events
    assert "one" in ass and "two" in ass and "three" in ass


def test_blur_to_sharp_static() -> None:
    ass = ASSGenerator(_registry()).generate(
        [
            SubtitleEntry(
                index=1,
                start=0.0,
                end=1.0,
                text="Blur",
                animation_preset="blur_to_sharp",
            )
        ],
        640,
        360,
    )
    assert ass.count("Dialogue:") == 1  # 1 static event


def test_unknown_preset_raises() -> None:
    with pytest.raises(ValidationError):
        ASSGenerator(_registry()).generate(
            [
                SubtitleEntry(
                    index=1,
                    start=0.0,
                    end=1.0,
                    text="X",
                    animation_preset="missing",
                )
            ],
            640,
            360,
        )
