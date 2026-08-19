"""Timeline & visual editing engine."""

from .animations import AnimationPresetRegistry, apply_preset_to_all
from .assets import VisualAssetScanner
from .filenames import TimestampFilename, parse_timestamp_filename
from .overlap import OverlapPair, find_overlaps
from .srt import SRTParser
from .transitions import (
    TransitionBoundary,
    TransitionEffectPreset,
    TransitionEffectRegistry,
    applicable_boundaries,
    default_transition_effect_registry,
    scan_sound_folder,
    select_effects,
    select_sounds,
    validate_transition_settings,
)
from .types import (
    AssetType,
    SubtitleEntry,
    TimelineItemStatus,
    TimelineState,
    TimedVisualAsset,
    TransitionEffectMode,
    TransitionSettings,
    TransitionSoundMode,
)

__all__ = [
    "AnimationPresetRegistry",
    "AssetType",
    "OverlapPair",
    "SRTParser",
    "SubtitleEntry",
    "TimelineItemStatus",
    "TimelineState",
    "TimedVisualAsset",
    "TimestampFilename",
    "TransitionBoundary",
    "TransitionEffectMode",
    "TransitionEffectPreset",
    "TransitionEffectRegistry",
    "TransitionSettings",
    "TransitionSoundMode",
    "VisualAssetScanner",
    "applicable_boundaries",
    "apply_preset_to_all",
    "default_transition_effect_registry",
    "find_overlaps",
    "parse_timestamp_filename",
    "scan_sound_folder",
    "select_effects",
    "select_sounds",
    "validate_transition_settings",
]
