"""FFmpeg/FFprobe subprocess runner.

The single subprocess boundary for all media commands. It always uses direct
argument lists (``shell=False``) and provides timeout and cancellation support.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from ..exceptions import MediaCancelledError, MediaCommandError
from .progress import FFmpegProgressParser, ProgressCallback

_STDERR_TAIL = 2000
_GRACE_SECONDS = 0.5

if os.name == "nt":
    _CREATE_NO_WINDOW = 0x08000000
else:
    _CREATE_NO_WINDOW = 0


@dataclass
class FFmpegResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed: float


class _BoundedBuffer:
    """Thread-safe tail buffer for stderr."""

    def __init__(self, max_chars: int = _STDERR_TAIL) -> None:
        self._max = max_chars
        self._data: list[str] = []
        self._length = 0
        self._lock = threading.Lock()

    def append(self, chunk: str) -> None:
        with self._lock:
            self._data.append(chunk)
            self._length += len(chunk)
            while self._length > self._max and self._data:
                removed = self._data.pop(0)
                self._length -= len(removed)

    def text(self) -> str:
        with self._lock:
            return "".join(self._data)[-self._max :]


class FFmpegRunner:
    """Run ffmpeg/ffprobe with progress, cancellation, and timeouts."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe") -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin

    def run(
        self,
        args: Sequence[str],
        *,
        duration: float | None = None,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
        timeout: float | None = None,
    ) -> FFmpegResult:
        """Run an FFmpeg/FFprobe command and return its result.

        ``args`` must be a complete list of tokens, including the executable.
        """
        if not args:
            raise MediaCommandError("No command provided.")

        executable = str(args[0])
        if not self._executable_available(executable):
            raise MediaCommandError(f"{Path(executable).name} not found: {executable}")

        start = time.monotonic()
        try:
            proc = subprocess.Popen(
                list(args),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                text=False,
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as exc:
            raise MediaCommandError(f"Failed to launch {executable}: {exc}") from exc

        stderr_buffer = _BoundedBuffer()
        parser = FFmpegProgressParser(total_duration=duration)
        stdout_parts: list[str] = []

        def _drain_stderr() -> None:
            assert proc.stderr is not None
            for raw in iter(proc.stderr.readline, b""):
                stderr_buffer.append(raw.decode("utf-8", errors="replace"))

        def _drain_stdout() -> None:
            assert proc.stdout is not None
            for raw in iter(proc.stdout.readline, b""):
                text = raw.decode("utf-8", errors="replace")
                stdout_parts.append(text)
                parser.parse_line(text, callback=progress)

        reader = threading.Thread(target=_drain_stderr, daemon=True)
        reader.start()
        out_reader = threading.Thread(target=_drain_stdout, daemon=True)
        out_reader.start()

        cancelled = False
        timed_out = False
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    self._terminate(proc)
                    break

                if timeout is not None and (time.monotonic() - start) > timeout:
                    timed_out = True
                    self._terminate(proc)
                    break

                if proc.poll() is not None:
                    break

                time.sleep(0.05)

            proc.wait()
            reader.join(timeout=2.0)
            out_reader.join(timeout=2.0)

            stdout = "".join(stdout_parts)
            result = FFmpegResult(
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr_buffer.text(),
                elapsed=time.monotonic() - start,
            )
        finally:
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()

        if cancelled:
            raise MediaCancelledError(f"{Path(executable).name} cancelled.")
        if timed_out:
            raise MediaCommandError(f"{Path(executable).name} timed out.")
        if proc.returncode != 0:
            raise MediaCommandError(
                f"{Path(executable).name} exited with code {proc.returncode}: "
                f"{result.stderr.strip()}"
            )

        return result

    def _executable_available(self, executable: str) -> bool:
        from shutil import which

        return which(executable) is not None or Path(executable).exists()

    @staticmethod
    def _terminate(proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
        except OSError:
            pass
        try:
            proc.wait(timeout=_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass
            proc.wait()
