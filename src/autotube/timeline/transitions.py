"""Pure transition planning, effect registry, sound scanning, and selection.

This module never touches FFmpeg, the GUI, or the network. It is the single
source of truth for detecting eligible boundaries, validating transition
settings, and deterministically selecting effects and sound files.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from ..constants import SUPPORTED_TRANSITION_SOUND_EXTENSIONS
from ..exceptions import ValidationError
from .missing import is_missing_slot
from .types import (
    TimelineState,
    TimedVisualAsset,
    TransitionEffectMode,
    TransitionSettings,
    TransitionSoundMode,
)

_ADJACENCY_EPSILON = 1e-6


@dataclass(frozen=True)
class TransitionEffectPreset:
    preset_id: str
    name: str
    xfade_name: str


class TransitionEffectRegistry:
    def __init__(self) -> None:
        self._presets: dict[str, TransitionEffectPreset] = {}

    def register(self, preset: TransitionEffectPreset) -> None:
        self._presets[preset.preset_id] = preset

    def get(self, preset_id: str) -> TransitionEffectPreset:
        if preset_id not in self._presets:
            raise ValidationError(f"Unknown transition effect: {preset_id!r}")
        return self._presets[preset_id]

    def list_all(self) -> list[TransitionEffectPreset]:
        return list(self._presets.values())

    def ids(self) -> list[str]:
        return list(self._presets.keys())


@dataclass
class TransitionBoundary:
    index: int
    time: float
    left_duration: float
    right_duration: float
    left_asset: TimedVisualAsset
    right_asset: TimedVisualAsset


_DEFAULT_EFFECTS = [
    ("fade", "Fade", "fade"),
    ("fadeblack", "Fade Black", "fadeblack"),
    ("fadewhite", "Fade White", "fadewhite"),
    ("wipeleft", "Wipe Left", "wipeleft"),
    ("wiperight", "Wipe Right", "wiperight"),
    ("wipeup", "Wipe Up", "wipeup"),
    ("wipedown", "Wipe Down", "wipedown"),
    ("slideleft", "Slide Left", "slideleft"),
    ("slideright", "Slide Right", "slideright"),
    ("slideup", "Slide Up", "slideup"),
    ("slidedown", "Slide Down", "slidedown"),
    ("dissolve", "Dissolve", "dissolve"),
    ("circleopen", "Circle Open", "circleopen"),
    ("circleclose", "Circle Close", "circleclose"),
    ("smoothleft", "Smooth Left", "smoothleft"),
    ("smoothright", "Smooth Right", "smoothright"),
    ("smoothup", "Smooth Up", "smoothup"),
    ("smoothdown", "Smooth Down", "smoothdown"),
    ("pixelize", "Pixelize", "pixelize"),
    ("distance", "Distance", "distance"),
    ("radial", "Radial", "radial"),
    ("hblur", "Horizontal Blur", "hblur"),
    ("zoomin", "Zoom In", "zoomin"),
]


def default_transition_effect_registry() -> TransitionEffectRegistry:
    """Return a registry populated with the built-in xfade presets."""
    registry = TransitionEffectRegistry()
    for preset_id, name, xfade_name in _DEFAULT_EFFECTS:
        registry.register(
            TransitionEffectPreset(
                preset_id=preset_id, name=name, xfade_name=xfade_name
            )
        )
    return registry


def scan_sound_folder(folder: Path) -> list[Path]:
    """Return deterministic sorted supported audio files from a folder."""
    folder = Path(folder)
    if not folder.exists() or not folder.is_dir():
        raise ValidationError(f"Transition sound folder does not exist: {folder}")
    files = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_TRANSITION_SOUND_EXTENSIONS
    ]
    return sorted(files, key=lambda p: p.name.lower())


def applicable_boundaries(timeline: TimelineState) -> list[TransitionBoundary]:
    """Return adjacent, non-missing visual asset boundaries in timeline order."""
    assets = sorted(
        (a for a in timeline.visual_assets if not is_missing_slot(a)),
        key=lambda a: (a.start, a.end),
    )
    boundaries: list[TransitionBoundary] = []
    for index in range(len(assets) - 1):
        left = assets[index]
        right = assets[index + 1]
        if abs(left.end - right.start) > _ADJACENCY_EPSILON:
            continue
        boundaries.append(
            TransitionBoundary(
                index=len(boundaries),
                time=right.start,
                left_duration=left.end - left.start,
                right_duration=right.end - right.start,
                left_asset=left,
                right_asset=right,
            )
        )
    return boundaries


def validate_transition_settings(settings: TransitionSettings) -> None:
    """Validate transition settings independent of any specific timeline."""
    if settings.duration <= 0:
        raise ValidationError("Transition duration must be positive.")

    if not 0.0 <= settings.sound_volume <= 1.0:
        raise ValidationError("Transition sound volume must be between 0.0 and 1.0.")

    if settings.effect_mode == TransitionEffectMode.MANUAL:
        if not settings.effect:
            raise ValidationError("Manual transition effect must be selected.")

    if settings.sound_mode != TransitionSoundMode.NONE:
        if settings.sound_folder is None:
            raise ValidationError(
                "A transition sound folder is required when sound mode is enabled."
            )
        scan_sound_folder(settings.sound_folder)


def _validate_boundary_durations(
    boundaries: list[TransitionBoundary], duration: float
) -> None:
    for boundary in boundaries:
        if duration >= min(boundary.left_duration, boundary.right_duration):
            raise ValidationError(
                f"Transition duration {duration} must be shorter than both "
                f"adjacent clip durations at {boundary.time}."
            )


def select_effects(
    boundaries: list[TransitionBoundary],
    settings: TransitionSettings,
    project_id: str,
    registry: TransitionEffectRegistry | None = None,
) -> list[str]:
    """Return one effect id per boundary, or an empty list when disabled."""
    if settings.effect_mode == TransitionEffectMode.NONE or not boundaries:
        return []

    validate_transition_settings(settings)
    _validate_boundary_durations(boundaries, settings.duration)

    if settings.effect_mode == TransitionEffectMode.MANUAL:
        registry = registry or default_transition_effect_registry()
        registry.get(settings.effect or "")
        return [settings.effect or ""] * len(boundaries)

    registry = registry or default_transition_effect_registry()
    ids = registry.ids()
    if not ids:
        raise ValidationError("Transition effect registry is empty.")
    rng = random.Random(f"{project_id}:transition-effect")
    return [rng.choice(ids) for _ in boundaries]


def select_sounds(
    boundaries: list[TransitionBoundary],
    settings: TransitionSettings,
    project_id: str,
) -> list[Path | None]:
    """Return one sound path (or None) per boundary in time order."""
    if settings.sound_mode == TransitionSoundMode.NONE or not boundaries:
        return [None] * len(boundaries)

    validate_transition_settings(settings)
    if settings.sound_folder is None:
        raise ValidationError("Transition sound folder must be set.")
    files = scan_sound_folder(settings.sound_folder)
    if not files:
        raise ValidationError(
            f"Transition sound folder contains no supported audio: {settings.sound_folder}"
        )

    if settings.sound_mode == TransitionSoundMode.RANDOM:
        rng = random.Random(f"{project_id}:transition-sound")
        return [rng.choice(files) for _ in boundaries]

    return [files[index % len(files)] for index in range(len(boundaries))]
