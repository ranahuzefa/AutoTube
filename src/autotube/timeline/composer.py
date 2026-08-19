"""Master timeline composition into a final MP4."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..exceptions import ValidationError
from ..media.constants import video_spec_from_render_settings
from ..media.service import FFmpegMediaService
from ..media.types import VideoSpec
from ..state import PipelineStage, ProjectState
from .animations import AnimationPresetRegistry, default_animation_registry
from .ass import ASSGenerator
from .media import TimelineMediaProcessor
from .missing import is_missing_slot, validate_missing_slots
from .overlap import find_overlaps
from .staleness import timeline_input_fingerprint
from .transitions import (
    applicable_boundaries,
    default_transition_effect_registry,
    select_effects,
    select_sounds,
    validate_transition_settings,
)
from .types import (
    ReplacementStatus,
    TimelineItemStatus,
    TimelineState,
    TransitionEffectMode,
    TransitionSoundMode,
)


class TimelineComposer:
    """Compose a ProjectState timeline into a final validated MP4."""

    def __init__(
        self,
        media_service: FFmpegMediaService,
        registry: AnimationPresetRegistry | None = None,
        transition_registry=None,
    ) -> None:
        self.media_service = media_service
        self.registry = registry or default_animation_registry()
        self.transition_registry = (
            transition_registry or default_transition_effect_registry()
        )
        self.processor = TimelineMediaProcessor(media_service)

    def compose(
        self,
        state: ProjectState,
        output_dir: Path,
        *,
        progress: Callable[[float], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Backward-compatible entry point.

        Kept for existing callers. Validation mode is used, so unresolved
        visual slots raise ``MissingVisualAssetsError``.
        """
        return self.compose_timeline_pipeline(
            state,
            output_dir,
            allow_missing=False,
            progress=progress,
            cancel_event=cancel_event,
        )

    def compose_timeline_pipeline(
        self,
        state: ProjectState,
        output_dir: Path,
        *,
        allow_missing: bool = False,
        progress: Callable[[float], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        timeline = self.validate_timeline_inputs(state)

        spec = video_spec_from_render_settings(state.render_settings)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if progress:
            progress(0.0)

        total_duration = self.total_duration(state, timeline)

        self.process_visual_assets(
            state, timeline, spec, output_dir, cancel_event=cancel_event
        )
        validate_missing_slots(timeline, allow_missing=allow_missing)

        base_video = self.build_base_track(
            state, timeline, spec, output_dir, progress, cancel_event
        )

        if progress:
            progress(50.0)

        audio = self.compose_audio(
            state, output_dir, progress=progress, cancel_event=cancel_event
        )

        if progress:
            progress(70.0)

        burned = self.generate_captions(
            state, timeline, spec, output_dir, base_video, cancel_event
        )

        if progress:
            progress(85.0)

        final = self.media_service.mux_video_audio(
            burned, audio, output_dir / "final.mp4", cancel_event=cancel_event
        )

        self.validate_final(final, spec, total_duration)

        timeline.rendered_path = str(final)
        timeline.rendered_fingerprint = timeline_input_fingerprint(state)
        timeline.rendered_at = datetime.now(timezone.utc)

        if progress:
            progress(100.0)

        return final

    def validate_timeline_inputs(self, state: ProjectState) -> TimelineState:
        if state.project is None:
            raise ValidationError("Project must exist to render timeline.")

        timeline = state.timeline
        if timeline is None:
            raise ValidationError("No timeline to render.")

        if state.project.voiceover_path is None:
            raise ValidationError("Project must have a voiceover path.")

        if find_overlaps(timeline.visual_assets):
            raise ValidationError("Overlapping visual assets must be resolved.")

        return timeline

    def total_duration(
        self, state: ProjectState, timeline: TimelineState
    ) -> float:
        durations = []
        try:
            audio_info = self.media_service.probe_audio(state.project.voiceover_path)
            if audio_info.duration:
                durations.append(audio_info.duration)
        except Exception:  # noqa: BLE001 - audio duration optional
            pass

        for asset in timeline.visual_assets:
            durations.append(asset.end)
        for subtitle in timeline.subtitles:
            durations.append(subtitle.end)

        if not durations:
            raise ValidationError("Timeline has no duration source.")

        return max(durations)

    def process_visual_assets(
        self,
        state: ProjectState,
        timeline: TimelineState,
        spec: VideoSpec,
        output_dir: Path,
        *,
        cancel_event: threading.Event | None = None,
    ) -> list[Path]:
        """Process renderable assets, converting failures into missing slots."""
        processed: list[Path] = []
        assets = sorted(timeline.visual_assets, key=lambda a: (a.start, a.end))

        for asset in assets:
            if cancel_event is not None and cancel_event.is_set():
                raise ValidationError("Timeline render cancelled.")

            if is_missing_slot(asset):
                continue

            try:
                result = self.processor.process(
                    asset, spec, output_dir, cancel_event=cancel_event
                )
            except Exception as exc:  # noqa: BLE001 - convert to missing slot
                asset.status = TimelineItemStatus.ERROR
                asset.error = str(exc)
                asset.processed_path = None
                asset.replacement_status = ReplacementStatus.REQUIRED
                continue

            asset.processed_path = Path(result)
            asset.status = TimelineItemStatus.READY
            asset.error = None
            processed.append(asset.processed_path)

        return processed

    def compose_audio(
        self,
        state: ProjectState,
        output_dir: Path,
        *,
        progress=None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Mix voiceover + BGM + optional transition SFX for the timeline."""
        if state.project is None or state.project.voiceover_path is None:
            raise ValidationError("Project must have a voiceover path.")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / "final_audio.m4a"
        settings = state.timeline.transition_settings

        boundaries = applicable_boundaries(state.timeline)
        sfx_path = None

        if (
            settings.effect_mode != TransitionEffectMode.NONE
            and settings.sound_mode != TransitionSoundMode.NONE
            and boundaries
        ):
            sounds = select_sounds(boundaries, settings, state.project_id)
            placements = [
                (sound, boundary.time)
                for sound, boundary in zip(sounds, boundaries)
                if sound is not None
            ]
            if placements:
                voiceover_info = self.media_service.probe_audio(
                    state.project.voiceover_path
                )
                voiceover_duration = voiceover_info.duration or self.total_duration(
                    state, state.timeline
                )
                sfx_path = self.media_service.build_transition_sfx(
                    placements,
                    output_dir / "transition_sfx.m4a",
                    duration=voiceover_duration,
                    transition_duration=settings.duration,
                    cancel_event=cancel_event,
                )

        mix_kwargs = {}
        if sfx_path is not None:
            mix_kwargs["sfx"] = sfx_path
            mix_kwargs["sfx_volume"] = settings.sound_volume

        return self.media_service.mix_audio(
            state.project.voiceover_path,
            destination,
            music=state.project.music_path,
            music_volume=state.render_settings.music_volume,
            cancel_event=cancel_event,
            **mix_kwargs,
        )

    def build_base_track(
        self,
        state: ProjectState,
        timeline: TimelineState,
        spec: VideoSpec,
        output_dir: Path,
        progress: Callable[[float], None] | None,
        cancel_event: threading.Event | None,
    ) -> Path:
        assets = sorted(timeline.visual_assets, key=lambda a: (a.start, a.end))

        if not assets:
            composed = state.stage(PipelineStage.COMPOSED).artifacts
            if composed:
                return composed[0]
            return self.media_service.black_segment(
                output_dir / "base.mp4",
                spec,
                self.total_duration(state, timeline),
                cancel_event=cancel_event,
            )

        clips: list[Path] = []
        cursor = 0.0
        total = self.total_duration(state, timeline)

        settings = timeline.transition_settings
        boundaries = applicable_boundaries(timeline)
        effect_names: list[str] = []
        transitions_enabled = settings.effect_mode != TransitionEffectMode.NONE
        if transitions_enabled and boundaries:
            validate_transition_settings(settings)
            effect_names = select_effects(
                boundaries, settings, state.project_id, self.transition_registry
            )

        runs: dict[int, tuple[list[TimedVisualAsset], Path]] = {}
        effect_index = 0
        non_missing = [a for a in assets if not is_missing_slot(a)]

        if transitions_enabled:
            for i, asset in enumerate(non_missing):
                if i == 0 or abs(non_missing[i - 1].end - asset.start) > 1e-6:
                    current_run = [asset]
                else:
                    current_run.append(asset)

                is_last = i == len(non_missing) - 1
                run_ends = (
                    is_last
                    or abs(asset.end - non_missing[i + 1].start) > 1e-6
                )

                if run_ends and len(current_run) >= 2:
                    run_durations = [a.end - a.start for a in current_run]
                    run_paths = []
                    for run_asset in current_run:
                        if run_asset.processed_path is None:
                            raise ValidationError(
                                f"Timeline asset {run_asset.source_path} has no processed clip."
                            )
                        run_paths.append(run_asset.processed_path)

                    run_file = self.media_service.compose_transition_run(
                        run_paths,
                        run_durations,
                        effect_names[effect_index : effect_index + len(current_run) - 1],
                        output_dir / f"transition_run_{effect_index}.mp4",
                        spec,
                        settings.duration,
                        cancel_event=cancel_event,
                    )
                    effect_index += len(current_run) - 1
                    runs[id(current_run[0])] = (current_run, run_file)

        skip_ids: set[int] = set()
        for asset in assets:
            if cancel_event is not None and cancel_event.is_set():
                raise ValidationError("Timeline render cancelled.")

            if id(asset) in skip_ids:
                continue

            if asset.start > cursor:
                gap = self.media_service.black_segment(
                    output_dir / f"gap_{int(cursor)}_{int(asset.start)}.mp4",
                    spec,
                    asset.start - cursor,
                    cancel_event=cancel_event,
                )
                clips.append(gap)

            run_entry = runs.get(id(asset))
            if run_entry is not None:
                run_assets, run_file = run_entry
                clips.append(run_file)
                for run_asset in run_assets[1:]:
                    skip_ids.add(id(run_asset))
                cursor = run_assets[-1].end
                continue

            if is_missing_slot(asset):
                black = self.media_service.black_segment(
                    output_dir / f"missing_{int(asset.start)}_{int(asset.end)}.mp4",
                    spec,
                    asset.end - asset.start,
                    cancel_event=cancel_event,
                )
                clips.append(black)
            else:
                if asset.processed_path is None:
                    raise ValidationError(
                        f"Timeline asset {asset.source_path} has no processed clip."
                    )
                clips.append(asset.processed_path)

            cursor = asset.end

        if cursor < total:
            tail = self.media_service.black_segment(
                output_dir / f"gap_{int(cursor)}_{int(total)}.mp4",
                spec,
                total - cursor,
                cancel_event=cancel_event,
            )
            clips.append(tail)

        list_file = output_dir / "clips.txt"
        list_file.write_text(
            "".join(f"file '{p.resolve().as_posix()}'\n" for p in clips),
            encoding="utf-8",
        )

        if progress:
            progress(25.0)

        return self.media_service.compose_video_only(
            list_file, output_dir / "base.mp4", spec, cancel_event=cancel_event
        )

    def generate_captions(
        self,
        state: ProjectState,
        timeline: TimelineState,
        spec: VideoSpec,
        output_dir: Path,
        base_video: Path,
        cancel_event: threading.Event | None,
    ) -> Path:
        if not timeline.subtitles:
            return base_video

        ass_path = output_dir / "timeline.ass"
        ass_path.write_text(
            ASSGenerator(self.registry).generate(
                timeline.subtitles, spec.width, spec.height
            ),
            encoding="utf-8",
        )
        return self.media_service.overlay_subtitles(
            base_video, ass_path, output_dir / "burned.mp4", spec,
            cancel_event=cancel_event,
        )

    def validate_final(
        self, path: Path, spec: VideoSpec, total_duration: float
    ) -> None:
        info = self.media_service.probe_media(path)
        if info.video_stream() is None:
            raise ValidationError("Final video has no video stream.")
        audio_streams = [s for s in info.streams if s.codec_type == "audio"]
        if len(audio_streams) != 1:
            raise ValidationError(
                f"Final video must have exactly one audio stream; got {len(audio_streams)}."
            )

        video = info.video_stream()
        if video.width != spec.width or video.height != spec.height:
            raise ValidationError(
                f"Final resolution {video.width}x{video.height} does not match "
                f"{spec.width}x{spec.height}."
            )
        if video.fps is not None and abs(video.fps - spec.fps) > 1.0:
            raise ValidationError(
                f"Final fps {video.fps} does not match {spec.fps}."
            )
        if info.duration is not None and abs(info.duration - total_duration) > 1.0:
            raise ValidationError(
                f"Final duration {info.duration} does not match {total_duration}."
            )
