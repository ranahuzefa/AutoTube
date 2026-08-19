"""Guarded AI keyword engine with deterministic local fallback."""

from __future__ import annotations

import logging
import threading

from ..state import KeywordSource, SegmentState
from ..stock.keywords import LocalKeywordService
from .config import AIConfig
from .models import AISegmentInput, BatchKeywordResult
from .prompts import build_ai_inputs, build_user_prompt
from .providers import AIKeywordProvider
from .registry import default_ai_provider_registry
from .validation import validate_ai_keywords

logger = logging.getLogger(__name__)

_TIMESTAMP_EPSILON = 1e-3


class AIKeywordEngine:
    """Generate visual keywords via AI, falling back to local on any failure."""

    def __init__(
        self,
        config: AIConfig,
        provider: AIKeywordProvider | None = None,
        local_service: LocalKeywordService | None = None,
    ) -> None:
        self.config = config
        self._provider = provider or default_ai_provider_registry().build_provider(config)
        self._local = local_service or LocalKeywordService()
        self._config_error = bool(config.errors())

    def generate_keywords(self, segment: SegmentState) -> list[str]:
        """Single-segment keyword generation (existing KeywordService API)."""
        result = self.generate_keywords_batch([segment]).get(segment.segment_id)
        if result is None:
            return self._local.generate_keywords(segment)
        return result.keywords

    def generate_keywords_batch(
        self,
        segments: list[SegmentState],
        *,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, BatchKeywordResult]:
        results: dict[str, BatchKeywordResult] = {}

        if not self.config.enabled or self._config_error:
            return self._local_batch(segments)

        if cancel_event is not None and cancel_event.is_set():
            from ..exceptions import AICancelledError

            raise AICancelledError("AI keyword generation cancelled.")

        inputs = build_ai_inputs(segments)
        if not inputs:
            return results

        chunks, local_ids = self._chunk(inputs)

        for segment in segments:
            if segment.segment_id in local_ids:
                results[segment.segment_id] = self._local_result(segment)

        ai_unavailable = False
        for chunk in chunks:
            if cancel_event is not None and cancel_event.is_set():
                from ..exceptions import AICancelledError

                raise AICancelledError("AI keyword generation cancelled.")

            if ai_unavailable:
                self._apply_local_chunk(chunk, segments, results)
                continue

            try:
                outputs = self._provider.generate(chunk, cancel_event=cancel_event)
            except Exception as exc:  # noqa: BLE001 - AI failure must never break workflow
                logger.warning("AI keyword generation failed; using local fallback: %s", exc)
                ai_unavailable = True
                self._apply_local_chunk(chunk, segments, results)
                continue

            self._apply_ai_chunk(chunk, outputs, segments, results)

        return results

    def _chunk(
        self, inputs: list[AISegmentInput]
    ) -> tuple[list[list[AISegmentInput]], set[str]]:
        chunks: list[list[AISegmentInput]] = []
        current: list[AISegmentInput] = []
        local_ids: set[str] = set()

        for item in inputs:
            single_prompt_len = len(build_user_prompt([item]))
            if single_prompt_len > self.config.max_input_chars:
                local_ids.add(item.segment_id)
                continue

            candidate = current + [item]
            if len(candidate) > self.config.batch_size:
                if current:
                    chunks.append(current)
                current = [item]
                continue

            if len(build_user_prompt(candidate)) > self.config.max_input_chars:
                if current:
                    chunks.append(current)
                current = [item]
                continue

            current = candidate

        if current:
            chunks.append(current)

        return chunks, local_ids

    def _apply_ai_chunk(
        self,
        chunk: list[AISegmentInput],
        outputs: list,
        segments: list[SegmentState],
        results: dict[str, BatchKeywordResult],
    ) -> None:
        by_id = {o.segment_id: o for o in outputs}
        segment_by_id = {s.segment_id: s for s in segments}

        for item in chunk:
            segment = segment_by_id.get(item.segment_id)
            if segment is None:
                continue

            output = by_id.get(item.segment_id)
            if output is None:
                results[item.segment_id] = self._local_result(segment)
                continue

            if not self._timestamps_match(item, output):
                results[item.segment_id] = self._local_result(segment)
                continue

            keywords = validate_ai_keywords(output.keywords, self.config)
            if not keywords:
                results[item.segment_id] = self._local_result(segment)
                continue

            results[item.segment_id] = BatchKeywordResult(
                segment_id=item.segment_id,
                keywords=keywords,
                source=KeywordSource.AI,
            )

    def _apply_local_chunk(
        self,
        chunk: list[AISegmentInput],
        segments: list[SegmentState],
        results: dict[str, BatchKeywordResult],
    ) -> None:
        segment_by_id = {s.segment_id: s for s in segments}
        for item in chunk:
            segment = segment_by_id.get(item.segment_id)
            if segment is None:
                continue
            results[item.segment_id] = self._local_result(segment)

    def _local_batch(
        self, segments: list[SegmentState]
    ) -> dict[str, BatchKeywordResult]:
        return {s.segment_id: self._local_result(s) for s in segments}

    def _local_result(self, segment: SegmentState) -> BatchKeywordResult:
        return BatchKeywordResult(
            segment_id=segment.segment_id,
            keywords=self._local.generate_keywords(segment),
            source=KeywordSource.LOCAL,
        )

    @staticmethod
    def _timestamps_match(item: AISegmentInput, output) -> bool:
        return (
            abs(item.start - output.start) <= _TIMESTAMP_EPSILON
            and abs(item.end - output.end) <= _TIMESTAMP_EPSILON
        )
