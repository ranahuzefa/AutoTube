"""Pure pipeline helpers for timeline-aware stage orchestration."""

from __future__ import annotations

from ..state import PipelineStage, ProjectState, StageStatus
from .types import TimelineState


TIMELINE_RENDER_STAGES: tuple[PipelineStage, ...] = (
    PipelineStage.CLIPS_READY,
    PipelineStage.COMPOSED,
    PipelineStage.AUDIO_READY,
    PipelineStage.CAPTIONS_READY,
    PipelineStage.COMPLETED,
)

TIMELINE_SKIP_STAGES: tuple[PipelineStage, ...] = (
    PipelineStage.TRANSCRIBED,
    PipelineStage.SEGMENTS_READY,
    PipelineStage.KEYWORDS_READY,
    PipelineStage.ASSETS_READY,
)


def has_timeline_content(state: ProjectState) -> bool:
    """Return True when the project has timeline content to render."""
    timeline = state.timeline
    if timeline is None:
        return False
    return bool(timeline.visual_assets) or bool(timeline.subtitles)


def mark_timeline_stages_skipped(state: ProjectState) -> None:
    """Mark timeline's not-required early stages as SKIPPED."""
    for stage in TIMELINE_SKIP_STAGES:
        stage_state = state.stage(stage)
        stage_state.status = StageStatus.SKIPPED
        stage_state.error = None
        stage_state.artifacts = []


def clear_timeline_stage(state: ProjectState, stage: PipelineStage) -> None:
    """Reset a single timeline render stage to PENDING."""
    stage_state = state.stage(stage)
    stage_state.status = StageStatus.PENDING
    stage_state.error = None
    stage_state.artifacts = []


def invalidate_timeline_render_stages(state: ProjectState) -> None:
    """Reset all timeline render stages before a stale re-render."""
    for stage in TIMELINE_RENDER_STAGES:
        clear_timeline_stage(state, stage)


def timeline_total_duration(state: ProjectState) -> float:
    """Compute timeline duration without media probing.

    The composer may probe audio separately; this helper is useful for
    stage-level validation and tests that do not have real media.
    """
    timeline = state.timeline
    if timeline is None:
        raise ValueError("No timeline to compute duration.")
    durations = [asset.end for asset in timeline.visual_assets]
    durations.extend(subtitle.end for subtitle in timeline.subtitles)
    if not durations:
        raise ValueError("Timeline has no duration source.")
    return max(durations)
