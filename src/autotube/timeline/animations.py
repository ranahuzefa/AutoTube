"""Extensible text-animation preset registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..exceptions import ValidationError
from .types import SubtitleEntry


class AnimationKind(str, Enum):
    SIMPLE_FILTER = "simple_filter"
    TEXT_ANIMATION = "text_animation"


@dataclass
class AnimationPreset:
    preset_id: str
    name: str
    kind: AnimationKind
    description: str = ""
    ffmpeg_filter_template: str | None = None


def default_animation_registry() -> AnimationPresetRegistry:
    """Return a registry populated with the built-in presets."""
    return _default_registry()


class AnimationPresetRegistry:
    def __init__(self) -> None:
        self._presets: dict[str, AnimationPreset] = {}

    def register(self, preset: AnimationPreset) -> None:
        self._presets[preset.preset_id] = preset

    def get(self, preset_id: str) -> AnimationPreset:
        if preset_id not in self._presets:
            raise ValidationError(f"Unknown animation preset: {preset_id!r}")
        return self._presets[preset_id]

    def list_all(self) -> list[AnimationPreset]:
        return list(self._presets.values())


def _default_registry() -> AnimationPresetRegistry:
    registry = AnimationPresetRegistry()
    simple = [
        ("fade_in", "Fade In", "fade=t=in:st=0:d=0.5"),
        ("fade_out", "Fade Out", "fade=t=out:st=0:d=0.5"),
        ("fade_in_out", "Fade In + Out", "fade=t=in:st=0:d=0.25,fade=t=out:st=0.75:d=0.25"),
        ("slide_up", "Slide Up", None),
        ("slide_down", "Slide Down", None),
        ("scale_in", "Scale In", None),
    ]
    text = [
        "word_pop",
        "typewriter",
        "word_by_word",
        "character_by_character",
        "highlight",
        "blur_to_sharp",
    ]

    for preset_id, name, template in simple:
        registry.register(
            AnimationPreset(
                preset_id=preset_id,
                name=name,
                kind=AnimationKind.SIMPLE_FILTER,
                ffmpeg_filter_template=template,
            )
        )

    for preset_id in text:
        registry.register(
            AnimationPreset(
                preset_id=preset_id,
                name=preset_id.replace("_", " ").title(),
                kind=AnimationKind.TEXT_ANIMATION,
            )
        )

    return registry


def apply_preset_to_all(
    subtitles: list[SubtitleEntry], preset_id: str, registry: AnimationPresetRegistry | None = None
) -> None:
    registry = registry or _default_registry()
    registry.get(preset_id)  # validate
    for subtitle in subtitles:
        subtitle.animation_preset = preset_id
