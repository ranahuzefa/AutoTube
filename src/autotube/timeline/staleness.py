"""Deterministic timeline staleness detection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..state import ProjectState
from .missing import collect_missing_slots


def _asset_fingerprint(asset) -> list:
    return [
        asset.start,
        asset.end,
        asset.asset_type.value,
        asset.status.value,
        str(asset.source_path) if asset.source_path else None,
        str(asset.processed_path) if asset.processed_path else None,
        asset.error,
        asset.source,
        asset.description,
        asset.replacement_status.value,
    ]


def timeline_input_fingerprint(state: ProjectState) -> str:
    """Return a deterministic hash of the timeline inputs and render spec.

    The hash changes whenever visual slot metadata, subtitles, or relevant
    render settings change. It never hashes media bytes.
    """
    timeline = state.timeline
    settings = state.render_settings

    assets = sorted(
        timeline.visual_assets if timeline else [],
        key=lambda asset: (asset.start, asset.end, str(asset.source_path or "")),
    )
    subtitles = sorted(
        timeline.subtitles if timeline else [],
        key=lambda subtitle: (subtitle.start, subtitle.end, subtitle.text),
    )

    transition_settings = timeline.transition_settings if timeline else None
    payload = {
        "assets": [_asset_fingerprint(asset) for asset in assets],
        "subtitles": [
            [
                subtitle.start,
                subtitle.end,
                subtitle.text,
                subtitle.animation_preset,
            ]
            for subtitle in subtitles
        ],
        "animation_preset": timeline.animation_preset if timeline else None,
        "transition_settings": {
            "effect_mode": (
                transition_settings.effect_mode.value
                if transition_settings
                else None
            ),
            "effect": transition_settings.effect if transition_settings else None,
            "duration": transition_settings.duration if transition_settings else None,
            "sound_folder": (
                str(transition_settings.sound_folder)
                if transition_settings and transition_settings.sound_folder
                else None
            ),
            "sound_mode": (
                transition_settings.sound_mode.value
                if transition_settings
                else None
            ),
            "sound_volume": (
                transition_settings.sound_volume if transition_settings else None
            ),
        },
        "output_dir": str(settings.output_dir),
        "resolution": settings.resolution,
        "fps": settings.fps,
        "music_volume": settings.music_volume,
        "caption_style": settings.caption_style,
    }

    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def is_timeline_stale(state: ProjectState, output_dir: Path | None = None) -> bool:
    """Return True when a previous timeline render is missing or out of date."""
    timeline = state.timeline
    if timeline is None:
        return False

    if timeline.rendered_path is None:
        return True

    final = Path(timeline.rendered_path)
    if not final.exists():
        return True

    current = timeline_input_fingerprint(state)
    return timeline.rendered_fingerprint != current
