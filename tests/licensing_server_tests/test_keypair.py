"""Tests for Ed25519 key-pair management."""

from __future__ import annotations

import os
from pathlib import Path

from licensing_server.keypair import (
    generate_keypair,
    load_private_key,
    load_public_key,
    public_key_fingerprint,
    save_private_key,
    save_public_key,
)


def test_roundtrip_persistence(tmp_path: Path) -> None:
    private_key, public_key = generate_keypair()
    priv_path = tmp_path / "signing.key"
    pub_path = tmp_path / "public.pem"
    save_private_key(priv_path, private_key)
    save_public_key(pub_path, public_key)

    loaded_private = load_private_key(priv_path)
    loaded_public = load_public_key(pub_path)

    assert loaded_private.private_bytes_raw() == private_key.private_bytes_raw()
    assert loaded_public.public_bytes_raw() == public_key.public_bytes_raw()


def test_private_file_has_0600_on_posix(tmp_path: Path) -> None:
    if os.name == "nt":
        return
    private_key, _ = generate_keypair()
    path = tmp_path / "signing.key"
    save_private_key(path, private_key)
    assert (path.stat().st_mode & 0o777) == 0o600


def test_fingerprint_is_non_sensitive() -> None:
    _, public_key = generate_keypair()
    fingerprint = public_key_fingerprint(public_key)
    assert len(fingerprint) == 16
    assert "PRIVATE" not in fingerprint.upper()
