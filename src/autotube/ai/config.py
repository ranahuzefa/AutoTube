"""AI keyword generation configuration."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings


@dataclass
class AIConfig:
    """Derived, non-persisted AI configuration view."""

    enabled: bool
    provider: str
    model: str
    api_key_env_var: str
    base_url: str
    temperature: float
    max_keywords: int
    batch_size: int
    max_input_chars: int
    max_keyword_chars: int
    timeout: float
    max_retries: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "AIConfig":
        return cls(
            enabled=settings.ai_enabled,
            provider=settings.ai_provider,
            model=settings.ai_model,
            api_key_env_var=settings.ai_api_key_env_var,
            base_url=settings.ai_base_url,
            temperature=settings.ai_temperature,
            max_keywords=settings.ai_max_keywords,
            batch_size=settings.ai_batch_size,
            max_input_chars=settings.ai_max_input_chars,
            max_keyword_chars=settings.ai_max_keyword_chars,
            timeout=settings.ai_timeout,
            max_retries=settings.ai_max_retries,
        )

    def errors(self) -> list[str]:
        errors: list[str] = []
        from .registry import default_ai_provider_registry

        if self.provider not in default_ai_provider_registry().known_ids():
            errors.append(f"Unsupported AI provider: {self.provider!r}.")
        if not self.model.strip():
            errors.append("AI model must be set.")
        if not self.api_key_env_var.strip():
            errors.append("AI API key environment variable must be set.")
        if not self.base_url.lower().startswith(("http://", "https://")):
            errors.append("AI base URL must be an http(s) URL.")
        if not 0.0 <= self.temperature <= 2.0:
            errors.append("AI temperature must be between 0.0 and 2.0.")
        if self.max_keywords <= 0:
            errors.append("AI max keywords must be positive.")
        if self.batch_size <= 0:
            errors.append("AI batch size must be positive.")
        if self.max_input_chars <= 0:
            errors.append("AI max input chars must be positive.")
        if self.max_keyword_chars <= 0:
            errors.append("AI max keyword chars must be positive.")
        if self.timeout <= 0:
            errors.append("AI timeout must be positive.")
        if self.max_retries < 0:
            errors.append("AI max retries must be non-negative.")
        return errors
