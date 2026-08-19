"""Application settings: dataclass with env overrides and atomic persistence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import (
    DEFAULT_AI_API_KEY_ENV_VAR,
    DEFAULT_AI_BASE_URL,
    DEFAULT_AI_BATCH_SIZE,
    DEFAULT_AI_ENABLED,
    DEFAULT_AI_IMAGE_API_KEY_ENV_VAR,
    DEFAULT_AI_IMAGE_BASE_URL,
    DEFAULT_AI_IMAGE_ENABLED,
    DEFAULT_AI_IMAGE_MODEL,
    DEFAULT_AI_IMAGE_PROVIDER,
    DEFAULT_AI_IMAGE_TIMEOUT,
    DEFAULT_AI_MAX_INPUT_CHARS,
    DEFAULT_AI_MAX_KEYWORD_CHARS,
    DEFAULT_AI_MAX_KEYWORDS,
    DEFAULT_AI_MAX_RETRIES,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROVIDER,
    DEFAULT_AI_TEMPERATURE,
    DEFAULT_AI_TIMEOUT,
    DEFAULT_AI_VIDEO_API_KEY_ENV_VAR,
    DEFAULT_AI_VIDEO_BASE_URL,
    DEFAULT_AI_VIDEO_ENABLED,
    DEFAULT_AI_VIDEO_MODEL,
    DEFAULT_AI_VIDEO_PROVIDER,
    DEFAULT_AI_VIDEO_TIMEOUT,
    DEFAULT_FPS,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MUSIC_VOLUME,
    DEFAULT_RESOLUTION,
    DEFAULT_STOCK_PROVIDERS,
    DEFAULT_WHISPER_MODEL,
    LEGACY_AI_API_KEY_ENV_VAR,
    LEGACY_AI_BASE_URL,
    LEGACY_AI_MODEL,
)
from .exceptions import ValidationError

ENV_PREFIX = "AUTOTUBE_"


def _env_name(field_name: str) -> str:
    return f"{ENV_PREFIX}{field_name.upper()}"


def _coerce_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def _parse_stock_providers(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return list(DEFAULT_STOCK_PROVIDERS)


def _migrate_legacy_ai_values(data: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(data)
    if migrated.get("ai_base_url") == LEGACY_AI_BASE_URL:
        migrated["ai_base_url"] = DEFAULT_AI_BASE_URL
    if migrated.get("ai_api_key_env_var") == LEGACY_AI_API_KEY_ENV_VAR:
        migrated["ai_api_key_env_var"] = DEFAULT_AI_API_KEY_ENV_VAR
    if migrated.get("ai_model") == LEGACY_AI_MODEL:
        migrated["ai_model"] = DEFAULT_AI_MODEL
    return migrated


@dataclass
class Settings:
    """User-level application settings."""

    output_dir: Path = field(default_factory=lambda: Path("output"))
    pexels_api_key: str = ""
    pixabay_api_key: str = ""
    stock_providers: list[str] = field(
        default_factory=lambda: list(DEFAULT_STOCK_PROVIDERS)
    )
    whisper_model: str = DEFAULT_WHISPER_MODEL
    fps: int = DEFAULT_FPS
    resolution: str = DEFAULT_RESOLUTION
    music_volume: float = DEFAULT_MUSIC_VOLUME
    log_level: str = DEFAULT_LOG_LEVEL
    ai_enabled: bool = DEFAULT_AI_ENABLED
    ai_provider: str = DEFAULT_AI_PROVIDER
    ai_model: str = DEFAULT_AI_MODEL
    ai_api_key_env_var: str = DEFAULT_AI_API_KEY_ENV_VAR
    ai_base_url: str = DEFAULT_AI_BASE_URL
    ai_temperature: float = DEFAULT_AI_TEMPERATURE
    ai_max_keywords: int = DEFAULT_AI_MAX_KEYWORDS
    ai_batch_size: int = DEFAULT_AI_BATCH_SIZE
    ai_max_input_chars: int = DEFAULT_AI_MAX_INPUT_CHARS
    ai_max_keyword_chars: int = DEFAULT_AI_MAX_KEYWORD_CHARS
    ai_timeout: float = DEFAULT_AI_TIMEOUT
    ai_max_retries: int = DEFAULT_AI_MAX_RETRIES
    ai_image_enabled: bool = DEFAULT_AI_IMAGE_ENABLED
    ai_image_provider: str = DEFAULT_AI_IMAGE_PROVIDER
    ai_image_model: str = DEFAULT_AI_IMAGE_MODEL
    ai_image_api_key_env_var: str = DEFAULT_AI_IMAGE_API_KEY_ENV_VAR
    ai_image_base_url: str = DEFAULT_AI_IMAGE_BASE_URL
    ai_image_timeout: float = DEFAULT_AI_IMAGE_TIMEOUT
    ai_video_enabled: bool = DEFAULT_AI_VIDEO_ENABLED
    ai_video_provider: str = DEFAULT_AI_VIDEO_PROVIDER
    ai_video_model: str = DEFAULT_AI_VIDEO_MODEL
    ai_video_api_key_env_var: str = DEFAULT_AI_VIDEO_API_KEY_ENV_VAR
    ai_video_base_url: str = DEFAULT_AI_VIDEO_BASE_URL
    ai_video_timeout: float = DEFAULT_AI_VIDEO_TIMEOUT

    def to_dict(self) -> dict[str, Any]:
        # API keys are deliberately excluded: they live in secure secret
        # storage, never in settings.json.
        return {
            "output_dir": str(self.output_dir),
            "stock_providers": list(self.stock_providers),
            "whisper_model": self.whisper_model,
            "fps": self.fps,
            "resolution": self.resolution,
            "music_volume": self.music_volume,
            "log_level": self.log_level,
            "ai_enabled": self.ai_enabled,
            "ai_provider": self.ai_provider,
            "ai_model": self.ai_model,
            "ai_api_key_env_var": self.ai_api_key_env_var,
            "ai_base_url": self.ai_base_url,
            "ai_temperature": self.ai_temperature,
            "ai_max_keywords": self.ai_max_keywords,
            "ai_batch_size": self.ai_batch_size,
            "ai_max_input_chars": self.ai_max_input_chars,
            "ai_max_keyword_chars": self.ai_max_keyword_chars,
            "ai_timeout": self.ai_timeout,
            "ai_max_retries": self.ai_max_retries,
            "ai_image_enabled": self.ai_image_enabled,
            "ai_image_provider": self.ai_image_provider,
            "ai_image_model": self.ai_image_model,
            "ai_image_api_key_env_var": self.ai_image_api_key_env_var,
            "ai_image_base_url": self.ai_image_base_url,
            "ai_image_timeout": self.ai_image_timeout,
            "ai_video_enabled": self.ai_video_enabled,
            "ai_video_provider": self.ai_video_provider,
            "ai_video_model": self.ai_video_model,
            "ai_video_api_key_env_var": self.ai_video_api_key_env_var,
            "ai_video_base_url": self.ai_video_base_url,
            "ai_video_timeout": self.ai_video_timeout,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        data = _migrate_legacy_ai_values(data)
        return cls(
            output_dir=Path(str(data.get("output_dir", "output"))),
            stock_providers=_parse_stock_providers(
                data.get("stock_providers", list(DEFAULT_STOCK_PROVIDERS))
            ),
            whisper_model=str(data.get("whisper_model", "base")),
            fps=int(data.get("fps", 30)),
            resolution=str(data.get("resolution", "1920x1080")),
            music_volume=float(data.get("music_volume", 0.2)),
            log_level=str(data.get("log_level", "INFO")),
            ai_enabled=bool(data.get("ai_enabled", DEFAULT_AI_ENABLED)),
            ai_provider=str(data.get("ai_provider", DEFAULT_AI_PROVIDER)),
            ai_model=str(data.get("ai_model", DEFAULT_AI_MODEL)),
            ai_api_key_env_var=str(
                data.get("ai_api_key_env_var", DEFAULT_AI_API_KEY_ENV_VAR)
            ),
            ai_base_url=str(data.get("ai_base_url", DEFAULT_AI_BASE_URL)),
            ai_temperature=float(data.get("ai_temperature", DEFAULT_AI_TEMPERATURE)),
            ai_max_keywords=int(data.get("ai_max_keywords", DEFAULT_AI_MAX_KEYWORDS)),
            ai_batch_size=int(data.get("ai_batch_size", DEFAULT_AI_BATCH_SIZE)),
            ai_max_input_chars=int(
                data.get("ai_max_input_chars", DEFAULT_AI_MAX_INPUT_CHARS)
            ),
            ai_max_keyword_chars=int(
                data.get("ai_max_keyword_chars", DEFAULT_AI_MAX_KEYWORD_CHARS)
            ),
            ai_timeout=float(data.get("ai_timeout", DEFAULT_AI_TIMEOUT)),
            ai_max_retries=int(data.get("ai_max_retries", DEFAULT_AI_MAX_RETRIES)),
            ai_image_enabled=bool(
                data.get("ai_image_enabled", DEFAULT_AI_IMAGE_ENABLED)
            ),
            ai_image_provider=str(
                data.get("ai_image_provider", DEFAULT_AI_IMAGE_PROVIDER)
            ),
            ai_image_model=str(data.get("ai_image_model", DEFAULT_AI_IMAGE_MODEL)),
            ai_image_api_key_env_var=str(
                data.get(
                    "ai_image_api_key_env_var", DEFAULT_AI_IMAGE_API_KEY_ENV_VAR
                )
            ),
            ai_image_base_url=str(
                data.get("ai_image_base_url", DEFAULT_AI_IMAGE_BASE_URL)
            ),
            ai_image_timeout=float(
                data.get("ai_image_timeout", DEFAULT_AI_IMAGE_TIMEOUT)
            ),
            ai_video_enabled=bool(
                data.get("ai_video_enabled", DEFAULT_AI_VIDEO_ENABLED)
            ),
            ai_video_provider=str(
                data.get("ai_video_provider", DEFAULT_AI_VIDEO_PROVIDER)
            ),
            ai_video_model=str(data.get("ai_video_model", DEFAULT_AI_VIDEO_MODEL)),
            ai_video_api_key_env_var=str(
                data.get(
                    "ai_video_api_key_env_var", DEFAULT_AI_VIDEO_API_KEY_ENV_VAR
                )
            ),
            ai_video_base_url=str(
                data.get("ai_video_base_url", DEFAULT_AI_VIDEO_BASE_URL)
            ),
            ai_video_timeout=float(
                data.get("ai_video_timeout", DEFAULT_AI_VIDEO_TIMEOUT)
            ),
        )


def _apply_env_overrides(settings: Settings) -> Settings:
    """Apply AUTOTUBE_* environment variables on top of loaded settings."""
    for name in (
        "output_dir",
        "pexels_api_key",
        "pixabay_api_key",
        "stock_providers",
        "whisper_model",
        "fps",
        "resolution",
        "music_volume",
        "log_level",
        "ai_enabled",
        "ai_provider",
        "ai_model",
        "ai_api_key_env_var",
        "ai_base_url",
        "ai_temperature",
        "ai_max_keywords",
        "ai_batch_size",
        "ai_max_input_chars",
        "ai_max_keyword_chars",
        "ai_timeout",
        "ai_max_retries",
        "ai_image_enabled",
        "ai_image_provider",
        "ai_image_model",
        "ai_image_api_key_env_var",
        "ai_image_base_url",
        "ai_image_timeout",
        "ai_video_enabled",
        "ai_video_provider",
        "ai_video_model",
        "ai_video_api_key_env_var",
        "ai_video_base_url",
        "ai_video_timeout",
    ):
        env = os.environ.get(_env_name(name))
        if env is None or env == "":
            continue
        if name == "output_dir":
            settings.output_dir = Path(env)
        elif name == "stock_providers":
            settings.stock_providers = _parse_stock_providers(env)
        elif name in ("fps",):
            settings.fps = int(env)
        elif name in ("music_volume",):
            settings.music_volume = float(env)
        elif name == "ai_enabled":
            settings.ai_enabled = _coerce_bool(env)
        elif name in ("ai_image_enabled", "ai_video_enabled"):
            setattr(settings, name, _coerce_bool(env))
        elif name in (
            "ai_temperature",
            "ai_timeout",
            "ai_image_timeout",
            "ai_video_timeout",
        ):
            setattr(settings, name, float(env))
        elif name in (
            "ai_max_keywords",
            "ai_batch_size",
            "ai_max_input_chars",
            "ai_max_keyword_chars",
            "ai_max_retries",
        ):
            setattr(settings, name, int(env))
        else:
            setattr(settings, name, env)
    return settings


def load_settings(apply_env: bool = True) -> Settings:
    """Load settings from disk (defaults if missing), then apply env overrides.

    API keys are never loaded from settings.json. Any legacy plaintext keys
    found on disk are migrated to secure secret storage and removed exactly once.
    """
    from .storage import SettingsStore

    store = SettingsStore()
    if store.path.exists():
        settings = store.load()
        _migrate_legacy_secret_keys()
    else:
        settings = Settings()

    settings.pexels_api_key = _load_secret(
        "pexels_api_key", settings.pexels_api_key
    )
    settings.pixabay_api_key = _load_secret(
        "pixabay_api_key", settings.pixabay_api_key
    )

    if apply_env:
        settings = _apply_env_overrides(settings)
    return settings


def save_settings(settings: Settings) -> None:
    """Persist non-secret settings atomically, and API keys to secret storage.

    Env overrides are not written back. API keys are written only to the secure
    secret store, never into settings.json.
    """
    from .storage import SettingsStore
    from .secrets import default_secret_store

    secret_store = default_secret_store()
    secret_store.set("pexels_api_key", settings.pexels_api_key)
    secret_store.set("pixabay_api_key", settings.pixabay_api_key)
    SettingsStore().save(settings)


def _migrate_legacy_secret_keys() -> None:
    """Move plaintext API keys from settings.json into secure storage once.

    This reads the raw settings file directly so it can distinguish a legacy
    plaintext key from a key that was already migrated and removed.
    """
    from .storage import SettingsStore

    store = SettingsStore()
    try:
        raw = store.path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return

    if not isinstance(data, dict):
        return

    pexels = data.get("pexels_api_key")
    pixabay = data.get("pixabay_api_key")
    if not pexels and not pixabay:
        return

    from .secrets import default_secret_store

    secret_store = default_secret_store()
    if pexels and not secret_store.get("pexels_api_key"):
        secret_store.set("pexels_api_key", str(pexels))
    if pixabay and not secret_store.get("pixabay_api_key"):
        secret_store.set("pixabay_api_key", str(pixabay))

    # Remove migrated keys from the on-disk settings object without touching
    # any other persisted fields.
    data.pop("pexels_api_key", None)
    data.pop("pixabay_api_key", None)
    cleaned = Settings.from_dict(data)
    store.save(cleaned)


def _load_secret(name: str, settings_value: str) -> str:
    """Return the secure-stored secret, falling back to an in-memory value.

    Env-var precedence is applied separately in ``_apply_env_overrides`` so it
    always wins over both secure storage and any legacy in-memory value.
    """
    from .secrets import default_secret_store

    try:
        stored = default_secret_store().get(name)
    except Exception:  # noqa: BLE001 - a missing/corrupt store is non-fatal here
        stored = ""

    return stored or settings_value


def _validate_stock_providers(providers: list[str]) -> None:
    from .stock.registry import default_stock_provider_registry

    known = default_stock_provider_registry().known_ids()
    seen: set[str] = set()
    for provider_id in providers:
        if provider_id not in known:
            raise ValidationError(f"Unsupported stock provider: {provider_id!r}.")
        if provider_id in seen:
            raise ValidationError(
                f"Duplicate stock provider in ordering: {provider_id!r}."
            )
        seen.add(provider_id)


def _validate_generation_settings(
    label: str,
    enabled: bool,
    provider: str,
    model: str,
    api_key_env_var: str,
    base_url: str,
    timeout: float,
) -> None:
    if timeout <= 0:
        raise ValidationError(f"{label} timeout must be positive.")
    if not enabled:
        return
    if not provider.strip():
        raise ValidationError(f"{label} provider must be set when enabled.")
    if not model.strip():
        raise ValidationError(f"{label} model must be set when enabled.")
    if not api_key_env_var.strip():
        raise ValidationError(
            f"{label} API key environment variable must be set when enabled."
        )
    if not base_url.lower().startswith(("http://", "https://")):
        raise ValidationError(f"{label} base URL must be an http(s) URL.")


def validate_settings(settings: Settings) -> None:
    _validate_stock_providers(settings.stock_providers)
    if not 0.0 <= settings.music_volume <= 1.0:
        raise ValidationError("Music volume must be between 0.0 and 1.0.")
    if settings.fps <= 0:
        raise ValidationError("FPS must be positive.")
    try:
        width, height = settings.resolution.lower().split("x")
        int(width)
        int(height)
    except ValueError as exc:
        raise ValidationError(
            f"Invalid resolution {settings.resolution!r}; expected WIDTHxHEIGHT."
        ) from exc
    if not 0.0 <= settings.ai_temperature <= 2.0:
        raise ValidationError("AI temperature must be between 0.0 and 2.0.")
    if settings.ai_max_keywords <= 0:
        raise ValidationError("AI max keywords must be positive.")
    if settings.ai_batch_size <= 0:
        raise ValidationError("AI batch size must be positive.")
    if settings.ai_max_input_chars <= 0:
        raise ValidationError("AI max input chars must be positive.")
    if settings.ai_max_keyword_chars <= 0:
        raise ValidationError("AI max keyword chars must be positive.")
    if settings.ai_timeout <= 0:
        raise ValidationError("AI timeout must be positive.")
    if settings.ai_max_retries < 0:
        raise ValidationError("AI max retries must be non-negative.")
    _validate_generation_settings(
        "AI image",
        settings.ai_image_enabled,
        settings.ai_image_provider,
        settings.ai_image_model,
        settings.ai_image_api_key_env_var,
        settings.ai_image_base_url,
        settings.ai_image_timeout,
    )
    _validate_generation_settings(
        "AI video",
        settings.ai_video_enabled,
        settings.ai_video_provider,
        settings.ai_video_model,
        settings.ai_video_api_key_env_var,
        settings.ai_video_base_url,
        settings.ai_video_timeout,
    )
    if settings.ai_enabled:
        if not settings.ai_model.strip():
            raise ValidationError("AI model must be set when AI is enabled.")
        if not settings.ai_api_key_env_var.strip():
            raise ValidationError(
                "AI API key environment variable must be set when AI is enabled."
            )
