"""Tests for atomic storage and project/settings persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autotube.config import Settings
from autotube.exceptions import CorruptProjectError, StorageError
from autotube.state import ProjectState, StageStatus, PipelineStage
from autotube.storage import AtomicFileWriter, ProjectStore, SettingsStore


def test_atomic_writer_leaves_no_tmp(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    AtomicFileWriter(target).write_text("hello")
    assert target.read_text() == "hello"
    assert list(tmp_path.glob("*.tmp")) == []


def test_project_store_roundtrip(tmp_path: Path) -> None:
    state = ProjectState()
    state.project_id = "fixed-id"
    state.last_error = "previous failure"
    path = tmp_path / "project.json"

    ProjectStore().save(state, path)
    restored = ProjectStore().load(path)

    assert restored.project_id == "fixed-id"
    assert restored.last_error == "previous failure"
    assert restored.stage(PipelineStage.TRANSCRIBED).status == StageStatus.PENDING


def test_project_store_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(CorruptProjectError):
        ProjectStore().load(path)


def test_project_store_missing_file(tmp_path: Path) -> None:
    with pytest.raises(StorageError):
        ProjectStore().load(tmp_path / "nope.json")


def test_settings_store_roundtrip(tmp_path: Path) -> None:
    store = SettingsStore(directory=tmp_path)
    store.save(Settings(output_dir=Path("out"), fps=24))
    settings = store.load()
    assert settings.output_dir == Path("out")
    assert settings.fps == 24


def test_settings_store_defaults_when_missing(tmp_path: Path) -> None:
    store = SettingsStore(directory=tmp_path)
    settings = store.load()
    assert settings.fps == 30
    assert settings.pexels_api_key == ""


def test_project_store_writes_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "project.json"
    ProjectStore().save(ProjectState(), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert len(data["stages"]) == 9
