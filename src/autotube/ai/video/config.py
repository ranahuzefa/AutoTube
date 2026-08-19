"""AI video generation configuration."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings


@dataclass
class AIVideoConfig:
    """Derived, non-persisted AI video generation configuration view."""

    enabled: bool
    provider: str
    model: str
    api_key_env_var: str
    base_url: str
    timeout: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "AIVideoConfig":
        return cls(
            enabled=settings.ai_video_enabled,
            provider=settings.ai_video_provider,
            model=settings.ai_video_model,
            api_key_env_var=settings.ai_video_api_key_env_var,
            base_url=settings.ai_video_base_url,
            timeout=settings.ai_video_timeout,
        )

    def errors(self) -> list[str]:
        errors: list[str] = []
        from .registry import default_ai_video_provider_registry

        if self.timeout <= 0:
            errors.append("AI video timeout must be positive.")
        if not self.enabled:
            return errors
        if self.provider not in default_ai_video_provider_registry().known_ids():
            errors.append(f"Unsupported AI video provider: {self.provider!r}.")
        if not self.model.strip():
            errors.append("AI video model must be set.")
        if not self.api_key_env_var.strip():
            errors.append("AI video API key environment variable must be set.")
        if not self.base_url.lower().startswith(("http://", "https://")):
            errors.append("AI video base URL must be an http(s) URL.")
        return errors
