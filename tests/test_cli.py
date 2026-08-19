"""Tests for the CLI entry point (headless paths only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from autotube.cli import main
from autotube.state import PipelineStage, ProjectState
from autotube.storage import ProjectStore


@pytest.fixture(autouse=True)
def _isolate_logs(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "autotube.logging_setup.default_log_directory", lambda: tmp_path / "logs"
    )


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "autotube" in capsys.readouterr().out


def test_new_project(tmp_path: Path, tmp_project_files, capsys: pytest.CaptureFixture[str]) -> None:
    script, voice = tmp_project_files
    code = main(
        [
            "--new",
            "--name",
            "Demo",
            "--script",
            str(script),
            "--voiceover",
            str(voice),
            "--output",
            str(tmp_path / "out"),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out.strip()
    project_path = Path(out)
    state = ProjectStore().load(project_path)
    assert state.project.name == "Demo"
    assert state.render_settings.output_dir == tmp_path / "out"
    assert state.next_pending_stage() == PipelineStage.TRANSCRIBED


def test_new_project_missing_input(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--new", "--name", "Demo"])
    assert code == 2
    assert "Error" in capsys.readouterr().err


def test_resume_reports_next_stage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state = ProjectState()
    path = tmp_path / "project.json"
    ProjectStore().save(state, path)
    code = main(["--resume", str(path)])
    assert code == 0
    assert capsys.readouterr().out.strip() == "transcribed"


def test_license_status_defaults_not_activated(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from autotube.licensing.storage import LicenseStore

    original = LicenseStore._default_directory
    LicenseStore._default_directory = staticmethod(lambda: tmp_path)
    try:
        code = main(["--license-status"])
    finally:
        LicenseStore._default_directory = staticmethod(original)
    assert code == 0
    assert capsys.readouterr().out.strip() == "not_activated"


def test_run_requires_license(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from autotube.licensing.storage import LicenseStore

    state = ProjectState()
    path = tmp_path / "project.json"
    ProjectStore().save(state, path)

    original = LicenseStore._default_directory
    LicenseStore._default_directory = staticmethod(lambda: tmp_path)
    try:
        code = main(["--run", str(path)])
    finally:
        LicenseStore._default_directory = staticmethod(original)
    assert code == 3
    assert "License required" in capsys.readouterr().err


def test_run_requires_ffmpeg(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch) -> None:
    from autotube.licensing.storage import LicenseStore
    from autotube.licensing.types import LicenseState, LicenseStatus

    store = LicenseStore(directory=tmp_path)
    store.save(LicenseState(status=LicenseStatus.ACTIVATED))

    state = ProjectState()
    path = tmp_path / "project.json"
    ProjectStore().save(state, path)

    monkeypatch.setattr("autotube.licensing.storage.LicenseStore._default_directory", staticmethod(lambda: tmp_path))
    monkeypatch.setattr("autotube.media.detection._which", lambda name: None)
    monkeypatch.setattr("autotube.media.detection._bundled_candidates", lambda name: [])

    code = main(["--run", str(path)])
    assert code == 4
    assert "ffmpeg" in capsys.readouterr().err
