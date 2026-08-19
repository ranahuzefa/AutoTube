"""Stock keyword + asset workflow with resume semantics."""

from __future__ import annotations

import threading
from pathlib import Path

from ..state import KeywordSource, PipelineStage, ProjectState, StageStatus
from ..storage import ProjectStore
from .keywords import LocalKeywordService
from .manager import StockManager
from .types import StockFilter


class StockWorkflow:
    """Prepare KEYWORDS_READY and ASSETS_READY without touching CLIPS_READY."""

    def __init__(
        self,
        keyword_service: LocalKeywordService | None = None,
        stock_manager: StockManager | None = None,
        store: ProjectStore | None = None,
        project_path: Path | None = None,
    ) -> None:
        self.keyword_service = keyword_service or LocalKeywordService()
        self.stock_manager = stock_manager
        self.store = store or ProjectStore()
        self.project_path = project_path

    def run(
        self,
        state: ProjectState,
        *,
        force: bool = False,
        cancel_event: threading.Event | None = None,
    ) -> ProjectState:
        if state.project is None:
            from ..exceptions import ValidationError

            raise ValidationError("Project must exist to run stock workflow.")

        keywords_stage = state.stage(PipelineStage.KEYWORDS_READY)
        assets_stage = state.stage(PipelineStage.ASSETS_READY)

        if force:
            keywords_stage.status = StageStatus.PENDING
            keywords_stage.error = None
            assets_stage.status = StageStatus.PENDING
            assets_stage.error = None
            for segment in state.segments:
                segment.selected_clip = None
                segment.error = None

        if keywords_stage.status in (StageStatus.PENDING, StageStatus.FAILED):
            self._run_keywords(state, cancel_event)
            keywords_stage.status = StageStatus.COMPLETED
            keywords_stage.error = None
            self._save(state)

        if assets_stage.status in (StageStatus.PENDING, StageStatus.FAILED):
            self._run_assets(state, cancel_event)
            assets_stage.status = StageStatus.COMPLETED
            assets_stage.error = None
            self._save(state)

        return state

    def _run_keywords(
        self, state: ProjectState, cancel_event: threading.Event | None
    ) -> None:
        batch_method = getattr(self.keyword_service, "generate_keywords_batch", None)
        if callable(batch_method):
            results = batch_method(state.segments, cancel_event=cancel_event)
            for segment in state.segments:
                outcome = results.get(segment.segment_id)
                if outcome is None:
                    segment.keywords = self.keyword_service.generate_keywords(segment)
                    segment.keyword_source = KeywordSource.LOCAL
                else:
                    segment.keywords = outcome.keywords
                    segment.keyword_source = outcome.source
            return

        for segment in state.segments:
            if cancel_event is not None and cancel_event.is_set():
                from ..exceptions import StockError

                raise StockError("Stock workflow cancelled.")
            segment.keywords = self.keyword_service.generate_keywords(segment)
            segment.keyword_source = KeywordSource.LOCAL

    def _run_assets(
        self, state: ProjectState, cancel_event: threading.Event | None
    ) -> None:
        if self.stock_manager is None:
            raise ValueError("StockManager is required for ASSETS_READY.")

        filter = StockFilter.from_render_settings(state.render_settings)
        output_dir = state.render_settings.output_dir

        for segment in state.segments:
            if cancel_event is not None and cancel_event.is_set():
                from ..exceptions import StockError

                raise StockError("Stock workflow cancelled.")
            self.stock_manager.resolve_segment(
                segment, filter, output_dir / "stock", cancel_event=cancel_event
            )

    def _save(self, state: ProjectState) -> None:
        if self.project_path is None:
            return
        self.store.save(state, self.project_path)
