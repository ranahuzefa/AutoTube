#!/usr/bin/env python
"""Stdlib-only release artifact security audit.

Walks the PyInstaller ``dist/autotube`` folder and fails if forbidden artifacts
are present. This script is a release gate, not part of the shipped application.

Usage:
    python packaging/verify_artifact.py [dist/autotube]
"""

from __future__ import annotations

import sys
import re
from pathlib import Path

FORBIDDEN_NAMES = {
    "tests",
    "pytest",
    "_pytest",
    "licensing_server",
    "signing.key",
    ".env",
}

FORBIDDEN_SUBSTRINGS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN ENCRYPTED PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
)

# Broad, plausible secret patterns. The goal is to catch an accidentally
# committed/literal secret, not to prove a negative against every possibility.
FORBIDDEN_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9]{20,}"),
    re.compile(rb"(?i)(pexels_api_key|pixabay_api_key)\s*[:=]\s*[A-Za-z0-9_\-]{8,}"),
)


def _should_scan(path: Path) -> bool:
    return path.suffix.lower() in {
        ".py", ".txt", ".json", ".pem", ".key", ".env", ".cfg", ".toml",
        ".md", ".iss", ".spec", ".xml", ".yaml", ".yml",
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]) if args else Path("dist/autotube")
    if not root.exists():
        print(f"ERROR: artifact directory not found: {root}", file=sys.stderr)
        return 1

    failures: list[str] = []
    scanned = 0
    for path in root.rglob("*"):
        if path.is_dir():
            if path.name.lower() in FORBIDDEN_NAMES:
                failures.append(f"Forbidden directory: {path}")
            continue

        rel = path.relative_to(root)
        if any(part.lower() in FORBIDDEN_NAMES for part in rel.parts):
            failures.append(f"Forbidden path: {rel}")
            continue

        if path.name.lower() in FORBIDDEN_NAMES:
            failures.append(f"Forbidden file: {rel}")
            continue

        if not _should_scan(path):
            continue

        try:
            data = path.read_bytes()
        except OSError:
            continue
        scanned += 1

        for marker in FORBIDDEN_SUBSTRINGS:
            if marker.encode("utf-8") in data:
                failures.append(f"Forbidden private key material in: {rel}")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(data):
                failures.append(f"Forbidden secret pattern in: {rel}")

    print(f"Scanned {scanned} text/config files under {root}")
    if failures:
        print("\n".join(f"  - {f}" for f in failures))
        print(f"ERROR: {len(failures)} forbidden artifact(s) found.")
        return 1

    print("Artifact audit passed: no forbidden artifacts found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
