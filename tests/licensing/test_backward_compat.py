"""Backward compatibility for Phase 1-9 project/settings with licensing."""

from __future__ import annotations

from pathlib import Path

from autotube.config import Settings
from autotube.state import ProjectState


def _phase9_project() -> dict:
    return {
        "project_id": "p1",
        "project": {
            "name": "Demo",
            "script_path": None,
            "voiceover_path": None,
            "music_path": None,
        },
        "render_settings": {
            "output_dir": "output",
            "resolution": "1920x1080",
            "fps": 30,
            "music_volume": 0.2,
            "whisper_model": "base",
            "caption_style": "burned",
        },
        "stages": [],
        "segments": [],
        "transcription": None,
        "timeline": {
            "subtitles": [],
            "visual_assets": [],
            "animation_preset": None,
            "rendered_path": None,
        },
        "last_error": None,
    }


def test_phase9_project_loads_without_licensing_fields() -> None:
    state = ProjectState.from_dict(_phase9_project())
    assert state.project.name == "Demo"
    assert state.timeline is not None


def test_project_serialization_has_no_licensing_keys() -> None:
    state = ProjectState.from_dict(_phase9_project())
    data = state.to_dict()
    assert "license" not in data
    assert "activation_token" not in str(data)


def test_settings_load_without_licensing_fields(tmp_path: Path) -> None:
    settings = Settings.from_dict({"output_dir": "out"})
    assert settings.output_dir == Path("out")
