"""Prompt construction for AI keyword generation."""

from __future__ import annotations

import json

from ..state import SegmentState
from .models import AISegmentInput

SYSTEM_PROMPT = (
    "You convert transcript segments into concrete visual-search keywords for "
    "stock video/image sites such as Pexels and Pixabay. For each segment, "
    "return keywords that favor people, objects, places, actions, situations, "
    "and visually searchable multi-word phrases. The current segment is the "
    "primary subject; previous and next segments are context only. Avoid "
    "hashtags, full sentences, generic filler, abstract grammatical words, "
    "duplicates, and overly broad terms. Respond with exactly one JSON object "
    'shaped as {"segments":[{"segment_id":"...","start":0.0,"end":0.0,'
    '"keywords":["..."]}]}.'
)


def build_ai_inputs(segments: list[SegmentState]) -> list[AISegmentInput]:
    """Build AI inputs with previous/current/next context."""
    return [
        AISegmentInput(
            segment_id=segment.segment_id,
            text=segment.text,
            start=segment.start,
            end=segment.end,
            previous_text=segments[i - 1].text if i > 0 else None,
            next_text=segments[i + 1].text if i + 1 < len(segments) else None,
        )
        for i, segment in enumerate(segments)
    ]


def build_user_prompt(segments: list[AISegmentInput]) -> str:
    """Render a JSON object of segment inputs for the model."""
    payload = {
        "segments": [
            {
                "segment_id": segment.segment_id,
                "start": segment.start,
                "end": segment.end,
                "previous": segment.previous_text,
                "current": segment.text,
                "next": segment.next_text,
            }
            for segment in segments
        ]
    }
    return json.dumps(payload, ensure_ascii=False)


def build_messages(segments: list[AISegmentInput]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(segments)},
    ]
