"""Tests for LicenseStore persistence."""

from __future__ import annotations

from pathlib import Path

from autotube.licensing.storage import LicenseStore
from autotube.licensing.types import LicenseState, LicenseStatus


def test_roundtrip_persistence(tmp_path: Path) -> None:
    store = LicenseStore(directory=tmp_path)
    state = LicenseState(
        license_id="lic-1",
        device_id_hash="a" * 64,
        activation_token="ATK1.token",
        entitlements=["render"],
        status=LicenseStatus.ACTIVATED,
    )
    store.save(state)
    restored = store.load()
    assert restored.license_id == "lic-1"
    assert restored.status == LicenseStatus.ACTIVATED
    assert restored.entitlements == ["render"]


def test_restart_restores_status(tmp_path: Path) -> None:
    store = LicenseStore(directory=tmp_path)
    store.save(LicenseState(status=LicenseStatus.OFFLINE_GRACE))
    restored = LicenseStore(directory=tmp_path).load()
    assert restored.status == LicenseStatus.OFFLINE_GRACE


def test_missing_file_returns_default(tmp_path: Path) -> None:
    store = LicenseStore(directory=tmp_path / "missing")
    state = store.load()
    assert state.status == LicenseStatus.NOT_ACTIVATED


def test_raw_product_key_absent(tmp_path: Path) -> None:
    store = LicenseStore(directory=tmp_path)
    store.save(LicenseState(activation_token="ATK1.token"))
    text = store.path.read_text(encoding="utf-8")
    assert "product_key" not in text
