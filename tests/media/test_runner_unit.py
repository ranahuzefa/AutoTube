"""Unit tests for FFmpegRunner error mapping using injected fake Popen."""

from __future__ import annotations

import threading

import pytest

from autotube.exceptions import MediaCancelledError, MediaCommandError
from autotube.media.ffmpeg_runner import FFmpegRunner


class _FakeStream:
    def __init__(self, lines):
        self._lines = iter(lines)

    def readline(self):
        try:
            return next(self._lines)
        except StopIteration:
            return b""

    def read(self):
        return b""

    def close(self):
        pass


class _FakeProc:
    def __init__(self, returncode=0, stdout_lines=(), stderr_lines=()):
        self.returncode = returncode
        self.stdout = _FakeStream(stdout_lines)
        self.stderr = _FakeStream(stderr_lines)
        self._waited = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self._waited = True
        return self.returncode

    def terminate(self):
        pass

    def kill(self):
        pass


def test_missing_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    runner = FFmpegRunner(ffmpeg_bin="definitely_missing")
    with pytest.raises(MediaCommandError):
        runner.run(["definitely_missing", "-version"])


def test_nonzero_exit_maps_to_media_command_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(_):
        return "/fake/ffmpeg"

    monkeypatch.setattr("shutil.which", fake_which)
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda *a, **k: _FakeProc(returncode=1, stderr_lines=[b"bad input"]),
    )
    runner = FFmpegRunner()
    with pytest.raises(MediaCommandError) as exc:
        runner.run(["ffmpeg", "-i", "x.mp4"])
    assert "exited with code 1" in str(exc.value)


def test_cancel_maps_to_media_cancelled_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(_):
        return "/fake/ffmpeg"

    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr("shutil.which", fake_which)
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda *a, **k: _FakeProc(returncode=0, stdout_lines=()),
    )
    runner = FFmpegRunner()
    with pytest.raises(MediaCancelledError):
        runner.run(["ffmpeg", "-i", "x.mp4"], cancel_event=cancel)
