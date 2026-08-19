"""Tests for the privacy-conscious device identifier."""

from __future__ import annotations

import hashlib

from autotube.licensing.device import device_id_hash, stable_device_id


def test_stable_device_id_deterministic() -> None:
    assert stable_device_id() == stable_device_id()


def test_device_id_hash_stable() -> None:
    first = device_id_hash(b"test-namespace")
    second = device_id_hash(b"test-namespace")
    assert first == second
    assert len(first) == 64


def test_device_id_hash_does_not_contain_raw_id() -> None:
    raw = stable_device_id()
    digest = device_id_hash(b"test-namespace")
    assert raw not in digest


def test_device_id_hash_matches_manual_sha256() -> None:
    raw = stable_device_id().encode("utf-8")
    expected = hashlib.sha256(b"ns" + raw).hexdigest()
    assert device_id_hash(b"ns") == expected
