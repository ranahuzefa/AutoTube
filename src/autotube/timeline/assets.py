"""Local visual asset folder scanning."""

from __future__ import annotations

from pathlib import Path

from .constants import SUPPORTED_IMAGE_EXTENSIONS
from .filenames import parse_timestamp_filename
from .types import AssetType, TimedVisualAsset


class VisualAssetScanner:
    """Scan a folder for timestamp-named local visual assets."""

    def scan(self, folder: Path) -> tuple[list[TimedVisualAsset], list[str]]:
        folder = Path(folder)
        if not folder.is_dir():
            return [], [f"Visual assets folder does not exist: {folder}"]

        assets: list[TimedVisualAsset] = []
        warnings: list[str] = []

        for path in sorted(folder.iterdir()):
            if not path.is_file():
                continue
            try:
                parsed = parse_timestamp_filename(path.name)
            except Exception as exc:  # noqa: BLE001 - collect per-file warnings
                warnings.append(str(exc))
                continue

            asset_type = (
                AssetType.IMAGE
                if parsed.extension in SUPPORTED_IMAGE_EXTENSIONS
                else AssetType.VIDEO
            )
            assets.append(
                TimedVisualAsset(
                    source_path=path,
                    start=parsed.start,
                    end=parsed.end,
                    asset_type=asset_type,
                )
            )

        assets.sort(key=lambda a: (a.start, a.end))
        return assets, warnings
