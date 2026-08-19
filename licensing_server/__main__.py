"""Licensing server entry point: ``python -m licensing_server``."""

from __future__ import annotations

from .admin_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
