"""Missing visual asset detection, reporting, and manual replacement.

This module is pure and deterministic: it never touches FFmpeg, the network, or
the filesystem. It is the single source of truth for classifying unresolved
timeline visual slots and producing the user-facing report.
"""

from __future__ import annotations

from pathlib import Path

from ..exceptions import MissingVisualAssetsError
from .types import (
    AssetType,
    ReplacementStatus,
    TimelineItemStatus,
    TimelineState,
    TimedVisualAsset,
)


def is_missing_slot(asset: TimedVisualAsset) -> bool:
    """Return True when a timeline visual slot is unresolved.

    This is metadata-only by design. A PENDING asset with a source path is
    renderable and not considered missing; file existence is validated by the
    media processor at render time.
    """
    if asset.source_path is None:
        return True
    return asset.status in (
        TimelineItemStatus.MISSING,
        TimelineItemStatus.MANUAL_REPLACEMENT_REQUIRED,
        TimelineItemStatus.ERROR,
    )


def collect_missing_slots(timeline: TimelineState) -> list[TimedVisualAsset]:
    """Return unresolved visual slots in timeline order."""
    return sorted(
        (asset for asset in timeline.visual_assets if is_missing_slot(asset)),
        key=lambda asset: (asset.start, asset.end),
    )


def format_slot_time(seconds: float) -> str:
    """Format seconds as ``HH:MM:SS`` or ``MM:SS``-style compact timestamp.

    The report format is intentionally compact and deterministic. Durations
    under one hour use ``MM:SS``; longer durations use ``HH:MM:SS``.
    """
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _status_label(asset: TimedVisualAsset) -> str:
    if asset.status == TimelineItemStatus.ERROR:
        if asset.source == "ai":
            return "Generation Failed"
        if asset.source == "stock":
            return "Download Failed"
        return "Processing Failed"
    if asset.status == TimelineItemStatus.MANUAL_REPLACEMENT_REQUIRED:
        return "Manual Replacement Required"
    if asset.status == TimelineItemStatus.MISSING:
        return "Missing"
    if asset.source_path is None:
        return "Missing"
    return asset.status.value.title()


def _type_label(asset: TimedVisualAsset) -> str:
    label = asset.asset_type.value.title()
    if asset.source == "ai":
        return f"AI {label}"
    if asset.source == "stock":
        return f"Stock {label}"
    return label


def build_missing_asset_report(timeline: TimelineState) -> str:
    """Build a deterministic human-readable missing-asset report."""
    missing = collect_missing_slots(timeline)
    if not missing:
        return "No missing visual assets."

    lines = ["MISSING VISUAL ASSETS"]
    for index, asset in enumerate(missing, start=1):
        lines.append(
            f"{index}. {format_slot_time(asset.start)} -> {format_slot_time(asset.end)}"
        )
        lines.append(f"   Type: {_type_label(asset)}")
        lines.append(f"   Status: {_status_label(asset)}")
        if asset.error:
            lines.append(f"   Reason: {asset.error}")
        if asset.description:
            lines.append(f"   Description: {asset.description}")
        action = (
            "Resolved"
            if asset.replacement_status == ReplacementStatus.RESOLVED
            else "Manual replacement required"
        )
        lines.append(f"   Action: {action}")
        lines.append("")
    return "\n".join(lines).rstrip()


def validate_missing_slots(
    timeline: TimelineState, *, allow_missing: bool = False
) -> None:
    """Raise unless all visual slots are resolved or missing is allowed."""
    if allow_missing:
        return
    missing = collect_missing_slots(timeline)
    if missing:
        raise MissingVisualAssetsError(build_missing_asset_report(timeline))


def _infer_asset_type(path: Path) -> AssetType:
    from .constants import SUPPORTED_IMAGE_EXTENSIONS

    return (
        AssetType.IMAGE
        if path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        else AssetType.VIDEO
    )


def assign_manual_replacement(
    timeline: TimelineState,
    slot: TimedVisualAsset,
    source_path: Path,
    asset_type: AssetType | None = None,
) -> None:
    """Assign a user-provided file to a slot without changing its timing."""
    slot.source_path = Path(source_path)
    slot.asset_type = asset_type or _infer_asset_type(slot.source_path)
    slot.status = TimelineItemStatus.READY
    slot.replacement_status = ReplacementStatus.RESOLVED
    slot.source = "manual"
    slot.processed_path = None
    slot.error = None

    if slot not in timeline.visual_assets:
        timeline.visual_assets.append(slot)


def apply_scanned_replacements(
    timeline: TimelineState, scanned_assets: list[TimedVisualAsset]
) -> list[TimedVisualAsset]:
    """Assign timestamp-matched scanned assets to missing slots.

    Existing timestamp-based scanner output is matched to unresolved slots by
    exact ``(start, end)``. Original slot timing is never mutated.
    """
    by_span = {
        (asset.start, asset.end): asset
        for asset in scanned_assets
        if asset.source_path is not None
    }
    remaining: list[TimedVisualAsset] = []
    for slot in collect_missing_slots(timeline):
        replacement = by_span.get((slot.start, slot.end))
        if replacement is None or replacement.source_path is None:
            remaining.append(slot)
            continue
        assign_manual_replacement(
            timeline, slot, replacement.source_path, asset_type=replacement.asset_type
        )
    return remaining
