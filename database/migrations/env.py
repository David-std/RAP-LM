"""Alembic environment. The migration role URL comes from RAPLM_MIGRATION_URL."""

import os

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config


def database_url() -> str:
    url = os.environ.get("RAPLM_MIGRATION_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("Set RAPLM_MIGRATION_URL to the migration role connection URL")
    return url


def run_migrations_offline() -> None:
    context.configure(url=database_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
