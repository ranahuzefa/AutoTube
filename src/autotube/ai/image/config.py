"""AI image generation configuration."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings


@dataclass
class AIImageConfig:
    """Derived, non-persisted AI image generation configuration view."""

    enabled: bool
    provider: str
    model: str
    api_key_env_var: str
    base_url: str
    timeout: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "AIImageConfig":
        return cls(
            enabled=settings.ai_image_enabled,
            provider=settings.ai_image_provider,
            model=settings.ai_image_model,
            api_key_env_var=settings.ai_image_api_key_env_var,
            base_url=settings.ai_image_base_url,
            timeout=settings.ai_image_timeout,
        )

    def errors(self) -> list[str]:
        errors: list[str] = []
        from .registry import default_ai_image_provider_registry

        if self.timeout <= 0:
            errors.append("AI image timeout must be positive.")
        if not self.enabled:
            return errors
        if self.provider not in default_ai_image_provider_registry().known_ids():
            errors.append(f"Unsupported AI image provider: {self.provider!r}.")
        if not self.model.strip():
            errors.append("AI image model must be set.")
        if not self.api_key_env_var.strip():
            errors.append("AI image API key environment variable must be set.")
        if not self.base_url.lower().startswith(("http://", "https://")):
            errors.append("AI image base URL must be an http(s) URL.")
        return errors
