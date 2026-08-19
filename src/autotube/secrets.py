"""Secret storage abstraction for non-settings API keys.

``settings.json`` must never contain raw API keys. This module provides a small
backend-agnostic store backed by a pluggable provider, with a Windows DPAPI
provider implemented on top of stdlib ``ctypes`` (no extra dependency).
"""

from __future__ import annotations

import abc

from .exceptions import SecretStorageError

SECRETS_FILE_NAME = "secrets.json"


class SecretBackend(abc.ABC):
    """Persist and retrieve named secret values."""

    def get(self, name: str) -> str:
        """Return the stored secret, or ``""`` when it is absent."""
        raise NotImplementedError

    def set(self, name: str, value: str) -> None:
        """Store a secret value."""
        raise NotImplementedError

    def delete(self, name: str) -> None:
        """Remove a stored secret."""
        raise NotImplementedError


class SecretStore:
    """Named-secret facade used by the application.

    The default backend is Windows DPAPI. Callers can inject an alternative
    backend for tests or non-Windows platforms. A failed backend is surfaced as
    ``SecretStorageError`` rather than silently returning an empty value, so
    missing or corrupt secure storage is never mistaken for a valid empty key.
    """

    def __init__(self, backend: SecretBackend | None = None) -> None:
        self._backend = backend or self._default_backend()

    @staticmethod
    def _default_backend() -> SecretBackend:
        from .windows_dpapi import WindowsDPAPIBackend

        return WindowsDPAPIBackend()

    def get(self, name: str) -> str:
        try:
            value = self._backend.get(name)
        except SecretStorageError:
            raise
        except Exception as exc:  # noqa: BLE001 - backend boundary
            raise SecretStorageError(
                f"Cannot read secure secret {name!r}."
            ) from exc
        return "" if value is None else str(value)

    def set(self, name: str, value: str) -> None:
        value = str(value)
        if not value.strip():
            self.delete(name)
            return
        try:
            self._backend.set(name, value)
        except SecretStorageError:
            raise
        except Exception as exc:  # noqa: BLE001 - backend boundary
            raise SecretStorageError(
                f"Cannot store secure secret {name!r}."
            ) from exc

    def delete(self, name: str) -> None:
        try:
            self._backend.delete(name)
        except SecretStorageError:
            raise
        except Exception as exc:  # noqa: BLE001 - backend boundary
            raise SecretStorageError(
                f"Cannot remove secure secret {name!r}."
            ) from exc


def default_secret_store() -> SecretStore:
    """Return the platform default secret store."""
    return SecretStore()
