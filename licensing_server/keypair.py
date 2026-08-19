"""Ed25519 key-pair management for the licensing server."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .constants import KEYS_DIR, PRIVATE_KEY_FILE, PUBLIC_KEY_FILE


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def save_private_key(path: Path, private_key: Ed25519PrivateKey) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path


def save_public_key(path: Path, public_key: Ed25519PublicKey) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return path


def load_private_key(path: Path = PRIVATE_KEY_FILE) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Expected an Ed25519 private key.")
    return key


def load_public_key(path: Path = PUBLIC_KEY_FILE) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(Path(path).read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Expected an Ed25519 public key.")
    return key


def public_key_fingerprint(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    import hashlib

    return hashlib.sha256(raw).hexdigest()[:16]


def ensure_keypair(
    private_path: Path = PRIVATE_KEY_FILE,
    public_path: Path = PUBLIC_KEY_FILE,
) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Load an existing keypair or generate and persist a new one."""
    if private_path.exists() and public_path.exists():
        return load_private_key(private_path), load_public_key(public_path)

    private_key, public_key = generate_keypair()
    save_private_key(private_path, private_key)
    save_public_key(public_path, public_key)
    return private_key, public_key


def init_keypair() -> tuple[Path, Path, str]:
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    private_key, public_key = ensure_keypair()
    return PRIVATE_KEY_FILE, PUBLIC_KEY_FILE, public_key_fingerprint(public_key)
