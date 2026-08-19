"""Tests for the SecretStore abstraction and its fail-closed behavior."""

from __future__ import annotations

import pytest

from autotube.exceptions import SecretStorageError
from autotube.secrets import SecretStore


class _MemoryBackend:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, name: str) -> str:
        return self.data.get(name, "")

    def set(self, name: str, value: str) -> None:
        self.data[name] = value

    def delete(self, name: str) -> None:
        self.data.pop(name, None)


def test_roundtrip() -> None:
    backend = _MemoryBackend()
    store = SecretStore(backend=backend)
    store.set("pexels_api_key", "secret-value")
    assert store.get("pexels_api_key") == "secret-value"


def test_save_read_new_instance_persists() -> None:
    backend = _MemoryBackend()
    SecretStore(backend=backend).set("pixabay_api_key", "pix-value")
    assert SecretStore(backend=backend).get("pixabay_api_key") == "pix-value"


def test_missing_secret_returns_empty() -> None:
    assert SecretStore(backend=_MemoryBackend()).get("missing") == ""


def test_empty_set_deletes() -> None:
    backend = _MemoryBackend()
    store = SecretStore(backend=backend)
    store.set("pexels_api_key", "value")
    store.set("pexels_api_key", "")
    assert store.get("pexels_api_key") == ""


class _FailingBackend:
    def get(self, name: str) -> str:
        raise SecretStorageError("corrupt")

    def set(self, name: str, value: str) -> None:
        raise SecretStorageError("corrupt")

    def delete(self, name: str) -> None:
        raise SecretStorageError("corrupt")


def test_corrupt_backend_surfaces_error() -> None:
    store = SecretStore(backend=_FailingBackend())
    with pytest.raises(SecretStorageError):
        store.get("pexels_api_key")
    with pytest.raises(SecretStorageError):
        store.set("pexels_api_key", "value")


def test_backend_exception_is_wrapped() -> None:
    class _RaisingBackend:
        def get(self, name: str) -> str:
            raise RuntimeError("boom")

        def set(self, name: str, value: str) -> None:
            raise RuntimeError("boom")

        def delete(self, name: str) -> None:
            raise RuntimeError("boom")

    store = SecretStore(backend=_RaisingBackend())
    with pytest.raises(SecretStorageError):
        store.get("pexels_api_key")
    with pytest.raises(SecretStorageError):
        store.set("pexels_api_key", "value")
