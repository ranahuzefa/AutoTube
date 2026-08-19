"""Pure FFmpeg/FFprobe command builders.

Each function returns a list of string tokens (no leading executable). Callers
prepend the configured ``ffmpeg``/``ffprobe`` binary and pass the result to
:class:`FFmpegRunner`. Every argument is a separate list item; ``shell=False`` is
used at execution time.
"""

from __future__ import annotations

from pathlib import Path

from ..constants import DEFAULT_TRANSITION_SOUND_VOLUME
from .constants import DEFAULT_MUSIC_VOLUME
from .paths import escape_filter_path, quote_filter_arg
from .types import AudioSpec, FitPolicy, MotionEffect, VideoSpec


def _fmt_seconds(value: float) -> str:
    return f"{value:.3f}"


def _video_encode_args(spec: VideoSpec) -> list[str]:
    return [
        "-c:v",
        spec.codec,
        "-preset",
        spec.preset,
        "-crf",
        spec.crf,
        "-pix_fmt",
        spec.pix_fmt,
    ]


def _audio_encode_args(spec: AudioSpec) -> list[str]:
    return [
        "-c:a",
        spec.codec,
        "-b:a",
        spec.bitrate,
        "-ar",
        str(spec.sample_rate),
        "-ac",
        str(spec.channels),
    ]


def _progress_args() -> list[str]:
    return ["-progress", "pipe:1", "-nostats", "-loglevel", "error"]


def build_probe_cmd(path: Path | str) -> list[str]:
    """FFprobe options (caller prepends ``ffprobe``)."""
    return [
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]


def build_scale_crop_pad_filter(
    width: int,
    height: int,
    fit: FitPolicy = FitPolicy.CONTAIN,
    pad_color: str = "black",
) -> str:
    """Return a scale+crop/pad filter that never distorts aspect ratio."""
    if fit == FitPolicy.COVER:
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={pad_color}"
    )


def _normalize_filter(spec: VideoSpec) -> str:
    base = build_scale_crop_pad_filter(spec.width, spec.height, spec.fit, spec.pad_color)
    return f"{base},fps={spec.fps},format={spec.pix_fmt}"


def build_normalize_video_cmd(src: Path | str, dst: Path | str, spec: VideoSpec) -> list[str]:
    """Normalize video to spec. Video-only by default (``-an``)."""
    args = ["-y", "-i", str(src)]
    if not spec.include_audio:
        args.append("-an")
    args += ["-vf", _normalize_filter(spec)]
    args += _video_encode_args(spec)
    if spec.include_audio:
        args += _audio_encode_args(AudioSpec())
    args += _progress_args()
    args.append(str(dst))
    return args


def build_trim_video_cmd(
    src: Path | str,
    dst: Path | str,
    spec: VideoSpec,
    start: float,
    end: float,
) -> list[str]:
    """Frame-accurate trim, always re-encoded, video-only."""
    duration = end - start
    args = ["-y", "-ss", _fmt_seconds(start), "-i", str(src), "-t", _fmt_seconds(duration)]
    if not spec.include_audio:
        args.append("-an")
    args += ["-vf", _normalize_filter(spec)]
    args += _video_encode_args(spec)
    if spec.include_audio:
        args += _audio_encode_args(AudioSpec())
    args += _progress_args()
    args.append(str(dst))
    return args


def build_loop_video_cmd(
    src: Path | str,
    dst: Path | str,
    spec: VideoSpec,
    duration: float,
) -> list[str]:
    """Loop a short source to an exact duration, video-only."""
    args = ["-y", "-stream_loop", "-1", "-i", str(src), "-t", _fmt_seconds(duration)]
    if not spec.include_audio:
        args.append("-an")
    args += ["-vf", _normalize_filter(spec)]
    args += _video_encode_args(spec)
    if spec.include_audio:
        args += _audio_encode_args(AudioSpec())
    args += _progress_args()
    args.append(str(dst))
    return args


def build_normalize_audio_cmd(src: Path | str, dst: Path | str, spec: AudioSpec) -> list[str]:
    """Normalize audio to a deterministic AAC profile (voiceover/BGM)."""
    return (
        ["-y", "-i", str(src), "-vn"]
        + _audio_encode_args(spec)
        + _progress_args()
        + [str(dst)]
    )


def build_trim_audio_cmd(
    src: Path | str,
    dst: Path | str,
    spec: AudioSpec,
    start: float,
    end: float,
) -> list[str]:
    """Trim audio to an exact duration and normalize it."""
    duration = end - start
    return (
        ["-y", "-ss", _fmt_seconds(start), "-i", str(src), "-t", _fmt_seconds(duration), "-vn"]
        + _audio_encode_args(spec)
        + _progress_args()
        + [str(dst)]
    )


def build_mix_audio_cmd(
    voiceover: Path | str,
    music: Path | str | None,
    dst: Path | str,
    spec: AudioSpec,
    music_volume: float = DEFAULT_MUSIC_VOLUME,
    *,
    sfx: Path | str | None = None,
    sfx_volume: float = DEFAULT_TRANSITION_SOUND_VOLUME,
) -> list[str]:
    """Mix voiceover + optional BGM + optional transition SFX.

    Voiceover is kept at full volume and BGM is scaled to ``music_volume``.
    When ``sfx`` is None the command is byte-for-byte identical to the previous
    no-SFX behavior. SFX is added in a second ``normalize=0`` amix stage so it
    can never re-scale or shift the existing voiceover/BGM mix.
    """
    if sfx is None:
        if music is None:
            return build_normalize_audio_cmd(voiceover, dst, spec)

        filter_complex = (
            "[0:a]volume=1.0[vo];"
            f"[1:a]volume={music_volume:g}[bg];"
            "[vo][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        return (
            ["-y", "-i", str(voiceover), "-i", str(music)]
            + ["-filter_complex", filter_complex]
            + ["-map", "[aout]"]
            + _audio_encode_args(spec)
            + _progress_args()
            + [str(dst)]
        )

    if music is None:
        filter_complex = (
            "[0:a]volume=1.0[vo];"
            f"[1:a]volume={sfx_volume:g}[fx];"
            "[vo][fx]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        return (
            ["-y", "-i", str(voiceover), "-i", str(sfx)]
            + ["-filter_complex", filter_complex]
            + ["-map", "[aout]"]
            + _audio_encode_args(spec)
            + _progress_args()
            + [str(dst)]
        )

    filter_complex = (
        "[0:a]volume=1.0[vo];"
        f"[1:a]volume={music_volume:g}[bg];"
        "[vo][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=1[vobg];"
        f"[2:a]volume={sfx_volume:g}[fx];"
        "[vobg][fx]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
    )
    return (
        ["-y", "-i", str(voiceover), "-i", str(music), "-i", str(sfx)]
        + ["-filter_complex", filter_complex]
        + ["-map", "[aout]"]
        + _audio_encode_args(spec)
        + _progress_args()
        + [str(dst)]
    )


def build_burn_captions_cmd(
    video: Path | str,
    srt: Path | str,
    dst: Path | str,
    spec: VideoSpec,
) -> list[str]:
    """Burn SRT captions into a video. Video-only by default."""
    subtitles_arg = f"subtitles={quote_filter_arg(escape_filter_path(srt))}"
    vf = f"{subtitles_arg},{_normalize_filter(spec)}"
    args = ["-y", "-i", str(video)]
    if not spec.include_audio:
        args.append("-an")
    args += ["-vf", vf]
    args += _video_encode_args(spec)
    if spec.include_audio:
        args += _audio_encode_args(AudioSpec())
    args += _progress_args()
    args.append(str(dst))
    return args


def build_compose_cmd(
    clip_list_file: Path | str,
    audio: Path | str,
    dst: Path | str,
    spec: VideoSpec,
    audio_spec: AudioSpec | None = None,
) -> list[str]:
    """Compose video-only clips + a separately mixed audio track.

    Only ``0:v`` from the concatenated clips and ``1:a`` from the final audio are
    mapped, so stock audio can never leak into the result.
    """
    audio_spec = audio_spec or AudioSpec()
    return (
        ["-y", "-f", "concat", "-safe", "0", "-i", str(clip_list_file)]
        + ["-i", str(audio)]
        + ["-map", "0:v:0", "-map", "1:a:0"]
        + _video_encode_args(spec)
        + _audio_encode_args(audio_spec)
        + ["-shortest"]
        + _progress_args()
        + [str(dst)]
    )


def build_image_duration_cmd(
    src: Path | str,
    dst: Path | str,
    spec: VideoSpec,
    duration: float,
) -> list[str]:
    """Render a still image into a video-only clip of exact duration."""
    args = [
        "-y",
        "-loop",
        "1",
        "-i",
        str(src),
        "-t",
        _fmt_seconds(duration),
        "-an",
        "-vf",
        _normalize_filter(spec),
    ]
    args += _video_encode_args(spec)
    args += _progress_args()
    args.append(str(dst))
    return args


def build_compose_video_only_cmd(
    clip_list_file: Path | str,
    dst: Path | str,
    spec: VideoSpec,
) -> list[str]:
    """Compose video-only clips (no audio stream)."""
    return (
        ["-y", "-f", "concat", "-safe", "0", "-i", str(clip_list_file)]
        + ["-map", "0:v:0"]
        + _video_encode_args(spec)
        + ["-an"]
        + _progress_args()
        + [str(dst)]
    )


def build_mux_video_audio_cmd(
    video: Path | str,
    audio: Path | str,
    dst: Path | str,
) -> list[str]:
    """Mux a video-only track with the final mixed audio.

    Both inputs are already encoded to spec, so stream copy is safe.
    """
    return (
        ["-y", "-i", str(video), "-i", str(audio)]
        + ["-map", "0:v:0", "-map", "1:a:0"]
        + ["-c:v", "copy", "-c:a", "copy"]
        + _progress_args()
        + [str(dst)]
    )


def build_transition_run_cmd(
    inputs: list[Path | str],
    durations: list[float],
    transition_names: list[str],
    duration: float,
    dst: Path | str,
    spec: VideoSpec,
) -> list[str]:
    """Build a video-only overlapping crossfade run.

    Every clip after the first is extended by ``duration`` seconds using
    ``tpad=start_mode=clone``, and each internal boundary is blended with an
    ``xfade`` filter. The exact-duration math keeps the run output length equal
    to ``sum(durations)`` while aligning the blend window to the nominal boundary.
    """
    if len(inputs) < 2:
        raise ValueError("A transition run needs at least two inputs.")
    if len(durations) != len(inputs):
        raise ValueError("durations must match inputs.")
    if len(transition_names) != len(inputs) - 1:
        raise ValueError("transition_names must have len(inputs) - 1 entries.")

    filter_parts: list[str] = ["[0:v]null[v0]"]
    previous_label = "v0"

    for index in range(1, len(inputs)):
        filter_parts.append(
            f"[{index}:v]tpad=start_mode=clone:start_duration={_fmt_seconds(duration)}[v{index}]"
        )
        offset = sum(durations[:index]) - duration
        transition = transition_names[index - 1]
        out_label = "vout" if index == len(inputs) - 1 else f"v{index}_out"

        filter_parts.append(
            f"[{previous_label}][v{index}]xfade=transition={transition}:"
            f"duration={_fmt_seconds(duration)}:offset={_fmt_seconds(offset)}[{out_label}]"
        )
        previous_label = out_label

    filter_complex = ";".join(filter_parts)
    return (
        ["-y"]
        + [arg for path in inputs for arg in ("-i", str(path))]
        + ["-filter_complex", filter_complex]
        + ["-map", f"[{previous_label}]"]
        + _video_encode_args(spec)
        + ["-an"]
        + _progress_args()
        + [str(dst)]
    )


def build_transition_sfx_cmd(
    placements: list[tuple[Path | str, float]],
    duration: float,
    dst: Path | str,
    spec: AudioSpec,
    *,
    transition_duration: float,
) -> list[str]:
    """Build a transition-SFX placement track.

    Each placement is delayed to its boundary start (minus the transition
    duration) and trimmed to the transition duration. All placements are mixed
    with ``normalize=0`` and the output is trimmed to ``duration``.
    """
    if not placements:
        raise ValueError("At least one SFX placement is required.")

    inputs: list[str] = []
    filter_parts: list[str] = []
    labels: list[str] = []

    for index, (path, start_seconds) in enumerate(placements):
        inputs.extend(["-i", str(path)])
        delay_ms = int(round(max(0.0, start_seconds - transition_duration) * 1000))
        label = f"sfx{index}"
        filter_parts.append(
            f"[{index}:a]aresample=48000,"
            "aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"adelay={delay_ms}|{delay_ms},"
            f"atrim=duration={_fmt_seconds(transition_duration)}[{label}]"
        )
        labels.append(label)

    mix_inputs = "".join(f"[{label}]" for label in labels)
    filter_parts.append(
        f"{mix_inputs}amix=inputs={len(labels)}:duration=longest:"
        "dropout_transition=0:normalize=0,apad[aout]"
    )
    filter_complex = ";".join(filter_parts)

    return (
        ["-y"]
        + inputs
        + ["-filter_complex", filter_complex]
        + ["-map", "[aout]"]
        + ["-t", _fmt_seconds(duration)]
        + _audio_encode_args(spec)
        + _progress_args()
        + [str(dst)]
    )


def build_black_segment_cmd(
    dst: Path | str,
    spec: VideoSpec,
    duration: float,
) -> list[str]:
    """Generate a video-only black clip of exact duration."""
    return (
        ["-y", "-f", "lavfi", "-i", f"color=c=black:s={spec.width}x{spec.height}"]
        + ["-t", _fmt_seconds(duration)]
        + ["-an"]
        + _video_encode_args(spec)
        + _progress_args()
        + [str(dst)]
    )


def build_overlay_subtitles_cmd(
    video: Path | str,
    ass: Path | str,
    dst: Path | str,
    spec: VideoSpec,
) -> list[str]:
    """Burn an ASS subtitle file into a video-only track."""
    subtitles_arg = f"subtitles={quote_filter_arg(escape_filter_path(ass))}"
    args = ["-y", "-i", str(video)]
    if not spec.include_audio:
        args.append("-an")
    args += ["-vf", subtitles_arg]
    args += _video_encode_args(spec)
    args += _progress_args()
    args.append(str(dst))
    return args


def build_motion_filter(
    effect: MotionEffect,
    fps: int,
    duration: float,
    width: int,
    height: int,
) -> str:
    """Return a zoompan filter preserving FPS and exact frame count/duration.

    ``d=1`` keeps one output frame per input frame; input clips are already
    normalized to the target FPS and exact duration, so frame count (and thus
    duration) is preserved. ``s`` is explicit to avoid FFmpeg default sizing.
    """
    if effect == MotionEffect.ZOOM_IN:
        zoom_expr = "min(zoom+0.0015,1.5)"
    elif effect == MotionEffect.ZOOM_OUT:
        zoom_expr = "if(lte(on,1),1.5,max(1.0,zoom-0.0015))"
    else:
        return ""

    return (
        f"zoompan=z='{zoom_expr}':d=1:"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={width}x{height}:fps={fps}"
    )
