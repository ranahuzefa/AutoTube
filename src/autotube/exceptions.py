"""Exception hierarchy for AutoTube Creator."""

from __future__ import annotations


class AutoTubeError(Exception):
    """Base class for all AutoTube Creator errors."""


class ConfigurationError(AutoTubeError):
    """Raised when settings are missing or invalid."""


class ValidationError(AutoTubeError):
    """Raised when a project or input fails validation."""


class MissingVisualAssetsError(ValidationError):
    """Raised when one or more timeline visual slots are unresolved."""

    def __init__(self, report: str) -> None:
        super().__init__(f"Missing visual assets:\n{report}")
        self.report = report


class StorageError(AutoTubeError):
    """Raised when project/settings persistence fails."""


class CorruptProjectError(StorageError):
    """Raised when a project file cannot be deserialized."""


class SecretStorageError(StorageError):
    """Raised when secure secret storage is missing, corrupt, or unusable."""


class ServiceNotAvailableError(AutoTubeError):
    """Raised when a pipeline stage has no registered service."""


class MediaError(AutoTubeError):
    """Raised by media/FFmpeg operations."""


class MediaCommandError(MediaError):
    """Raised when an FFmpeg/FFprobe command fails or times out."""


class MediaCancelledError(MediaError):
    """Raised when an FFmpeg/FFprobe command is cancelled."""


class TranscriptionError(AutoTubeError):
    """Raised by transcription operations."""


class TranscriptionModelError(TranscriptionError):
    """Raised when a transcription model fails to load or download."""


class TranscriptionCancelledError(TranscriptionError):
    """Raised when transcription is cancelled cooperatively."""


class StockError(AutoTubeError):
    """Raised by stock search/download operations."""


class ProviderError(StockError):
    """Raised when a stock provider request fails."""


class RateLimitError(ProviderError):
    """Raised when a stock provider indicates rate limiting."""


class DownloadError(StockError):
    """Raised when a stock asset download fails."""


class DownloadCancelledError(DownloadError):
    """Raised when a stock asset download is cancelled."""


class AIError(AutoTubeError):
    """Raised by AI keyword generation operations."""


class AIConfigurationError(AIError):
    """Raised when AI configuration is missing or invalid."""


class AIProviderError(AIError):
    """Raised when an AI provider request fails."""

    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class AIRateLimitError(AIProviderError):
    """Raised when an AI provider indicates rate limiting."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message, retryable=True)
        self.retry_after = retry_after


class AIResponseError(AIError):
    """Raised when an AI provider response is malformed."""


class AICancelledError(AIError):
    """Raised when AI keyword generation is cancelled cooperatively."""


class LicenseError(AutoTubeError):
    """Base class for licensing errors."""


class LicenseInvalidError(LicenseError):
    """Raised when a product key or activation token is malformed."""


class LicenseServerUnavailableError(LicenseError):
    """Raised when the licensing server cannot be reached."""


class LicenseActivationLimitError(LicenseError):
    """Raised when the server reports the activation limit has been reached."""


class LicenseRevokedError(LicenseError):
    """Raised when a license has been revoked."""


class LicenseExpiredError(LicenseError):
    """Raised when a license has expired."""


class LicenseConfigurationError(LicenseError):
    """Raised when client-side licensing verification is not configured."""


class LicenseNotActivatedError(LicenseError):
    """Raised when a gated operation requires an activated license."""


_CANCELLATION_TYPES = (
    MediaCancelledError,
    DownloadCancelledError,
    TranscriptionCancelledError,
    AICancelledError,
)

_CANCELLATION_MESSAGES = {
    "pipeline cancelled.",
    "timeline render cancelled.",
}


def is_cancellation(exc: BaseException) -> bool:
    """Return True when ``exc`` represents a cooperative cancellation."""
    if isinstance(exc, _CANCELLATION_TYPES):
        return True
    return str(exc).strip().lower() in _CANCELLATION_MESSAGES
