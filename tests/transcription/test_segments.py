"""Tests for the deterministic SegmentBuilder."""

from __future__ import annotations

from autotube.state import SegmentState, WordState
from autotube.transcription.config import TranscriptionConfig
from autotube.transcription.segments import SegmentBuilder


def _seg(segment_id, text, start, end, words=None):
    return SegmentState(
        segment_id=segment_id,
        text=text,
        start=start,
        end=end,
        words=words or [],
    )


def _w(word, start, end):
    return WordState(word=word, start=start, end=end)


def test_merges_small_gap() -> None:
    cfg = TranscriptionConfig()
    builder = SegmentBuilder()
    out = builder.build(
        [
            _seg("a", "hello", 0.0, 1.0),
            _seg("b", "world", 1.1, 2.0),
        ],
        cfg,
        2.0,
    )
    assert len(out) == 1
    assert out[0].text == "hello world"
    assert out[0].start == 0.0
    assert out[0].end == 2.0
    assert out[0].segment_id == "a"


def test_does_not_merge_large_gap() -> None:
    cfg = TranscriptionConfig()
    out = SegmentBuilder().build(
        [_seg("a", "hello", 0.0, 1.0), _seg("b", "world", 3.0, 4.0)],
        cfg,
        4.0,
    )
    assert len(out) == 2


def test_splits_long_segment_at_word_boundary() -> None:
    cfg = TranscriptionConfig(max_segment_duration=4.0, min_segment_duration=1.0)
    words = [_w("a", 0, 1), _w("b", 1, 2), _w("c", 2, 3), _w("d", 3, 4), _w("e", 4, 5), _w("f", 5, 6)]
    seg = _seg("long", "a b c d e f", 0.0, 6.0, words)
    out = SegmentBuilder().build([seg], cfg, 6.0)
    assert len(out) == 2
    assert abs(out[0].end - 4.0) < 0.6
    assert out[0].segment_id == "long"
    assert out[1].segment_id != "long"


def test_impossible_split_left_unsplit_with_note() -> None:
    cfg = TranscriptionConfig(max_segment_duration=2.0, min_segment_duration=1.5)
    seg = _seg("x", "superlongword", 0.0, 2.5, [_w("superlongword", 0.0, 2.5)])
    out = SegmentBuilder().build([seg], cfg, 2.5)
    assert len(out) == 1
    assert "cannot be safely split" in out[0].error


def test_clamps_to_audio_duration() -> None:
    cfg = TranscriptionConfig()
    out = SegmentBuilder().build([_seg("a", "hello", 0.0, 10.0)], cfg, 5.0)
    assert out[0].end == 5.0


def test_drops_empty_segments() -> None:
    cfg = TranscriptionConfig()
    out = SegmentBuilder().build(
        [_seg("a", "   ", 0.0, 1.0), _seg("b", "ok", 1.0, 2.0)], cfg, 2.0
    )
    assert len(out) == 1
    assert out[0].text == "ok"
