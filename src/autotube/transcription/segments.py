"""Deterministic segment merging/splitting for transcript-derived visuals."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from ..state import SegmentState, SegmentStatus, WordState
from .config import TranscriptionConfig


class SegmentBuilder:
    """Normalize raw whisper segments into visual-ready segment state."""

    def build(
        self,
        raw_segments: list[SegmentState],
        config: TranscriptionConfig,
        audio_duration: float,
    ) -> list[SegmentState]:
        if audio_duration <= 0:
            return []

        segments = [
            self._normalize(s, audio_duration) for s in raw_segments
        ]
        segments = [s for s in segments if s.end > s.start and s.text.strip()]

        if not segments:
            return []

        merged = self._merge_gaps(segments, config.merge_gap_threshold)
        split = self._split_long(merged, config, audio_duration)
        coalesced = self._coalesce_short(split, config)
        return self._clamp(coalesced, audio_duration)

    @staticmethod
    def _normalize(segment: SegmentState, audio_duration: float) -> SegmentState:
        start = max(0.0, segment.start)
        end = min(audio_duration, max(segment.end, start))
        return replace(
            segment,
            start=start,
            end=end,
            status=SegmentStatus.PENDING,
            error=None,
            selected_clip=None,
        )

    @staticmethod
    def _merge_gaps(
        segments: list[SegmentState], threshold: float
    ) -> list[SegmentState]:
        if not segments:
            return []

        result: list[SegmentState] = []
        current = segments[0]

        for next_seg in segments[1:]:
            if next_seg.start - current.end < threshold:
                words = current.words + next_seg.words
                words = SegmentBuilder._dedupe_words(words)
                current = SegmentState(
                    segment_id=current.segment_id,
                    text=" ".join(
                        part for part in (current.text.strip(), next_seg.text.strip()) if part
                    ),
                    start=min(current.start, next_seg.start),
                    end=max(current.end, next_seg.end),
                    keywords=[],
                    selected_clip=None,
                    status=SegmentStatus.PENDING,
                    error=None,
                    words=words,
                )
            else:
                result.append(current)
                current = next_seg

        result.append(current)
        return result

    @staticmethod
    def _dedupe_words(words: list[WordState]) -> list[WordState]:
        seen: set[tuple[str, float, float]] = set()
        out: list[WordState] = []
        for w in sorted(words, key=lambda w: (w.start, w.end, w.word)):
            key = (w.word, w.start, w.end)
            if key in seen:
                continue
            seen.add(key)
            out.append(w)
        return out

    @staticmethod
    def _split_long(
        segments: list[SegmentState],
        config: TranscriptionConfig,
        audio_duration: float,
    ) -> list[SegmentState]:
        out: list[SegmentState] = []
        for segment in segments:
            if segment.end - segment.start <= config.max_segment_duration:
                out.append(segment)
                continue

            pieces = SegmentBuilder._split_one(segment, config)
            if not pieces:
                out.append(segment)
                continue

            out.extend(pieces)

        return out

    @staticmethod
    def _split_one(
        segment: SegmentState, config: TranscriptionConfig
    ) -> list[SegmentState]:
        # Prefer a word boundary that leaves enough room for the min duration.
        cut = segment.start + config.max_segment_duration
        words = segment.words
        if words:
            candidates = [
                w.end
                for w in words
                if segment.start + config.min_segment_duration
                < w.end
                < segment.end - config.min_segment_duration
            ]
            if candidates:
                cut = min(candidates, key=lambda x: abs(x - cut))

        if cut - segment.start < config.min_segment_duration or segment.end - cut < config.min_segment_duration:
            # Cannot split safely; leave unsplit and flag.
            return [replace(segment, error="segment exceeds max duration and cannot be safely split")]

        first_words = [w for w in words if w.end <= cut]
        second_words = [w for w in words if w.start >= cut]

        first = SegmentState(
            segment_id=segment.segment_id,
            text=" ".join(w.word for w in first_words).strip()
            or segment.text[: int(len(segment.text) * 0.5)].strip(),
            start=segment.start,
            end=cut,
            status=SegmentStatus.PENDING,
            words=first_words,
        )
        second = SegmentState(
            segment_id=str(uuid4()),
            text=" ".join(w.word for w in second_words).strip()
            or segment.text[int(len(segment.text) * 0.5) :].strip(),
            start=cut,
            end=segment.end,
            status=SegmentStatus.PENDING,
            words=second_words,
        )
        return [first, second]

    @staticmethod
    def _coalesce_short(
        segments: list[SegmentState], config: TranscriptionConfig
    ) -> list[SegmentState]:
        if not segments:
            return []

        out: list[SegmentState] = [segments[0]]
        for seg in segments[1:]:
            prev = out[-1]
            duration = seg.end - seg.start
            if (
                duration < config.min_segment_duration
                and prev.end - prev.start + duration <= config.max_segment_duration
            ):
                merged = SegmentState(
                    segment_id=prev.segment_id,
                    text=" ".join(
                        part for part in (prev.text.strip(), seg.text.strip()) if part
                    ),
                    start=prev.start,
                    end=seg.end,
                    status=SegmentStatus.PENDING,
                    words=SegmentBuilder._dedupe_words(prev.words + seg.words),
                )
                out[-1] = merged
            else:
                out.append(seg)

        return out

    @staticmethod
    def _clamp(
        segments: list[SegmentState], audio_duration: float
    ) -> list[SegmentState]:
        return [
            replace(
                s,
                start=max(0.0, s.start),
                end=min(audio_duration, max(s.end, s.start)),
            )
            for s in segments
            if min(audio_duration, max(s.end, s.start)) > max(0.0, s.start)
        ]
