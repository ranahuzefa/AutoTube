"""Tests for domain models."""

from __future__ import annotations

from pathlib import Path

import pytest

from autotube.exceptions import ValidationError
from autotube.models import (
    Project,
    RenderSettings,
    Script,
    Voiceover,
    validate_project,
    validate_render_settings,
)


def test_project_roundtrip(tmp_path: Path) -> None:
    project = Project(
        name="Demo",
        script_path=tmp_path / "s.txt",
        voiceover_path=tmp_path / "v.mp3",
        music_path=tmp_path / "m.mp3",
    )
    data = project.to_dict()
    restored = Project.from_dict(data)
    assert restored == project


def test_render_settings_roundtrip() -> None:
    settings = RenderSettings(output_dir=Path("out"), fps=24, music_volume=0.3)
    assert RenderSettings.from_dict(settings.to_dict()) == settings


def test_validate_project_rejects_missing_files(tmp_path: Path) -> None:
    project = Project(
        name="Demo",
        script_path=tmp_path / "missing.txt",
        voiceover_path=tmp_path / "missing.mp3",
    )
    with pytest.raises(ValidationError):
        validate_project(project)


def test_validate_project_accepts_valid(tmp_project_files) -> None:
    script, voice = tmp_project_files
    validate_project(Project(name="Demo", script_path=script, voiceover_path=voice))


def test_validate_render_settings_rejects_bad_resolution() -> None:
    with pytest.raises(ValidationError):
        validate_render_settings(RenderSettings(resolution="nope"))


def test_script_from_file(tmp_path: Path) -> None:
    path = tmp_path / "s.txt"
    path.write_text("Hello", encoding="utf-8")
    script = Script.from_file(path)
    assert script.text == "Hello"
    assert script.source_path == path
