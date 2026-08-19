"""Server-side SQLite license database.

Stores only SHA-256 hashes of product keys and redacted placeholders — never the
raw product key.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .constants import DATABASE_FILE


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LicenseRecord:
    license_id: str
    product_key_hash: str
    product_key_redacted: str
    entitlements: list[str]
    machine_limit: int
    expires_at: str | None
    status: str
    created_at: str
    revoked_at: str | None = None
    revoke_reason: str | None = None


@dataclass
class ActivationRecord:
    license_id: str
    device_id_hash: str
    activation_token: str
    activated_at: str
    last_validated_at: str
    status: str


def _hash_key(canonical_key: str) -> str:
    return hashlib.sha256(canonical_key.encode("ascii")).hexdigest()


class LicenseDatabase:
    def __init__(self, path: Path = DATABASE_FILE) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._create_schema()

    def _create_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                license_id TEXT PRIMARY KEY,
                product_key_hash TEXT UNIQUE NOT NULL,
                product_key_redacted TEXT NOT NULL,
                entitlements_json TEXT NOT NULL,
                machine_limit INTEGER NOT NULL,
                expires_at TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                revoke_reason TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activations (
                license_id TEXT NOT NULL,
                device_id_hash TEXT NOT NULL,
                activation_token TEXT NOT NULL,
                activated_at TEXT NOT NULL,
                last_validated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                PRIMARY KEY (license_id, device_id_hash)
            )
            """
        )
        self._conn.commit()

    def create_license(
        self,
        *,
        canonical_key: str,
        entitlements: list[str],
        machine_limit: int,
        expires_at: str | None,
    ) -> LicenseRecord:
        record = LicenseRecord(
            license_id=str(uuid4()),
            product_key_hash=_hash_key(canonical_key),
            product_key_redacted="ATK-*****-*****-*****-*****-*",
            entitlements=entitlements,
            machine_limit=machine_limit,
            expires_at=expires_at,
            status="active",
            created_at=_now(),
        )
        try:
            self._conn.execute(
                """
                INSERT INTO licenses (
                    license_id, product_key_hash, product_key_redacted,
                    entitlements_json, machine_limit, expires_at, status,
                    created_at, revoked_at, revoke_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.license_id,
                    record.product_key_hash,
                    record.product_key_redacted,
                    json.dumps(record.entitlements),
                    record.machine_limit,
                    record.expires_at,
                    record.status,
                    record.created_at,
                    record.revoked_at,
                    record.revoke_reason,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Product key already exists.") from exc
        return record

    def get_license(self, license_id: str) -> LicenseRecord | None:
        row = self._conn.execute(
            "SELECT * FROM licenses WHERE license_id = ?", (license_id,)
        ).fetchone()
        if row is None:
            return None
        return self._license_from_row(row)

    def list_licenses(self) -> list[LicenseRecord]:
        rows = self._conn.execute(
            "SELECT * FROM licenses ORDER BY created_at"
        ).fetchall()
        return [self._license_from_row(row) for row in rows]

    def get_license_by_key_hash(self, key_hash: str) -> LicenseRecord | None:
        row = self._conn.execute(
            "SELECT * FROM licenses WHERE product_key_hash = ?", (key_hash,)
        ).fetchone()
        return self._license_from_row(row) if row else None

    def revoke_license(self, license_id: str, reason: str) -> None:
        now = _now()
        self._conn.execute(
            "UPDATE licenses SET status = 'revoked', revoked_at = ?, revoke_reason = ? WHERE license_id = ?",
            (now, reason, license_id),
        )
        self._conn.execute(
            "UPDATE activations SET status = 'revoked' WHERE license_id = ?",
            (license_id,),
        )
        self._conn.commit()

    def count_active_activations(self, license_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM activations WHERE license_id = ? AND status = 'active'",
            (license_id,),
        ).fetchone()
        return int(row[0])

    def upsert_activation(
        self,
        license_id: str,
        device_id_hash: str,
        activation_token: str,
    ) -> ActivationRecord:
        now = _now()
        self._conn.execute(
            """
            INSERT INTO activations (
                license_id, device_id_hash, activation_token,
                activated_at, last_validated_at, status
            ) VALUES (?, ?, ?, ?, ?, 'active')
            ON CONFLICT(license_id, device_id_hash) DO UPDATE SET
                activation_token = excluded.activation_token,
                last_validated_at = excluded.last_validated_at,
                status = 'active'
            """,
            (license_id, device_id_hash, activation_token, now, now),
        )
        self._conn.commit()
        return ActivationRecord(
            license_id=license_id,
            device_id_hash=device_id_hash,
            activation_token=activation_token,
            activated_at=now,
            last_validated_at=now,
            status="active",
        )

    def touch_activation(self, license_id: str, device_id_hash: str) -> None:
        self._conn.execute(
            "UPDATE activations SET last_validated_at = ? WHERE license_id = ? AND device_id_hash = ?",
            (_now(), license_id, device_id_hash),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _license_from_row(self, row) -> LicenseRecord:
        return LicenseRecord(
            license_id=row[0],
            product_key_hash=row[1],
            product_key_redacted=row[2],
            entitlements=json.loads(row[3]),
            machine_limit=row[4],
            expires_at=row[5],
            status=row[6],
            created_at=row[7],
            revoked_at=row[8],
            revoke_reason=row[9],
        )
