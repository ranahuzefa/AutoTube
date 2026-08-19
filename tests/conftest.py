"""Shared test fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmp_project_files(tmp_path: Path) -> tuple[Path, Path]:
    script = tmp_path / "script.txt"
    script.write_text("Hello world. This is a test.", encoding="utf-8")
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"fake mp3")
    return script, voice


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("AUTOTUBE_") and not name.startswith("AUTOTUBE_RUN_"):
            monkeypatch.delenv(name)
