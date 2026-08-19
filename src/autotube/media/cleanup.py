"""Safe cleanup of stale AutoTube-owned render temp files.

Only orphaned ``.partial`` (media) and ``.part`` (download) files left behind by
a hard crash are removed. Final outputs, resumable stage intermediates, user
source assets, directories, and symlinks are never touched.
"""

from __future__ import annotations

import re
from pathlib import Path

_MEDIA_TEMP = re.compile(r"^\..+\.[0-9a-f]{8}\.partial(?:\..+)?$")
_DOWNLOAD_TEMP = re.compile(r"^\..+\.part$")


def cleanup_stale_render_temps(root: Path) -> int:
    """Remove orphaned AutoTube temp files under ``root``.

    Returns the number of files removed. Best-effort: individual unlink errors
    are ignored and the offending file is simply not counted.
    """
    if not isinstance(root, Path):
        root = Path(root)
    if not root.is_dir():
        return 0

    removed = 0
    for path in root.rglob("*"):
        if path.is_symlink() or path.is_dir():
            continue
        if not (_MEDIA_TEMP.match(path.name) or _DOWNLOAD_TEMP.match(path.name)):
            continue
        try:
            path.unlink()
        except OSError:
            continue
        removed += 1
    return removed
