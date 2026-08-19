"""State-aware pipeline orchestrator.

The pipeline never fakes work. Stages without a registered service are marked
FAILED with an explicit "service not available" message.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Protocol

from ..exceptions import AutoTubeError
from ..state import PipelineStage, ProjectState, StageStatus, STAGE_ORDER

logger = logging.getLogger(__name__)


class StageRunner(Protocol):
    def __call__(self, state: ProjectState) -> Any:
        """Run a stage against project state and return its artifacts (any)."""


class Pipeline:
    """Ordered, resumable executor for the 9 pipeline stages."""

    def __init__(self) -> None:
        self._registry: dict[PipelineStage, StageRunner] = {}

    def register(self, stage: PipelineStage, runner: StageRunner) -> None:
        self._registry[stage] = runner

    def available(self, stage: PipelineStage) -> bool:
        return stage in self._registry

    def run(self, state: ProjectState, force: bool = False) -> ProjectState:
        """Run pending/failed stages in order. Completed stages are skipped."""
        for stage in STAGE_ORDER:
            stage_state = state.stage(stage)
            if not force and stage_state.status in (StageStatus.COMPLETED, StageStatus.SKIPPED):
                continue
            self._run_stage(state, stage)
        return state

    def run_stage(self, state: ProjectState, stage: PipelineStage) -> ProjectState:
        """Run a single stage explicitly."""
        self._run_stage(state, stage)
        return state

    def _run_stage(self, state: ProjectState, stage: PipelineStage) -> None:
        stage_state = state.stage(stage)
        runner = self._registry.get(stage)

        if runner is None:
            stage_state.status = StageStatus.FAILED
            stage_state.error = f"Service not available for stage '{stage.value}'."
            state.last_error = stage_state.error
            state.touch()
            logger.warning("Skipping %s: %s", stage.value, stage_state.error)
            return

        stage_state.status = StageStatus.RUNNING
        stage_state.error = None
        stage_state.started_at = _now()
        state.touch()
        logger.info("Running stage: %s", stage.value)

        try:
            result = runner(state)
        except AutoTubeError as exc:
            stage_state.status = StageStatus.FAILED
            stage_state.error = str(exc)
            state.last_error = str(exc)
            logger.exception("Stage %s failed", stage.value)
        except Exception as exc:  # noqa: BLE001 - pipeline boundary
            stage_state.status = StageStatus.FAILED
            stage_state.error = f"Unexpected error: {exc}"
            state.last_error = stage_state.error
            logger.exception("Stage %s failed unexpectedly", stage.value)
        else:
            stage_state.status = StageStatus.COMPLETED
            stage_state.error = None
            if result is not None and not isinstance(result, (list, tuple, dict, str, bytes)):
                result = [result]
            if isinstance(result, list) or isinstance(result, tuple):
                from pathlib import Path

                stage_state.artifacts = [
                    Path(item) if isinstance(item, (str, Path)) else item
                    for item in result
                    if isinstance(item, (str, Path))
                ]
            elif isinstance(result, (str, Path)):
                stage_state.artifacts = [Path(result)]
            logger.info("Stage %s completed", stage.value)
        finally:
            stage_state.finished_at = _now()
            state.touch()


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
