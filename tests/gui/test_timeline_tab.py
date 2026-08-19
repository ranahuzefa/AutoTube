"""Tests for timeline tab failure/cancellation recovery."""

from __future__ import annotations

import pytest

from autotube.gui.timeline_tab import TimelineTab


@pytest.fixture
def tab(qt_app):
    return TimelineTab()


def test_cancel_shows_feedback(tab: TimelineTab) -> None:
    import threading

    tab._cancel_event = threading.Event()
    tab._cancel()
    assert tab.warnings_label.text() == "Cancelling..."


def test_on_cancelled_resets_controls(tab: TimelineTab) -> None:
    from autotube.state import ProjectState

    tab.set_state(ProjectState())
    tab.render_button.setEnabled(False)
    tab.cancel_button.setEnabled(True)
    tab._worker = object()
    tab._on_cancelled("Pipeline cancelled.")
    assert tab._worker is None
    assert tab.render_button.isEnabled()
    assert not tab.cancel_button.isEnabled()
    assert "cancelled" in tab.warnings_label.text()


def test_on_finished_handles_empty_artifacts(tab: TimelineTab) -> None:
    from autotube.state import ProjectState

    tab.set_state(ProjectState())
    tab.render_button.setEnabled(False)
    tab.cancel_button.setEnabled(True)
    tab._worker = object()
    tab._on_finished("fallback")
    assert "Rendered: fallback" in tab.warnings_label.text()
    assert tab.render_button.isEnabled()
    assert not tab.cancel_button.isEnabled()


def test_build_failure_surfaces_error(tab: TimelineTab, monkeypatch) -> None:
    from autotube.state import ProjectState

    tab.set_state(ProjectState())

    def _boom():
        raise RuntimeError("no providers")

    monkeypatch.setattr(tab, "_build_orchestrator", _boom)
    monkeypatch.setattr(
        "autotube.licensing.runtime.ensure_usable_and_fresh",
        lambda state=None, **kwargs: state,
    )
    tab._render()
    assert tab._worker is None
    assert "Cannot start render" in tab.warnings_label.text()
    assert tab.render_button.isEnabled()
