"""FFprobe integration: run ffprobe and parse JSON into typed metadata."""

from __future__ import annotations

import json
from pathlib import Path

from ..exceptions import MediaError, MediaCommandError
from .commands import build_probe_cmd
from .ffmpeg_runner import FFmpegRunner
from .types import MediaInfo, StreamInfo


class FFprobe:
    """Probe media files and return typed :class:`MediaInfo`."""

    def __init__(self, runner: FFmpegRunner | None = None) -> None:
        self.runner = runner or FFmpegRunner()

    def probe(self, path: Path | str) -> MediaInfo:
        path = Path(path)
        if not path.exists():
            raise MediaError(f"Input file does not exist: {path}")

        args = [self.runner.ffprobe_bin] + build_probe_cmd(path)
        try:
            result = self.runner.run(args)
        except MediaCommandError as exc:
            raise MediaError(f"ffprobe failed for {path}: {exc}") from exc

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise MediaError(f"Invalid ffprobe JSON for {path}: {exc}") from exc

        return _parse_probe(data, path)


def _parse_probe(data: dict, path: Path) -> MediaInfo:
    fmt = data.get("format", {}) or {}
    streams = [_parse_stream(s, idx) for idx, s in enumerate(data.get("streams", []))]
    return MediaInfo(
        path=path,
        format_name=fmt.get("format_name"),
        duration=_optional_float(fmt.get("duration")),
        bit_rate=_optional_int(fmt.get("bit_rate")),
        streams=streams,
    )


def _parse_stream(data: dict, index: int) -> StreamInfo:
    fps = None
    avg = data.get("avg_frame_rate") or data.get("r_frame_rate")
    if avg and "/" in avg:
        try:
            num, den = avg.split("/")
            if float(den) != 0:
                fps = float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            fps = None
    elif avg:
        fps = _optional_float(avg)

    return StreamInfo(
        index=index,
        codec_type=data.get("codec_type", ""),
        codec_name=data.get("codec_name"),
        width=_optional_int(data.get("width")),
        height=_optional_int(data.get("height")),
        fps=fps,
        pix_fmt=data.get("pix_fmt"),
        sample_rate=_optional_int(data.get("sample_rate")),
        channels=_optional_int(data.get("channels")),
        duration=_optional_float(data.get("duration")),
    )


def _optional_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
