"""Tests for device detection."""

from __future__ import annotations

from autotube.transcription.device import DeviceDetector


def test_auto_cpu_when_no_cuda() -> None:
    detector = DeviceDetector(cuda_count=lambda: 0)
    info = detector.detect("auto", "auto")
    assert info.device == "cpu"
    assert info.compute_type == "int8"
    assert info.cuda_available is False


def test_auto_cuda_when_available() -> None:
    detector = DeviceDetector(cuda_count=lambda: 1)
    info = detector.detect("auto", "auto")
    assert info.device == "cuda"
    assert info.compute_type == "float16"
    assert info.cuda_available is True


def test_cuda_request_falls_back_to_cpu() -> None:
    detector = DeviceDetector(cuda_count=lambda: 0)
    info = detector.detect("cuda", "auto")
    assert info.device == "cpu"
    assert "falling back" in info.reason


def test_explicit_compute_type_preserved() -> None:
    detector = DeviceDetector(cuda_count=lambda: 0)
    info = detector.detect("cpu", "float32")
    assert info.compute_type == "float32"
