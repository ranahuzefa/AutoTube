"""CPU/GPU device and compute-type detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class DeviceInfo:
    device: str
    compute_type: str
    cuda_available: bool
    reason: str


_CudaCountFn = Callable[[], int]


def _default_cuda_count() -> int:
    try:
        import ctranslate2  # lazy import

        return int(ctranslate2.get_cuda_device_count())
    except Exception:  # noqa: BLE001 - detection must never crash
        return 0


class DeviceDetector:
    """Resolve requested device/compute type to concrete values.

    Detection is testable by injecting a fake CUDA-count function.
    """

    def __init__(self, cuda_count: _CudaCountFn | None = None) -> None:
        self._cuda_count = cuda_count or _default_cuda_count

    def detect(self, requested_device: str, requested_compute_type: str) -> DeviceInfo:
        cuda_available = self._cuda_count() > 0

        if requested_device == "auto":
            device = "cuda" if cuda_available else "cpu"
            if device == "cuda":
                return DeviceInfo("cuda", "float16", True, "auto-detected CUDA")
            return DeviceInfo("cpu", "int8", False, "no CUDA device available")

        if requested_device == "cuda" and not cuda_available:
            return DeviceInfo(
                "cpu",
                self._resolve_compute("cpu", requested_compute_type),
                False,
                "CUDA requested but unavailable; falling back to CPU",
            )

        compute = self._resolve_compute(requested_device, requested_compute_type)
        return DeviceInfo(
            requested_device,
            compute,
            cuda_available and requested_device == "cuda",
            f"using requested device {requested_device}",
        )

    @staticmethod
    def _resolve_compute(device: str, requested_compute_type: str) -> str:
        if requested_compute_type != "auto":
            return requested_compute_type
        return "float16" if device == "cuda" else "int8"
