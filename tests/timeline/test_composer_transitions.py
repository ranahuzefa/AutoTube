"""Tests for TimelineComposer transition integration with fakes."""

from __future__ import annotations

from pathlib import Path

from autotube.models import Project, RenderSettings
from autotube.state import ProjectState
from autotube.timeline.composer import TimelineComposer
from autotube.timeline.staleness import timeline_input_fingerprint
from autotube.timeline.types import (
    AssetType,
    TimelineState,
    TimedVisualAsset,
    TransitionEffectMode,
    TransitionSettings,
    TransitionSoundMode,
)


class _FakeMedia:
    def __init__(self, tmp_path: Path):
        self.tmp_path = tmp_path
        self.calls = []
        self.probe_duration = 4.0

    def probe_audio(self, path):
        from types import SimpleNamespace

        return SimpleNamespace(duration=self.probe_duration)

    def probe_media(self, path):
        from types import SimpleNamespace

        return SimpleNamespace(
            streams=[
                SimpleNamespace(codec_type="video", width=640, height=360, fps=30.0),
                SimpleNamespace(codec_type="audio"),
            ],
            video_stream=lambda: SimpleNamespace(width=640, height=360, fps=30.0),
            duration=self.probe_duration,
        )

    def mix_audio(self, *a, **k):
        self.calls.append(("mix_audio", k))
        return Path("final_audio.m4a")

    def overlay_subtitles(self, *a, **k):
        return Path("burned.mp4")

    def mux_video_audio(self, *a, **k):
        return Path("final.mp4")

    def black_segment(self, destination, spec, duration, *, cancel_event=None):
        self.calls.append(("black_segment", duration))
        return Path(destination)

    def compose_video_only(self, *a, **k):
        self.calls.append(("compose_video_only",))
        return Path("base.mp4")

    def compose_transition_run(self, inputs, durations, names, destination, spec, duration, **k):
        self.calls.append(("compose_transition_run", durations, names))
        return Path(destination)

    def build_transition_sfx(self, placements, destination, *, duration, transition_duration, **k):
        self.calls.append(("build_transition_sfx", placements))
        return Path(destination)


class _FakeProcessor:
    def process(self, asset, spec, output_dir, *, cancel_event=None):
        asset.processed_path = Path(f"processed_{asset.start}.mp4")
        return asset.processed_path


def _state(tmp_path: Path) -> ProjectState:
    state = ProjectState(
        project=Project(name="T", voiceover_path=tmp_path / "voice.mp3"),
        render_settings=RenderSettings(resolution="640x360", fps=30),
    )
    state.timeline = TimelineState()
    return state


def _composer(media: _FakeMedia) -> TimelineComposer:
    composer = TimelineComposer(media)
    composer.processor = _FakeProcessor()
    return composer


def test_no_transitions_uses_existing_concat(tmp_path: Path) -> None:
    media = _FakeMedia(tmp_path)
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(Path("a.mp4"), 0.0, 2.0, AssetType.VIDEO),
        TimedVisualAsset(Path("b.mp4"), 2.0, 4.0, AssetType.VIDEO),
    ]

    result = _composer(media).compose_timeline_pipeline(state, tmp_path / "out")

    assert result == Path("final.mp4")
    assert "compose_transition_run" not in [c[0] for c in media.calls]
    assert ("compose_video_only",) in media.calls


def test_transition_run_replaces_adjacent_assets(tmp_path: Path) -> None:
    media = _FakeMedia(tmp_path)
    media.probe_duration = 7.0
    state = _state(tmp_path)
    state.timeline.transition_settings = TransitionSettings(
        effect_mode=TransitionEffectMode.MANUAL, effect="fade", duration=0.5
    )
    state.timeline.visual_assets = [
        TimedVisualAsset(Path("a.mp4"), 0.0, 2.0, AssetType.VIDEO),
        TimedVisualAsset(Path("b.mp4"), 2.0, 4.0, AssetType.VIDEO),
        TimedVisualAsset(Path("c.mp4"), 5.0, 7.0, AssetType.VIDEO),
    ]

    _composer(media).compose_timeline_pipeline(state, tmp_path / "out")

    transition_calls = [c for c in media.calls if c[0] == "compose_transition_run"]
    assert len(transition_calls) == 1
    # Adjacent run of a and b; c is separated by a gap.
    assert transition_calls[0][1] == [2.0, 2.0]


def test_compose_audio_omits_sfx_when_disabled(tmp_path: Path) -> None:
    media = _FakeMedia(tmp_path)
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(Path("a.mp4"), 0.0, 2.0, AssetType.VIDEO),
        TimedVisualAsset(Path("b.mp4"), 2.0, 4.0, AssetType.VIDEO),
    ]

    result = _composer(media).compose_audio(state, tmp_path / "out")

    assert result == Path("final_audio.m4a")
    assert not any(c[0] == "build_transition_sfx" for c in media.calls)
    assert any(c[0] == "mix_audio" and "sfx" not in c[1] for c in media.calls)


def test_compose_audio_passes_sfx_and_volume(tmp_path: Path) -> None:
    media = _FakeMedia(tmp_path)
    state = _state(tmp_path)
    state.timeline.transition_settings = TransitionSettings(
        effect_mode=TransitionEffectMode.MANUAL,
        effect="fade",
        duration=0.5,
        sound_folder=tmp_path / "sfx",
        sound_mode=TransitionSoundMode.RANDOM,
        sound_volume=0.5,
    )
    (tmp_path / "sfx").mkdir()
    (tmp_path / "sfx" / "tone.wav").write_bytes(b"x")
    state.timeline.visual_assets = [
        TimedVisualAsset(Path("a.mp4"), 0.0, 2.0, AssetType.VIDEO),
        TimedVisualAsset(Path("b.mp4"), 2.0, 4.0, AssetType.VIDEO),
    ]

    _composer(media).compose_audio(state, tmp_path / "out")

    assert any(c[0] == "build_transition_sfx" for c in media.calls)
    mix_calls = [c for c in media.calls if c[0] == "mix_audio"]
    assert mix_calls
    assert mix_calls[-1][1].get("sfx") is not None
    assert mix_calls[-1][1].get("sfx_volume") == 0.5


def test_transition_settings_change_fingerprint(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.timeline.visual_assets = [
        TimedVisualAsset(Path("a.mp4"), 0.0, 2.0, AssetType.VIDEO),
        TimedVisualAsset(Path("b.mp4"), 2.0, 4.0, AssetType.VIDEO),
    ]
    before = timeline_input_fingerprint(state)
    state.timeline.transition_settings.effect = "wipeleft"
    assert timeline_input_fingerprint(state) != before
