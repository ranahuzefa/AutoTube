"""Windows DPAPI integration tests.

These run only on Windows and exercise the real DPAPI backend (round-trip,
missing, and no-plaintext-on-disk) using the actual ``ctypes`` implementation.
"""

from __future__ import annotations

import os

import pytest

from autotube.exceptions import SecretStorageError
from autotube.windows_dpapi import WindowsDPAPIBackend

pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="Windows DPAPI integration tests run only on Windows",
)


def test_dpapi_roundtrip(tmp_path) -> None:
    backend = WindowsDPAPIBackend(directory=tmp_path)
    backend.set("pexels_api_key", "dpapi-secret")
    assert backend.get("pexels_api_key") == "dpapi-secret"


def test_dpapi_restart_persistence(tmp_path) -> None:
    first = WindowsDPAPIBackend(directory=tmp_path)
    first.set("pixabay_api_key", "dpapi-persist")

    second = WindowsDPAPIBackend(directory=tmp_path)
    assert second.get("pixabay_api_key") == "dpapi-persist"


def test_dpapi_missing_returns_empty(tmp_path) -> None:
    backend = WindowsDPAPIBackend(directory=tmp_path)
    assert backend.get("missing") == ""


def test_dpapi_no_plaintext_on_disk(tmp_path) -> None:
    backend = WindowsDPAPIBackend(directory=tmp_path)
    backend.set("pexels_api_key", "super-secret-value")
    raw = backend.path.read_bytes()
    assert b"super-secret-value" not in raw


def test_dpapi_corrupt_store_fails(tmp_path) -> None:
    backend = WindowsDPAPIBackend(directory=tmp_path)
    backend.path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SecretStorageError):
        backend.get("pexels_api_key")
