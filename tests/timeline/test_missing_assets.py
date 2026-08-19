"""Tests for missing visual asset detection, reporting, and replacement."""

from __future__ import annotations

from pathlib import Path

import pytest

from autotube.exceptions import MissingVisualAssetsError, ValidationError
from autotube.timeline.missing import (
    apply_scanned_replacements,
    assign_manual_replacement,
    build_missing_asset_report,
    collect_missing_slots,
    format_slot_time,
    is_missing_slot,
    validate_missing_slots,
)
from autotube.timeline.types import (
    AssetType,
    ReplacementStatus,
    TimelineItemStatus,
    TimelineState,
    TimedVisualAsset,
)


def _slot(
    start: float,
    end: float,
    *,
    source_path: Path | None = None,
    status: TimelineItemStatus = TimelineItemStatus.PENDING,
    asset_type: AssetType = AssetType.IMAGE,
) -> TimedVisualAsset:
    return TimedVisualAsset(
        source_path=source_path,
        start=start,
        end=end,
        asset_type=asset_type,
        status=status,
    )


def test_missing_when_no_source_path() -> None:
    assert is_missing_slot(_slot(0.0, 1.0))


def test_missing_status_values() -> None:
    for status in (
        TimelineItemStatus.MISSING,
        TimelineItemStatus.MANUAL_REPLACEMENT_REQUIRED,
        TimelineItemStatus.ERROR,
    ):
        assert is_missing_slot(_slot(0.0, 1.0, source_path=Path("x.png"), status=status))


def test_pending_with_source_is_not_missing() -> None:
    assert not is_missing_slot(_slot(0.0, 1.0, source_path=Path("x.png")))


def test_ready_with_source_is_not_missing() -> None:
    assert not is_missing_slot(
        _slot(0.0, 1.0, source_path=Path("x.png"), status=TimelineItemStatus.READY)
    )


def test_collect_missing_slots_sorted() -> None:
    timeline = TimelineState(
        visual_assets=[
            _slot(5.0, 6.0, status=TimelineItemStatus.MISSING),
            _slot(1.0, 2.0),
            _slot(3.0, 4.0, source_path=Path("x.png")),
        ]
    )
    slots = collect_missing_slots(timeline)
    assert [(s.start, s.end) for s in slots] == [(1.0, 2.0), (5.0, 6.0)]


def test_report_contains_required_fields() -> None:
    slot = _slot(5.0, 10.0, status=TimelineItemStatus.ERROR, asset_type=AssetType.VIDEO)
    slot.source = "ai"
    slot.error = "Provider/API failure"
    slot.description = "sunset drone shot"
    slot.replacement_status = ReplacementStatus.REQUIRED
    timeline = TimelineState(visual_assets=[slot])

    report = build_missing_asset_report(timeline)
    assert "00:05 -> 00:10" in report
    assert "Type: AI Video" in report
    assert "Status: Generation Failed" in report
    assert "Reason: Provider/API failure" in report
    assert "Description: sunset drone shot" in report
    assert "Action: Manual replacement required" in report


def test_report_no_missing() -> None:
    assert build_missing_asset_report(TimelineState()) == "No missing visual assets."


def test_validation_mode_raises() -> None:
    timeline = TimelineState(visual_assets=[_slot(0.0, 1.0)])
    with pytest.raises(MissingVisualAssetsError) as excinfo:
        validate_missing_slots(timeline, allow_missing=False)
    assert "MISSING VISUAL ASSETS" in excinfo.value.report
    assert isinstance(excinfo.value, ValidationError)


def test_continue_mode_allows_missing() -> None:
    timeline = TimelineState(visual_assets=[_slot(0.0, 1.0)])
    validate_missing_slots(timeline, allow_missing=True)


def test_manual_replacement_preserves_timing() -> None:
    timeline = TimelineState()
    slot = _slot(12.0, 15.0, status=TimelineItemStatus.MISSING)
    timeline.visual_assets.append(slot)

    assign_manual_replacement(timeline, slot, Path("replacement.png"))

    assert slot.start == 12.0
    assert slot.end == 15.0
    assert slot.source_path == Path("replacement.png")
    assert slot.asset_type == AssetType.IMAGE
    assert slot.status == TimelineItemStatus.READY
    assert slot.replacement_status == ReplacementStatus.RESOLVED
    assert slot.error is None
    assert collect_missing_slots(timeline) == []


def test_manual_replacement_video_type() -> None:
    timeline = TimelineState()
    slot = _slot(0.0, 2.0, status=TimelineItemStatus.MISSING)
    timeline.visual_assets.append(slot)
    assign_manual_replacement(timeline, slot, Path("replacement.mp4"))
    assert slot.asset_type == AssetType.VIDEO


def test_scanned_replacements_preserve_timing() -> None:
    timeline = TimelineState(
        visual_assets=[
            _slot(5.0, 7.0, status=TimelineItemStatus.MISSING),
        ]
    )
    scanned = [
        TimedVisualAsset(
            source_path=Path("0005--0007.png"),
            start=5.0,
            end=7.0,
            asset_type=AssetType.IMAGE,
            status=TimelineItemStatus.READY,
        )
    ]

    remaining = apply_scanned_replacements(timeline, scanned)

    assert remaining == []
    slot = timeline.visual_assets[0]
    assert slot.start == 5.0
    assert slot.end == 7.0
    assert slot.source_path == Path("0005--0007.png")
    assert slot.status == TimelineItemStatus.READY
    assert slot.replacement_status == ReplacementStatus.RESOLVED


def test_scanned_replacements_no_match() -> None:
    timeline = TimelineState(visual_assets=[_slot(5.0, 7.0, status=TimelineItemStatus.MISSING)])
    scanned = [
        TimedVisualAsset(
            source_path=Path("0001--0002.png"),
            start=1.0,
            end=2.0,
            asset_type=AssetType.IMAGE,
            status=TimelineItemStatus.READY,
        )
    ]

    remaining = apply_scanned_replacements(timeline, scanned)

    assert len(remaining) == 1
    assert remaining[0].start == 5.0
    assert remaining[0].end == 7.0


def test_format_slot_time() -> None:
    assert format_slot_time(0.0) == "00:00"
    assert format_slot_time(5.0) == "00:05"
    assert format_slot_time(300.0) == "05:00"
    assert format_slot_time(3661.0) == "01:01:01"
