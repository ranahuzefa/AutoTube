"""Admin CLI for the licensing server."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .constants import PUBLIC_KEY_FILE
from .database import LicenseDatabase
from .generation import format_key, generate_canonical_key
from .issuance import issue_activation, validate_activation
from .keypair import (
    ensure_keypair,
    init_keypair,
    load_public_key,
    public_key_fingerprint,
)


def _iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _cmd_init_keypair(_args) -> int:
    private_path, public_path, fingerprint = init_keypair()
    print(f"Private key: {private_path}")
    print(f"Public key:  {public_path}")
    print(f"Public key fingerprint: {fingerprint}")
    return 0


def _cmd_generate_key(args) -> int:
    canonical = generate_canonical_key()
    expires_at = _iso(args.expires_days) if args.expires_days else None
    record = LicenseDatabase().create_license(
        canonical_key=canonical,
        entitlements=args.entitlements or ["render"],
        machine_limit=args.machine_limit,
        expires_at=expires_at,
    )
    print("WARNING: store this product key securely. It is shown only once.")
    print(format_key(canonical))
    print(f"License ID: {record.license_id}")
    return 0


def _cmd_list_keys(_args) -> int:
    records = LicenseDatabase().list_licenses()
    if not records:
        print("No licenses.")
        return 0
    for record in records:
        print(
            f"{record.license_id}\t{record.product_key_redacted}\t"
            f"{record.status}\t{record.machine_limit}\t{record.expires_at or '-'}"
        )
    return 0


def _cmd_revoke_key(args) -> int:
    db = LicenseDatabase()
    if db.get_license(args.license_id) is None:
        print("Unknown license id.", file=sys.stderr)
        return 1
    db.revoke_license(args.license_id, args.reason)
    print(f"Revoked {args.license_id}")
    return 0


def _cmd_issue_token(args) -> int:
    db = LicenseDatabase()
    canonical = args.product_key.replace("-", "").upper()
    from .database import _hash_key

    record = db.get_license_by_key_hash(_hash_key(canonical))
    if record is None:
        print("Unknown product key.", file=sys.stderr)
        return 1

    private_key, _ = ensure_keypair()
    result = issue_activation(
        db,
        license_id=record.license_id,
        device_id_hash=args.device_id_hash,
        private_key=private_key,
    )
    print(result["activation_token"])
    return 0


def _cmd_validate_token(args) -> int:
    db = LicenseDatabase()
    _, public_key = ensure_keypair()
    result = validate_activation(
        db,
        license_id=args.license_id,
        device_id_hash=args.device_id_hash,
        activation_token=args.activation_token,
        public_key=public_key,
    )
    print(result["status"])
    return 0


def _cmd_export_public_key(args) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(PUBLIC_KEY_FILE.read_bytes())
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="licensing_server")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-keypair").set_defaults(func=_cmd_init_keypair)

    gen = sub.add_parser("generate-key")
    gen.add_argument("--entitlements", nargs="*")
    gen.add_argument("--machine-limit", type=int, default=1)
    gen.add_argument("--expires-days", type=int, default=None)
    gen.set_defaults(func=_cmd_generate_key)

    sub.add_parser("list-keys").set_defaults(func=_cmd_list_keys)

    rev = sub.add_parser("revoke-key")
    rev.add_argument("--license-id", required=True)
    rev.add_argument("--reason", default="Revoked by admin")
    rev.set_defaults(func=_cmd_revoke_key)

    issue = sub.add_parser("issue-token")
    issue.add_argument("--product-key", required=True)
    issue.add_argument("--device-id-hash", required=True)
    issue.set_defaults(func=_cmd_issue_token)

    validate = sub.add_parser("validate-token")
    validate.add_argument("--license-id", required=True)
    validate.add_argument("--device-id-hash", required=True)
    validate.add_argument("--activation-token", required=True)
    validate.set_defaults(func=_cmd_validate_token)

    export = sub.add_parser("export-public-key")
    export.add_argument("--out", required=True)
    export.set_defaults(func=_cmd_export_public_key)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - CLI boundary, no secrets in message
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
