"""ASS subtitle generation with animation preset mapping."""

from __future__ import annotations

from ..exceptions import ValidationError
from .animations import AnimationPresetRegistry
from .types import SubtitleEntry


def _ass_time(seconds: float) -> str:
    """Convert seconds to ASS time ``H:MM:SS.cc``."""
    cs = int(round(seconds * 100))
    hours, cs = divmod(cs, 360000)
    minutes, cs = divmod(cs, 6000)
    secs, cs = divmod(cs, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _event(start: float, end: float, text: str, tags: str = "") -> str:
    return (
        f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},"
        f"Default,,0,0,0,,{tags}{text}"
    )


class ASSGenerator:
    """Generate ASS v4+ subtitles for the timeline."""

    def __init__(self, registry: AnimationPresetRegistry) -> None:
        self.registry = registry

    def generate(
        self, subtitles: list[SubtitleEntry], width: int, height: int
    ) -> str:
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,"
            "&H00000000,0,0,0,0,100,100,0,0,1,2,1,2,20,20,20,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
            "Effect, Text",
        ]

        for subtitle in subtitles:
            preset_id = subtitle.animation_preset
            if preset_id:
                preset = self.registry.get(preset_id)
                lines.extend(self._events_for(subtitle, preset))
            else:
                lines.append(_event(subtitle.start, subtitle.end, subtitle.text))

        return "\n".join(lines) + "\n"

    def _events_for(self, subtitle: SubtitleEntry, preset) -> list[str]:
        duration = subtitle.end - subtitle.start
        if duration <= 0:
            raise ValidationError(
                f"Subtitle {subtitle.index} has non-positive duration."
            )

        strategy = _PRESET_STRATEGIES.get(preset.preset_id)
        if strategy is None:
            return [_event(subtitle.start, subtitle.end, subtitle.text)]

        return strategy(subtitle, duration)

    def _split_words(self, subtitle: SubtitleEntry) -> list[str]:
        return [w for w in subtitle.text.split() if w]

    def _split_chars(self, subtitle: SubtitleEntry) -> list[str]:
        return [c for c in subtitle.text if not c.isspace()]


def _fade_in(subtitle: SubtitleEntry, duration: float) -> list[str]:
    return [_event(subtitle.start, subtitle.end, subtitle.text, r"{\fad(500,0)}")]


def _fade_out(subtitle: SubtitleEntry, duration: float) -> list[str]:
    return [_event(subtitle.start, subtitle.end, subtitle.text, r"{\fad(0,500)}")]


def _fade_in_out(subtitle: SubtitleEntry, duration: float) -> list[str]:
    return [_event(subtitle.start, subtitle.end, subtitle.text, r"{\fad(300,300)}")]


def _slide_up(subtitle: SubtitleEntry, duration: float) -> list[str]:
    return [
        _event(
            subtitle.start,
            subtitle.end,
            subtitle.text,
            r"{\move(20,80,20,20)}",
        )
    ]


def _slide_down(subtitle: SubtitleEntry, duration: float) -> list[str]:
    return [
        _event(
            subtitle.start,
            subtitle.end,
            subtitle.text,
            r"{\move(20,20,20,80)}",
        )
    ]


def _scale_in(subtitle: SubtitleEntry, duration: float) -> list[str]:
    return [
        _event(
            subtitle.start,
            subtitle.end,
            subtitle.text,
            r"{\t(0,500,\fscx0\fscy0)}",
        )
    ]


def _word_pop(subtitle: SubtitleEntry, duration: float) -> list[str]:
    words = subtitle.text.split()
    if not words:
        return [_event(subtitle.start, subtitle.end, subtitle.text)]
    step = duration / len(words)
    return [
        _event(subtitle.start + i * step, subtitle.start + (i + 1) * step, w, r"{\fad(100,0)}")
        for i, w in enumerate(words)
    ]


def _typewriter(subtitle: SubtitleEntry, duration: float) -> list[str]:
    chars = [c for c in subtitle.text]
    if not chars:
        return [_event(subtitle.start, subtitle.end, subtitle.text)]
    step = duration / len(chars)
    return [
        _event(subtitle.start + i * step, subtitle.start + (i + 1) * step, c, r"{\fad(50,0)}")
        for i, c in enumerate(chars)
    ]


def _word_by_word(subtitle: SubtitleEntry, duration: float) -> list[str]:
    words = subtitle.text.split()
    if not words:
        return [_event(subtitle.start, subtitle.end, subtitle.text)]
    step = duration / len(words)
    return [
        _event(subtitle.start + i * step, subtitle.start + (i + 1) * step, w)
        for i, w in enumerate(words)
    ]


def _character_by_character(subtitle: SubtitleEntry, duration: float) -> list[str]:
    chars = [c for c in subtitle.text if not c.isspace()]
    if not chars:
        return [_event(subtitle.start, subtitle.end, subtitle.text)]
    step = duration / len(chars)
    return [
        _event(subtitle.start + i * step, subtitle.start + (i + 1) * step, c)
        for i, c in enumerate(chars)
    ]


def _highlight(subtitle: SubtitleEntry, duration: float) -> list[str]:
    return [
        _event(
            subtitle.start,
            subtitle.end,
            subtitle.text,
            r"{\t(0," + str(int(duration * 1000)) + r",\c&H00FFFF&)}",
        )
    ]


# blur_to_sharp intentionally has no animation strategy (standard libass cannot
# transition blur); it falls back to a static subtitle event.
_PRESET_STRATEGIES = {
    "fade_in": _fade_in,
    "fade_out": _fade_out,
    "fade_in_out": _fade_in_out,
    "slide_up": _slide_up,
    "slide_down": _slide_down,
    "scale_in": _scale_in,
    "word_pop": _word_pop,
    "typewriter": _typewriter,
    "word_by_word": _word_by_word,
    "character_by_character": _character_by_character,
    "highlight": _highlight,
}
