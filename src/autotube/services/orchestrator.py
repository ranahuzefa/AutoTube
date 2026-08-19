"""Full 9-stage pipeline orchestrator.

This orchestrator owns persistence and delegates the transcription and stock
stages to the existing Phase 3/4 workflows, while running media stages directly
against the Phase 2 media service. When a project has timeline content, the
orchestrator routes the render stages through :class:`TimelineComposer`.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..exceptions import AutoTubeError, ValidationError
from ..media.constants import video_spec_from_render_settings
from ..media.cleanup import cleanup_stale_render_temps
from ..media.service import FFmpegMediaService
from ..media.types import MotionEffect
from ..state import (
    PipelineStage,
    ProjectState,
    SegmentStatus,
    StageStatus,
    STAGE_ORDER,
)
from ..storage import ProjectStore
from ..timeline.composer import TimelineComposer
from ..timeline.composer_stages import (
    TIMELINE_RENDER_STAGES,
    TIMELINE_SKIP_STAGES,
    has_timeline_content,
    invalidate_timeline_render_stages,
)
from ..timeline.missing import (
    build_missing_asset_report,
    is_missing_slot,
    validate_missing_slots,
)
from ..timeline.staleness import (
    is_timeline_stale,
    timeline_input_fingerprint,
)
from ..timeline.types import ReplacementStatus, TimelineItemStatus
from ..transcription.workflow import TranscriptionWorkflow
from ..stock.workflow import StockWorkflow

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Run all 9 pipeline stages in order with resume/force/cancel/persistence."""

    def __init__(
        self,
        *,
        transcription_workflow: TranscriptionWorkflow,
        stock_workflow: StockWorkflow,
        media_service: FFmpegMediaService,
        store: ProjectStore,
        project_path: Path,
        motion: MotionEffect = MotionEffect.NONE,
        timeline_composer: TimelineComposer | None = None,
    ) -> None:
        self.transcription_workflow = transcription_workflow
        self.stock_workflow = stock_workflow
        self.media_service = media_service
        self.store = store
        self.project_path = project_path
        self.motion = motion
        self.timeline_composer = timeline_composer or TimelineComposer(media_service)

    def run(
        self,
        state: ProjectState,
        *,
        force: bool = False,
        allow_missing: bool = False,
        cancel_event: threading.Event | None = None,
        progress: Callable[[float], None] | None = None,
    ) -> ProjectState:
        timeline_mode = has_timeline_content(state)
        output_dir = state.render_settings.output_dir
        cleanup_stale_render_temps(output_dir)

        if force:
            self._reset_all(state)
        elif timeline_mode:
            self._invalidate_stale_timeline(state)

        if progress is not None:
            progress(0.0)

        for index, stage in enumerate(STAGE_ORDER):
            self._check_cancel(cancel_event)
            stage_state = state.stage(stage)

            if timeline_mode and stage in TIMELINE_SKIP_STAGES:
                stage_state.status = StageStatus.SKIPPED
                stage_state.error = None
                stage_state.artifacts = []
                self._save(state)
                continue

            if stage_state.status in (StageStatus.COMPLETED, StageStatus.SKIPPED):
                if (
                    timeline_mode
                    and stage_state.status == StageStatus.COMPLETED
                    and not self._stage_artifacts_valid(state, stage)
                ):
                    stage_state.status = StageStatus.FAILED
                    stage_state.error = "Missing intermediate artifact."
                    state.last_error = stage_state.error
                    self._save(state)
                else:
                    continue

            stage_state.status = StageStatus.RUNNING
            stage_state.error = None

            try:
                self._dispatch(
                    stage,
                    state,
                    cancel_event,
                    timeline_mode=timeline_mode,
                    allow_missing=allow_missing,
                )
            except AutoTubeError as exc:
                stage_state.status = StageStatus.FAILED
                stage_state.error = str(exc)
                state.last_error = str(exc)
                self._save(state)
                logger.exception("Stage %s failed", stage.value)
                raise
            except Exception as exc:  # noqa: BLE001 - pipeline boundary
                stage_state.status = StageStatus.FAILED
                stage_state.error = f"Unexpected error: {exc}"
                state.last_error = stage_state.error
                self._save(state)
                logger.exception("Stage %s failed unexpectedly", stage.value)
                raise

            stage_state.status = StageStatus.COMPLETED
            stage_state.error = None
            self._save(state)

            if progress is not None:
                progress((index + 1) / len(STAGE_ORDER) * 100.0)

        if progress is not None:
            progress(100.0)
        return state

    def _dispatch(
        self,
        stage: PipelineStage,
        state: ProjectState,
        cancel_event: threading.Event | None,
        *,
        timeline_mode: bool,
        allow_missing: bool,
    ) -> None:
        if stage == PipelineStage.TRANSCRIBED:
            self.transcription_workflow.run(
                state, force=False, cancel_event=cancel_event
            )
        elif stage == PipelineStage.SEGMENTS_READY:
            return
        elif stage == PipelineStage.KEYWORDS_READY:
            self.stock_workflow.run(state, force=False, cancel_event=cancel_event)
        elif stage == PipelineStage.ASSETS_READY:
            return
        elif stage == PipelineStage.CLIPS_READY:
            if timeline_mode:
                self._run_timeline_clips(state, allow_missing, cancel_event)
            else:
                self._run_clips(state, cancel_event)
        elif stage == PipelineStage.COMPOSED:
            if timeline_mode:
                self._run_timeline_compose(state, cancel_event)
            else:
                self._run_compose(state, cancel_event)
        elif stage == PipelineStage.AUDIO_READY:
            self._run_audio(state, cancel_event)
        elif stage == PipelineStage.CAPTIONS_READY:
            if timeline_mode:
                self._run_timeline_captions(state, cancel_event)
            else:
                self._run_captions(state, cancel_event)
        elif stage == PipelineStage.COMPLETED:
            if timeline_mode:
                self._run_timeline_finalize(state, cancel_event)
            else:
                self._run_finalize(state, cancel_event)
        else:
            raise ValidationError(f"Unknown pipeline stage: {stage}")

    def _run_clips(
        self, state: ProjectState, cancel_event: threading.Event | None
    ) -> None:
        if state.project is None:
            raise ValidationError("Project must exist to process clips.")

        spec = video_spec_from_render_settings(state.render_settings)
        output_dir = state.render_settings.output_dir

        for segment in state.segments:
            self._check_cancel(cancel_event)
            clip = segment.selected_clip or {}
            local_path = clip.get("local_path")
            if not local_path:
                segment.status = SegmentStatus.FAILED
                segment.error = "Missing local_path in selected_clip."
                raise ValidationError(
                    f"Segment {segment.segment_id} has no local stock asset."
                )

            try:
                result = self.media_service.process_clip(
                    Path(local_path),
                    segment,
                    spec,
                    output_dir,
                    motion=self.motion,
                    cancel_event=cancel_event,
                )
            except AutoTubeError:
                segment.status = SegmentStatus.FAILED
                raise

            segment.selected_clip = dict(segment.selected_clip or {})
            segment.selected_clip["processed_path"] = str(result.path)
            segment.status = SegmentStatus.PROCESSED
            segment.error = None

        state.stage(PipelineStage.CLIPS_READY).artifacts = [
            Path(s.selected_clip["processed_path"])
            for s in state.segments
            if s.selected_clip and s.selected_clip.get("processed_path")
        ]

    def _run_timeline_clips(
        self,
        state: ProjectState,
        allow_missing: bool,
        cancel_event: threading.Event | None,
    ) -> None:
        timeline = state.timeline
        if timeline is None:
            raise ValidationError("No timeline to render.")

        spec = video_spec_from_render_settings(state.render_settings)
        output_dir = state.render_settings.output_dir

        processed = self.timeline_composer.process_visual_assets(
            state, timeline, spec, output_dir, cancel_event=cancel_event
        )
        validate_missing_slots(timeline, allow_missing=allow_missing)

        state.stage(PipelineStage.CLIPS_READY).artifacts = [
            Path(path) for path in processed
        ]

    def _run_compose(
        self, state: ProjectState, cancel_event: threading.Event | None
    ) -> None:
        paths = [
            Path(s.selected_clip["processed_path"])
            for s in state.segments
            if s.selected_clip and s.selected_clip.get("processed_path")
        ]
        if not paths:
            raise ValidationError("No processed clips available for composition.")

        spec = video_spec_from_render_settings(state.render_settings)
        output_dir = state.render_settings.output_dir
        list_file = output_dir / "clips.txt"
        output_dir.mkdir(parents=True, exist_ok=True)
        list_file.write_text(
            "".join(f"file '{p.resolve().as_posix()}'\n" for p in paths),
            encoding="utf-8",
        )

        destination = output_dir / "composed.mp4"
        self.media_service.compose_video_only(
            list_file, destination, spec, cancel_event=cancel_event
        )
        state.stage(PipelineStage.COMPOSED).artifacts = [destination]

    def _run_timeline_compose(
        self, state: ProjectState, cancel_event: threading.Event | None
    ) -> None:
        timeline = state.timeline
        if timeline is None:
            raise ValidationError("No timeline to render.")

        spec = video_spec_from_render_settings(state.render_settings)
        output_dir = state.render_settings.output_dir
        base = self.timeline_composer.build_base_track(
            state,
            timeline,
            spec,
            output_dir,
            progress=None,
            cancel_event=cancel_event,
        )
        state.stage(PipelineStage.COMPOSED).artifacts = [base]

    def _run_audio(
        self, state: ProjectState, cancel_event: threading.Event | None
    ) -> None:
        if state.project is None or state.project.voiceover_path is None:
            raise ValidationError("Project must have a voiceover path.")

        output_dir = state.render_settings.output_dir
        if has_timeline_content(state):
            destination = self.timeline_composer.compose_audio(
                state, output_dir, cancel_event=cancel_event
            )
        else:
            destination = output_dir / "final_audio.m4a"
            self.media_service.mix_audio(
                state.project.voiceover_path,
                destination,
                music=state.project.music_path,
                music_volume=state.render_settings.music_volume,
                cancel_event=cancel_event,
            )
        state.stage(PipelineStage.AUDIO_READY).artifacts = [destination]

    def _run_captions(
        self, state: ProjectState, cancel_event: threading.Event | None
    ) -> None:
        composed = state.stage(PipelineStage.COMPOSED).artifacts
        if not composed:
            raise ValidationError("Composed video not found for captions.")

        from ..media.captions import write_srt

        output_dir = state.render_settings.output_dir
        srt_path = output_dir / "captions.srt"
        write_srt(state.segments, srt_path)

        spec = video_spec_from_render_settings(state.render_settings)
        captioned = output_dir / "captioned.mp4"
        self.media_service.render_captions(
            composed[0],
            srt_path,
            captioned,
            spec,
            cancel_event=cancel_event,
        )
        state.stage(PipelineStage.CAPTIONS_READY).artifacts = [srt_path, captioned]

    def _run_timeline_captions(
        self, state: ProjectState, cancel_event: threading.Event | None
    ) -> None:
        composed = state.stage(PipelineStage.COMPOSED).artifacts
        if not composed:
            raise ValidationError("Composed video not found for captions.")

        timeline = state.timeline
        if timeline is None:
            raise ValidationError("No timeline to render.")

        spec = video_spec_from_render_settings(state.render_settings)
        output_dir = state.render_settings.output_dir
        burned = self.timeline_composer.generate_captions(
            state,
            timeline,
            spec,
            output_dir,
            composed[0],
            cancel_event,
        )

        artifacts = [burned]
        if timeline.subtitles:
            artifacts.insert(0, output_dir / "timeline.ass")
        state.stage(PipelineStage.CAPTIONS_READY).artifacts = artifacts

    def _run_finalize(
        self, state: ProjectState, cancel_event: threading.Event | None
    ) -> None:
        captioned_artifacts = state.stage(PipelineStage.CAPTIONS_READY).artifacts
        audio_artifacts = state.stage(PipelineStage.AUDIO_READY).artifacts
        if not captioned_artifacts or not audio_artifacts:
            raise ValidationError("Captioned video and final audio are required.")

        captioned = captioned_artifacts[-1]
        audio = audio_artifacts[-1]
        output_dir = state.render_settings.output_dir
        final = output_dir / "final.mp4"

        self.media_service.mux_video_audio(
            captioned, audio, final, cancel_event=cancel_event
        )
        self._validate_final(final, state)
        state.stage(PipelineStage.COMPLETED).artifacts = [final]

    def _run_timeline_finalize(
        self, state: ProjectState, cancel_event: threading.Event | None
    ) -> None:
        captioned_artifacts = state.stage(PipelineStage.CAPTIONS_READY).artifacts
        audio_artifacts = state.stage(PipelineStage.AUDIO_READY).artifacts
        if not captioned_artifacts or not audio_artifacts:
            raise ValidationError("Captioned video and final audio are required.")

        timeline = state.timeline
        if timeline is None:
            raise ValidationError("No timeline to render.")

        burned = captioned_artifacts[-1]
        audio = audio_artifacts[-1]
        output_dir = state.render_settings.output_dir
        final = output_dir / "final.mp4"

        self.media_service.mux_video_audio(
            burned, audio, final, cancel_event=cancel_event
        )
        self._validate_final(final, state)

        spec = video_spec_from_render_settings(state.render_settings)
        total_duration = self.timeline_composer.total_duration(state, timeline)
        self.timeline_composer.validate_final(final, spec, total_duration)

        timeline.rendered_path = str(final)
        timeline.rendered_fingerprint = timeline_input_fingerprint(state)
        timeline.rendered_at = datetime.now(timezone.utc)

        state.stage(PipelineStage.COMPLETED).artifacts = [final]

    def _validate_final(self, path: Path, state: ProjectState) -> None:
        info = self.media_service.probe_video(path)
        spec = video_spec_from_render_settings(state.render_settings)

        video = info.video_stream()
        if video is None:
            raise ValidationError("Final video has no video stream.")

        audio = info.audio_stream()
        if audio is None:
            raise ValidationError("Final video has no audio stream.")

        audio_streams = [s for s in info.streams if s.codec_type == "audio"]
        if len(audio_streams) != 1:
            raise ValidationError(
                f"Final video must have exactly one audio stream; got {len(audio_streams)}."
            )

        if video.width != spec.width or video.height != spec.height:
            raise ValidationError(
                f"Final video resolution {video.width}x{video.height} does not match "
                f"{spec.width}x{spec.height}."
            )

        if video.fps is not None and abs(video.fps - spec.fps) > 1.0:
            raise ValidationError(
                f"Final video fps {video.fps} does not match {spec.fps}."
            )

    def _stage_artifacts_valid(self, state: ProjectState, stage: PipelineStage) -> bool:
        timeline = state.timeline
        artifacts = state.stage(stage).artifacts

        if stage == PipelineStage.CLIPS_READY:
            if timeline is None:
                return bool(artifacts)
            for asset in timeline.visual_assets:
                if is_missing_slot(asset):
                    continue
                if asset.processed_path is None or not asset.processed_path.exists():
                    return False
            return True

        if stage == PipelineStage.COMPOSED:
            return bool(artifacts) and artifacts[0].exists()

        if stage == PipelineStage.AUDIO_READY:
            return bool(artifacts) and artifacts[-1].exists()

        if stage == PipelineStage.CAPTIONS_READY:
            return bool(artifacts) and all(path.exists() for path in artifacts)

        if stage == PipelineStage.COMPLETED:
            return bool(artifacts) and artifacts[-1].exists()

        return True

    def _invalidate_stale_timeline(self, state: ProjectState) -> None:
        if state.timeline is None:
            return
        if state.timeline.rendered_fingerprint is None:
            return
        if not is_timeline_stale(state):
            return
        invalidate_timeline_render_stages(state)

    def _reset_all(self, state: ProjectState) -> None:
        for stage in STAGE_ORDER:
            stage_state = state.stage(stage)
            stage_state.status = StageStatus.PENDING
            stage_state.error = None
            stage_state.artifacts = []

        for segment in state.segments:
            segment.keywords = []
            segment.selected_clip = None
            segment.error = None
            segment.status = SegmentStatus.PENDING
            segment.words = []

        state.segments = []
        state.transcription = None
        state.last_error = None

        if state.timeline is not None:
            state.timeline.rendered_path = None
            state.timeline.rendered_fingerprint = None
            state.timeline.rendered_at = None
            for asset in state.timeline.visual_assets:
                asset.status = TimelineItemStatus.PENDING
                asset.processed_path = None
                asset.error = None
                asset.replacement_status = ReplacementStatus.NONE

    def _save(self, state: ProjectState) -> None:
        self.store.save(state, self.project_path)

    @staticmethod
    def _check_cancel(cancel_event: threading.Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise AutoTubeError("Pipeline cancelled.")
