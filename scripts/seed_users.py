"""Seed four demo users for the local stack.

Idempotent: re-running upserts rather than duplicating rows. Passwords are
hashed with bcrypt. The plaintexts below are intentionally weak — this script
is for the local demo and the soutenance Loom, not for any deployed env.

Usage:
    python scripts/seed_users.py

Prereq: scripts/users_migration.sql has been applied (see Makefile target).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2

# Make `api/` importable so we reuse the same bcrypt helper the runtime uses.
# The sys.path tweak has to happen before the services.auth import, which is
# why that one has a lint waiver. psycopg2 is fine at the top.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from services.auth import hash_password  # noqa: E402

DEMO_USERS = [
    ("admin@pfa.local", "admin123", "Admin Demo", "admin"),
    ("ops@pfa.local", "ops123", "Ops Lead", "ops"),
    ("analyst@pfa.local", "analyst123", "Data Analyst", "analyst"),
    ("viewer@pfa.local", "viewer123", "Read-only Viewer", "viewer"),
]


def main() -> int:
    dsn = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", 5432)),
        "dbname": os.getenv("POSTGRES_DB", "pfa_olist"),
        "user": os.getenv("POSTGRES_USER", "pfa"),
        "password": os.getenv("POSTGRES_PASSWORD", "pfa_local_2026"),
    }
    conn = psycopg2.connect(**dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                for email, password, display_name, role in DEMO_USERS:
                    cur.execute(
                        """
                        INSERT INTO governance.users (email, password_hash, display_name, role)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (email) DO UPDATE SET
                            password_hash = EXCLUDED.password_hash,
                            display_name  = EXCLUDED.display_name,
                            role          = EXCLUDED.role
                        """,
                        (email, hash_password(password), display_name, role),
                    )
                    print(f"  upserted {email} / {role}")
    finally:
        conn.close()
    print("[seed_users] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
