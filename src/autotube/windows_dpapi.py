"""Windows DPAPI secret backend implemented with stdlib ``ctypes``.

Encrypted blobs are base64-encoded and stored in a small JSON file beside
``settings.json``. DPAPI binds the ciphertext to the current Windows user, so the
file contains only user-bound ciphertext, never a raw API key.

No third-party dependency is required. This backend is Windows-only; importing or
constructing it on other platforms raises ``SecretStorageError``.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path

from .exceptions import SecretStorageError
from .secrets import SECRETS_FILE_NAME, SecretBackend
from .storage import AtomicFileWriter

_CRYPTPROTECT_UI_FORBIDDEN = 0x01


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _blob_from_bytes(data: bytes) -> _DATA_BLOB:
    buffer = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(
        len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))
    )


def _bytes_from_blob(blob: _DATA_BLOB) -> bytes:
    if not blob.pbData or blob.cbData == 0:
        return b""
    return ctypes.string_at(blob.pbData, blob.cbData)


class WindowsDPAPIBackend(SecretBackend):
    """Persist named secrets in a user-bound DPAPI-encrypted JSON file."""

    def __init__(self, directory: Path | None = None) -> None:
        if os.name != "nt":
            raise SecretStorageError(
                "Windows DPAPI is only available on Windows."
            )
        self.directory = Path(directory) if directory else self._default_directory()
        self.path = self.directory / SECRETS_FILE_NAME

        self._crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure()

    @staticmethod
    def _default_directory() -> Path:
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "AutoTube"

    def _configure(self) -> None:
        self._crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(_DATA_BLOB),
            wintypes.LPCWSTR,
            ctypes.POINTER(_DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(_DATA_BLOB),
        ]
        self._crypt32.CryptProtectData.restype = wintypes.BOOL

        self._crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DATA_BLOB),
            wintypes.LPCWSTR,
            ctypes.POINTER(_DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(_DATA_BLOB),
        ]
        self._crypt32.CryptUnprotectData.restype = wintypes.BOOL

        self._kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self._kernel32.LocalFree.restype = ctypes.c_void_p

    def get(self, name: str) -> str:
        data = self._read()
        encoded = data.get(name)
        if not encoded:
            return ""

        try:
            blob = base64.urlsafe_b64decode(encoded)
        except (ValueError, TypeError) as exc:
            raise SecretStorageError(
                f"Secure secret {name!r} is corrupt."
            ) from exc

        try:
            plain = self._unprotect(blob)
        except SecretStorageError:
            raise
        return plain.decode("utf-8", errors="strict")

    def set(self, name: str, value: str) -> None:
        value = str(value)
        if not value.strip():
            self.delete(name)
            return

        data = self._read()
        blob = self._protect(value.encode("utf-8"))
        data[name] = base64.urlsafe_b64encode(blob).decode("ascii")
        self._write(data)

    def delete(self, name: str) -> None:
        data = self._read()
        if name not in data:
            return
        del data[name]
        self._write(data)

    def _protect(self, data: bytes) -> bytes:
        in_blob = _blob_from_bytes(data)
        out_blob = _DATA_BLOB()
        if not self._crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        ):
            raise SecretStorageError("Windows DPAPI failed to protect the secret.")
        try:
            return _bytes_from_blob(out_blob)
        finally:
            self._free(out_blob)

    def _unprotect(self, data: bytes) -> bytes:
        in_blob = _blob_from_bytes(data)
        out_blob = _DATA_BLOB()
        if not self._crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        ):
            raise SecretStorageError(
                "Windows DPAPI failed to unprotect the secret; it may be corrupt "
                "or bound to another Windows user."
            )
        try:
            return _bytes_from_blob(out_blob)
        finally:
            self._free(out_blob)

    def _free(self, blob: _DATA_BLOB) -> None:
        if blob.pbData:
            self._kernel32.LocalFree(ctypes.cast(blob.pbData, ctypes.c_void_p))

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise SecretStorageError(
                f"Secure secret store is corrupt: {self.path}"
            ) from exc
        if not isinstance(data, dict):
            raise SecretStorageError(
                f"Secure secret store must be a JSON object: {self.path}"
            )
        return data

    def _write(self, data: dict) -> None:
        try:
            AtomicFileWriter(self.path).write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n"
            )
        except OSError as exc:
            raise SecretStorageError(
                f"Cannot write secure secret store {self.path}: {exc}"
            ) from exc
