"""Tests for local visual asset scanning."""

from __future__ import annotations

from pathlib import Path

from autotube.timeline.assets import VisualAssetScanner
from autotube.timeline.types import AssetType


def test_scan_valid_assets(tmp_path: Path) -> None:
    (tmp_path / "0001--0002.png").write_bytes(b"img")
    (tmp_path / "0015--0016.mp4").write_bytes(b"vid")
    assets, warnings = VisualAssetScanner().scan(tmp_path)
    assert len(assets) == 2
    assert assets[0].start == 1.0
    assert assets[0].end == 2.0
    assert assets[0].asset_type == AssetType.IMAGE
    assert assets[1].start == 15.0
    assert assets[1].asset_type == AssetType.VIDEO
    assert warnings == []


def test_invalid_filename_warns_and_skips(tmp_path: Path) -> None:
    (tmp_path / "random.png").write_bytes(b"img")
    assets, warnings = VisualAssetScanner().scan(tmp_path)
    assert assets == []
    assert len(warnings) == 1


def test_missing_folder() -> None:
    assets, warnings = VisualAssetScanner().scan(Path("/nonexistent"))
    assert assets == []
    assert warnings
