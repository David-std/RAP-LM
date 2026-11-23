# ruff: noqa: E501  (SQL fixture rows and query strings read best on one line)
"""Fixtures for API contract tests against a real PostGIS database.

Set ``RAPLM_TEST_ADMIN_URL`` to an owner connection of a PostGIS server
(``docker compose up -d db`` provides one at 127.0.0.1:5433). The fixture
recreates the ``raplm_test`` database, applies the Alembic migrations and
seeds a tiny **demo** run (``is_demo = true``): synthetic values used only to
verify the contract, never presented as model results. Tests needing the
database are skipped when the variable is not set.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[3]
ADMIN_URL = os.environ.get("RAPLM_TEST_ADMIN_URL")
TEST_DB = "raplm_test"

SQUARE = "ST_Multi(ST_MakeEnvelope({x0}, {y0}, {x1}, {y1}, 4326))"


def _url(base: str, db: str, user: str | None = None, password: str | None = None) -> str:
    from sqlalchemy.engine import make_url

    url = make_url(base).set(database=db, drivername="postgresql")
    if user:
        url = url.set(username=user, password=password)
    return url.render_as_string(hide_password=False)


SEED = f"""
INSERT INTO district VALUES
 ('150101', 'Lima', 4, {SQUARE.format(x0=-77.04, y0=-12.06, x1=-77.02, y1=-12.04)}),
 ('150131', 'San Isidro', 4, {SQUARE.format(x0=-77.04, y0=-12.10, x1=-77.02, y1=-12.08)});
INSERT INTO spatial_representation VALUES
 ('grid-1km', 'cell', 'demo grid', 1000, 'EPSG:32718', NULL, 'largest share'),
 ('district-43', 'district', 'districts', NULL, 'EPSG:32718', NULL, 'official');
INSERT INTO spatial_unit VALUES
 ('grid-1km', 'F1-C1', 'cell', 'Cell F1-C1', '150101', 1, 1, 1, {SQUARE.format(x0=-77.04, y0=-12.05, x1=-77.03, y1=-12.04)}),
 ('grid-1km', 'F1-C2', 'cell', 'Cell F1-C2', '150101', 1, 2, 1, {SQUARE.format(x0=-77.03, y0=-12.05, x1=-77.02, y1=-12.04)}),
 ('grid-1km', 'F5-C1', 'cell', 'Cell F5-C1', '150131', 5, 1, 1, {SQUARE.format(x0=-77.04, y0=-12.09, x1=-77.03, y1=-12.08)}),
 ('district-43', '150101', 'district', 'Lima', '150101', NULL, NULL, 4, {SQUARE.format(x0=-77.04, y0=-12.06, x1=-77.02, y1=-12.04)}),
 ('district-43', '150131', 'district', 'San Isidro', '150131', NULL, NULL, 4, {SQUARE.format(x0=-77.04, y0=-12.10, x1=-77.02, y1=-12.08)});
INSERT INTO analysis_period VALUES
 ('2023-wd-1824', 2023, 'weekday', 3, '2023-01-01', '2024-01-01', 18, 24, 'demo', '2023 weekday 18-24'),
 ('2024-wd-1824', 2024, 'weekday', 3, '2024-01-01', '2025-01-01', 18, 24, 'demo', '2024 weekday 18-24'),
 ('2024-we-0006', 2024, 'weekend', 0, '2024-01-01', '2025-01-01', 0, 6, 'demo', '2024 weekend 0-6');
INSERT INTO source_snapshot VALUES
 ('demo_source', 'Demo', 'Synthetic fixture', NULL, 'n/a', NULL, NULL, NULL, NULL, 'demo', 'demo', true, NULL),
 ('excluded_source', 'Demo', 'Excluded fixture', NULL, 'n/a', NULL, NULL, NULL, NULL, 'demo', 'demo', false, 'not comparable');
INSERT INTO variable VALUES
 ('v_occ', 'Occurrence', 'occurrence', 'events', 'demo_source', '2023', 'demo', true),
 ('v_exp', 'Pedestrian volume', 'exposure', 'p', NULL, 'n/a', 'not available', false);
INSERT INTO limitation VALUES ('L-demo', 'Demo', 'Synthetic data.');
INSERT INTO target_definition VALUES ('t-demo', 'All pedestrian collisions', 'demo', 'per km2 per year', 'percentile');
INSERT INTO threshold_set VALUES ('levels-v1', 'levels-v1', 40, 70, 'fixed', now());
INSERT INTO dataset_version VALUES ('demo-ds', '{{}}', 'x', now());
INSERT INTO model_run (run_id, status, is_demo, dataset_version_id, target_definition_id, threshold_set_id,
  model_family, code_commit_sha, seed, config, split, metrics, artifact_sha256, results_sha256, created_at, published_at)
VALUES ('demo-run', 'published', true, 'demo-ds', 't-demo', 'levels-v1', 'demo', 'abc', 1, '{{}}', '{{}}',
  '{{"selected_variant": "cnn_lstm", "selection_rule": "demo", "candidates": {{}}, "validation": [], "test": [], "reporting_factor": {{}}}}',
  'x', 'x', now(), now());
INSERT INTO run_source VALUES ('demo-run', 'demo_source');
INSERT INTO run_variable VALUES ('demo-run', 'v_occ');
INSERT INTO run_limitation VALUES ('demo-run', 'L-demo');
INSERT INTO run_period VALUES
 ('demo-run', '2023-wd-1824', 'train', '{{demo_source}}'),
 ('demo-run', '2024-wd-1824', 'test', '{{demo_source}}'),
 ('demo-run', '2024-we-0006', 'test', '{{demo_source}}');
INSERT INTO risk_result VALUES
 ('demo-run', 'grid-1km', 'F1-C1', '2023-wd-1824', 'estimated', 2.0, 80, 'high', 1.5, 3, 2, 0),
 ('demo-run', 'grid-1km', 'F1-C1', '2024-wd-1824', 'estimated', 1.0, 55, 'medium', 1.8, 1, 1, 0),
 ('demo-run', 'grid-1km', 'F1-C2', '2024-wd-1824', 'estimated', 0.2, 10, 'low', 0.1, 0, 0, 0),
 ('demo-run', 'grid-1km', 'F1-C1', '2024-we-0006', 'estimated', 0.5, 40, 'medium', NULL, 0, 0, 0),
 ('demo-run', 'district-43', '150101', '2024-wd-1824', 'estimated', 0.6, 75, 'high', 0.5, 4, 3, 1),
 ('demo-run', 'district-43', '150131', '2024-wd-1824', 'estimated', 0.1, 20, 'low', 0.1, 1, 1, 0);
-- F5-C1 has no row for any period: it must be served as no_result, never as zero.
UPDATE risk_result SET severity_value = 0.1, severity_index = 60, exposure_ratio = 1.8, exposure_index = 85,
  breakdown = '{{"severity": [1, 2, 0, 0], "type": [2, 1, 0, 0], "vehicle": [1, 0, 0.5, 0, 0, 0, 1.5, 0, 0], "service": [2, 1, 0, 0]}}'
  WHERE unit_id = 'F1-C1' AND period_id = '2024-wd-1824';
INSERT INTO publication_pointer VALUES ('active', 'demo-run', now());
INSERT INTO model_card VALUES ('demo-run', '{{"run_id": "demo-run", "variant": "cnn_lstm"}}', '[2023, 2024]',
  '["onsv", "onsv"]', 2024, '["population", "prior_collisions"]', '[0.5, 1.0, 2.0]', '["population"]',
  '{{"corridors": 1, "events_assigned": 3, "events_not_on_corridor": 0, "total_length_km": 1.0,
     "concentration": {{"10%_length": 1.0}}}}');
INSERT INTO unit_explanation VALUES
 ('demo-run', 'grid-1km', 'F1-C1', '[1.5, 1.0]', '[3, 1]', '[12.5, -4.0]', NULL, '[["F1-C1", 1.0], ["F1-C2", 0.4]]'),
 ('demo-run', 'district-43', '150101', '[2.0, 1.2]', '[4, 1]', '[10.0, 2.0]', '{{"population": [-20.0, 0.0, 15.0]}}', NULL);
INSERT INTO corridor VALUES ('demo-run', '150101:ABANCAY', '150101', 'Abancay', 1.0, 3, 3, 1, 1.0, 2, 0, 70,
  '{{"cenacom": 3}}', '{{"2016": 3}}', '[0,0,0,3,0,0,0,0]', '{{"street": 3}}',
  ST_Multi(ST_GeomFromText('LINESTRING(-77.035 -12.045, -77.03 -12.05)', 4326)));
INSERT INTO forecast VALUES
 ('demo-run', 'district-43', '150101', 2025, 'weekday', 3, 80, 'high', 72, 88, 75, 3.2),
 ('demo-run', 'district-43', '150131', 2025, 'weekday', 3, 30, 'low', 25, 36, 20, 0.8),
 ('demo-run', 'grid-1km', 'F1-C1', 2025, 'weekday', 3, 55, 'medium', 50, 61, 60, NULL);
"""


@pytest.fixture(scope="session")
def database() -> dict[str, str]:
    if not ADMIN_URL:
        pytest.skip("RAPLM_TEST_ADMIN_URL not set: PostGIS contract tests skipped")
    admin = _url(ADMIN_URL, "postgres")
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {TEST_DB}")
    owner = _url(ADMIN_URL, TEST_DB)
    env = dict(
        os.environ, RAPLM_MIGRATION_URL=owner.replace("postgresql://", "postgresql+psycopg://")
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ROOT / "database/alembic.ini"),
            "upgrade",
            "head",
        ],
        check=True,
        env=env,
        cwd=ROOT,
    )
    with psycopg.connect(owner, autocommit=True) as conn:
        conn.execute(SEED)
    reader_pw = os.environ.get("RAPLM_READER_PASSWORD", "raplm_reader_dev")
    return {
        "owner": owner,
        "reader": _url(ADMIN_URL, TEST_DB, "raplm_reader", reader_pw),
    }


@pytest.fixture(scope="session")
def client(database: dict[str, str]):
    from fastapi.testclient import TestClient
    from raster_api import db
    from raster_api.config import get_settings

    get_settings().database_url = database["reader"].replace(
        "postgresql://", "postgresql+psycopg://"
    )
    db.get_engine.cache_clear()
    from raster_api.main import app

    with TestClient(app) as c:
        yield c
