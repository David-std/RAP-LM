"""Prepare a managed PostgreSQL (cloud demo, render.yaml) with the published run.

Usage::

    RAPLM_REMOTE_OWNER_URL="postgresql://raplm_owner:<password>@<host>/raplm" \\
        python -m tools.deploy.remote_setup \\
        --dataset artifacts/datasets/fused-v1.3.0 --run artifacts/runs/<run_id>

Steps, all idempotent except the publication of a run (runs are immutable):

1. Create the separated roles ``raplm_reader`` (read-only) and ``raplm_publisher`` with
   random passwords when they do not exist (same privileges as database/init/01_roles.sh).
2. Apply the Alembic migrations with the owner role.
3. Publish the run atomically and its analyst layers with the publisher role.
4. Print the read-only URL to set as ``DATABASE_URL`` of the API service.

Passwords are printed once and never written to disk or to the repository. External
connections to managed databases require TLS (``sslmode=require``).
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]


def with_tls(url: str) -> str:
    return url if "sslmode=" in url else url + ("&" if "?" in url else "?") + "sslmode=require"


def role_url(owner_url: str, role: str, password: str) -> str:
    parts = urlsplit(owner_url)
    host = parts.hostname + (f":{parts.port}" if parts.port else "")
    return urlunsplit(
        (parts.scheme, f"{role}:{quote(password)}@{host}", parts.path, parts.query, "")
    )


def ensure_roles(owner_url: str) -> dict[str, str]:
    """Create the two roles if missing; return the new passwords (empty if they existed)."""
    created: dict[str, str] = {}
    with psycopg.connect(owner_url, autocommit=True) as conn:
        for role in ("raplm_reader", "raplm_publisher"):
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            if exists:
                continue
            password = secrets.token_urlsafe(24)
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            created[role] = password
        conn.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO raplm_reader"
        )
        conn.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO raplm_publisher"
        )
        conn.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO raplm_publisher"
        )
        conn.execute("ALTER ROLE raplm_reader SET default_transaction_read_only = on")
    return created


def run(module: str, *args: str, env: dict[str, str]) -> None:
    subprocess.run([sys.executable, "-m", module, *args], cwd=ROOT, env=env, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--publisher-password", help="existing raplm_publisher password (reruns)")
    args = ap.parse_args()
    owner = os.environ.get("RAPLM_REMOTE_OWNER_URL")
    if not owner:
        raise SystemExit("Set RAPLM_REMOTE_OWNER_URL to the external URL of the managed database")
    owner = with_tls(owner)

    created = ensure_roles(owner)
    publisher_password = created.get("raplm_publisher") or args.publisher_password
    if not publisher_password:
        raise SystemExit("raplm_publisher already exists: pass --publisher-password")

    env = dict(os.environ)
    env["RAPLM_MIGRATION_URL"] = "postgresql+psycopg://" + owner.split("://", 1)[1]
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "database/alembic.ini", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    env["RAPLM_PUBLISHER_URL"] = role_url(owner, "raplm_publisher", publisher_password)
    run(
        "pipelines.publication.publisher",
        "--dataset",
        str(args.dataset),
        "--run",
        str(args.run),
        env=env,
    )
    run(
        "pipelines.publication.extras",
        "--dataset",
        str(args.dataset),
        "--run",
        str(args.run),
        env=env,
    )

    print("\nDone. Store these secrets outside the repository:")
    for role, password in created.items():
        print(f"  {role} password: {password}")
    if "raplm_reader" in created:
        reader = role_url(owner, "raplm_reader", created["raplm_reader"])
        print(f"\nSet DATABASE_URL of raplm-api to:\n  {reader}")


if __name__ == "__main__":
    main()
