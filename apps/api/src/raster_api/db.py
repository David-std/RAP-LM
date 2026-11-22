"""Database access for the read-only API (Figure 5D: repository layer).

Every query is parameterised. The connection uses the ``raplm_reader`` role,
whose sessions default to read-only transactions.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Connection, Engine, create_engine

from raster_api.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)


def get_connection() -> Iterator[Connection]:
    with get_engine().connect() as connection:
        yield connection
