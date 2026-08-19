"""Tests for workflow tab failure/cancellation recovery."""

from __future__ import annotations

import pytest

from autotube.gui.workflow_tab import WorkflowTab


@pytest.fixture
def tab(qt_app):
    return WorkflowTab()


def test_refresh_with_no_state_disables_buttons(tab: WorkflowTab) -> None:
    tab.set_state(None)
    assert not tab.run_button.isEnabled()
    assert not tab.cancel_button.isEnabled()


def test_on_cancelled_resets_controls(tab: WorkflowTab) -> None:
    from autotube.state import ProjectState

    tab.set_state(ProjectState())
    tab.run_button.setEnabled(False)
    tab.cancel_button.setEnabled(True)
    tab._worker = object()  # simulate active worker
    tab._on_cancelled("Pipeline cancelled.")
    assert tab._worker is None
    assert tab.run_button.isEnabled()
    assert not tab.cancel_button.isEnabled()
    assert "Cancelled" in tab.status_label.text()


def test_on_failed_resets_controls(tab: WorkflowTab) -> None:
    from autotube.state import ProjectState

    tab.set_state(ProjectState())
    tab.run_button.setEnabled(False)
    tab.cancel_button.setEnabled(True)
    tab._worker = object()
    tab._on_failed("boom")
    assert tab._worker is None
    assert tab.run_button.isEnabled()
    assert not tab.cancel_button.isEnabled()
    assert "Failed" in tab.status_label.text()


def test_build_failure_surfaces_error(tab: WorkflowTab, monkeypatch) -> None:
    from autotube.state import ProjectState

    tab.set_state(ProjectState())

    def _boom():
        raise RuntimeError("no providers")

    monkeypatch.setattr(tab, "_build_orchestrator", _boom)
    monkeypatch.setattr(
        "autotube.licensing.runtime.ensure_usable_and_fresh",
        lambda state=None, **kwargs: state,
    )
    tab._run()
    assert tab._worker is None
    assert "Cannot start" in tab.status_label.text()
    assert tab.run_button.isEnabled()
