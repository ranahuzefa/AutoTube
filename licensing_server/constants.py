"""Server-side licensing constants and storage paths."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_ROOT / "data"
KEYS_DIR = PACKAGE_ROOT / "keys"

PRIVATE_KEY_FILE = KEYS_DIR / "signing.key"
PUBLIC_KEY_FILE = KEYS_DIR / "public.pem"
DATABASE_FILE = DATA_DIR / "licenses.db"

PRODUCT_KEY_PAYLOAD_LENGTH = 20
PRODUCT_KEY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PRODUCT_KEY_PREFIX = "ATK"

DEFAULT_MACHINE_LIMIT = 1
DEFAULT_GRACE_DAYS = 7
