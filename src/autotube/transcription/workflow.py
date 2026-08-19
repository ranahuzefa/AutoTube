"""Transcription + segmentation workflow with resume semantics."""

from __future__ import annotations

import threading
from pathlib import Path

from ..state import (
    PipelineStage,
    ProjectState,
    StageStatus,
    TranscriptionInfo,
)
from ..storage import ProjectStore
from .config import TranscriptionConfig
from .segments import SegmentBuilder
from .service import (
    FasterWhisperTranscriptionService,
    TranscriptionProgressCallback,
)


class TranscriptionWorkflow:
    """Run TRANSCRIBED and SEGMENTS_READY against a ProjectState."""

    def __init__(
        self,
        service: FasterWhisperTranscriptionService | None = None,
        store: ProjectStore | None = None,
        project_path: Path | None = None,
    ) -> None:
        self.service = service or FasterWhisperTranscriptionService()
        self.store = store or ProjectStore()
        self.project_path = project_path

    def run(
        self,
        state: ProjectState,
        *,
        force: bool = False,
        progress: TranscriptionProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ProjectState:
        if state.project is None or state.project.voiceover_path is None:
            from ..exceptions import ValidationError

            raise ValidationError("Project must have a voiceover path.")

        voiceover = state.project.voiceover_path
        config = TranscriptionConfig.from_render_settings(state.render_settings)

        transcribed = state.stage(PipelineStage.TRANSCRIBED)
        segments_ready = state.stage(PipelineStage.SEGMENTS_READY)

        if force:
            transcribed.status = StageStatus.PENDING
            transcribed.error = None
            segments_ready.status = StageStatus.PENDING
            segments_ready.error = None
            state.segments = []
            state.transcription = None

        need_transcribe = transcribed.status in (StageStatus.PENDING, StageStatus.FAILED)
        need_segments = (
            segments_ready.status in (StageStatus.PENDING, StageStatus.FAILED)
            or not state.segments
        )

        if need_transcribe:
            result = self.service.transcribe_with_config(
                voiceover,
                config,
                progress=progress,
                cancel_event=cancel_event,
            )
            state.transcription = TranscriptionInfo(
                language=result.language,
                language_probability=result.language_probability,
                duration=result.duration,
                model=result.model,
                device=result.device,
                compute_type=result.compute_type,
            )
            state.segments = result.segments
            transcribed.status = StageStatus.COMPLETED
            transcribed.error = None
            transcribed.artifacts = [voiceover]
            self._save(state)

        if need_segments:
            builder = SegmentBuilder()
            state.segments = builder.build(
                state.segments, config, self._audio_duration(state)
            )
            segments_ready.status = StageStatus.COMPLETED
            segments_ready.error = None
            segments_ready.artifacts = [voiceover]
            self._save(state)

        return state

    def _audio_duration(self, state: ProjectState) -> float:
        if state.transcription and state.transcription.duration:
            return state.transcription.duration
        if state.segments:
            return state.segments[-1].end
        try:
            from ..media.service import FFmpegMediaService

            voiceover = state.project.voiceover_path if state.project else None
            if voiceover:
                info = FFmpegMediaService().probe_audio(voiceover)
                return info.duration or 0.0
        except Exception:  # noqa: BLE001
            pass
        return 0.0

    def _save(self, state: ProjectState) -> None:
        if self.project_path is None:
            return
        self.store.save(state, self.project_path)
