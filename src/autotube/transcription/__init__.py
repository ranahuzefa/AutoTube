"""Local faster-whisper transcription and segmentation."""

from .config import TranscriptionConfig
from .device import DeviceDetector, DeviceInfo
from .model import WhisperModelLoader
from .segments import SegmentBuilder
from .service import FasterWhisperTranscriptionService, TranscriptionResult
from .workflow import TranscriptionWorkflow

__all__ = [
    "DeviceDetector",
    "DeviceInfo",
    "FasterWhisperTranscriptionService",
    "SegmentBuilder",
    "TranscriptionConfig",
    "TranscriptionResult",
    "TranscriptionWorkflow",
    "WhisperModelLoader",
]
