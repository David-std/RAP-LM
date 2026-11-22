# ruff: noqa: E501  (SQL fixture rows and query strings read best on one line)
"""Contract tests of the read API v1 (HT-09, RT-02; RF-01..RF-08; M-02, M-03, M-08).

Each test states the requirement or story it verifies. Data is the demo
fixture of conftest.py (``is_demo = true``).
"""

from __future__ import annotations

import psycopg
import pytest

pytestmark = pytest.mark.usefixtures("database")

REQUIRED_CONTEXT = {"unit", "period", "run_id", "risk_index", "risk_level", "availability"}


def test_periods_listed_chronologically_with_bounds(client):  # RF-03, HU-10
    body = client.get("/api/v1/periods").json()
    ids = [p["period_id"] for p in body["data"]]
    assert ids == ["2023-wd-1824", "2024-wd-1824", "2024-we-0006"]
    first = body["data"][0]
    assert first["start_date"] == "2023-01-01" and first["end_date"] == "2024-01-01"
    assert body["meta"]["run"]["is_demo"] is True
    assert "DEMO" in body["meta"]["scope_notice"]


def test_units_are_geojson_inside_scope(client):  # RF-01, RG-01, HU-04
    r = client.get("/api/v1/units", params={"unit_type": "cell"})
    assert r.headers["content-type"].startswith("application/geo+json")
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert {f["properties"]["district_id"] for f in fc["features"]} <= {"150101", "150131"}
    assert all(f["geometry"]["type"] == "MultiPolygon" for f in fc["features"])


def test_risk_every_result_has_full_context(client):  # RF-07, HU-22, M-02
    body = client.get("/api/v1/risk", params={"period_id": "2024-wd-1824"}).json()
    assert len(body["data"]) == 3
    for item in body["data"]:
        assert REQUIRED_CONTEXT <= item.keys()
        assert item["period"]["period_id"] == "2024-wd-1824"
        assert item["run_id"] == "demo-run"
    assert body["meta"]["legend"]["bands"][2] == {
        "level": "high",
        "min_index": 70.0,
        "max_index": 100.0,
        "label": "Alto",
    }


def test_missing_result_is_explicit_not_zero(client):  # HU-21, RF-07
    body = client.get(
        "/api/v1/risk", params={"period_id": "2024-wd-1824", "unit_id": "F5-C1"}
    ).json()
    item = body["data"][0]
    assert item["availability"] == "no_result"
    assert (
        item["indicator_value"] is None
        and item["risk_level"] is None
        and item["risk_index"] is None
    )
    assert body["counts"]["no_result"] == 1


def test_level_and_district_filters(client):  # RF-04, HU-13..HU-15
    by_level = client.get(
        "/api/v1/risk", params={"period_id": "2024-wd-1824", "levels": "low"}
    ).json()
    assert [r["unit"]["unit_id"] for r in by_level["data"]] == ["F1-C2"]
    by_district = client.get(
        "/api/v1/risk", params={"period_id": "2024-wd-1824", "district_ids": "150131"}
    ).json()
    assert [r["unit"]["unit_id"] for r in by_district["data"]] == ["F5-C1"]
    combined = client.get(
        "/api/v1/risk",
        params={"period_id": "2024-wd-1824", "district_ids": "150101", "levels": "high,medium"},
    ).json()
    assert [r["unit"]["unit_id"] for r in combined["data"]] == ["F1-C1"]


def test_removing_filters_restores_full_set(client):  # HU-16
    full = client.get("/api/v1/risk", params={"period_id": "2024-wd-1824"}).json()
    assert {r["unit"]["unit_id"] for r in full["data"]} == {"F1-C1", "F1-C2", "F5-C1"}


def test_unknown_period_never_substituted(
    client,
):  # RT-02, criterion "never returns another period"
    r = client.get("/api/v1/risk", params={"period_id": "2019-wd-1824"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "UNKNOWN_PERIOD"


@pytest.mark.parametrize(
    "params",
    [
        {},  # missing period
        {"period_id": "bad id!"},
        {"period_id": "2024-wd-1824", "unit_type": "hexagon"},
        {"period_id": "2024-wd-1824", "levels": "extreme"},
        {"period_id": "2024-wd-1824", "district_ids": "070101"},  # Callao: outside scope
    ],
)
def test_invalid_queries_return_contract_error(client, params):  # RT-02, RG-01
    r = client.get("/api/v1/risk", params=params)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_PARAMETERS"


def test_spatial_comparison_same_period(client):  # RF-05, HU-17, HU-18
    body = client.get(
        "/api/v1/comparisons",
        params={"mode": "spatial", "unit_ids": "F1-C1,F1-C2", "period_id": "2024-wd-1824"},
    ).json()
    assert body["comparable"] is True
    assert [i["result"]["period"]["period_id"] for i in body["items"]] == ["2024-wd-1824"] * 2
    assert body["items"][1]["index_difference"] == -45.0


def test_spatial_comparison_flags_units_without_result(client):  # HU-21
    body = client.get(
        "/api/v1/comparisons",
        params={"mode": "spatial", "unit_ids": "F1-C1,F5-C1", "period_id": "2024-wd-1824"},
    ).json()
    assert body["comparable"] is False
    assert "F5-C1" in body["reason"]
    assert body["items"][1]["index_difference"] is None


def test_comparison_across_representations_is_rejected(client):  # HU-18
    r = client.get(
        "/api/v1/comparisons",
        params={"mode": "spatial", "unit_ids": "F1-C1,150101", "period_id": "2024-wd-1824"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INCOMPATIBLE_COMPARISON"


def test_temporal_comparison_keeps_unit_fixed(client):  # RF-06, HU-20
    body = client.get(
        "/api/v1/comparisons",
        params={"mode": "temporal", "unit_id": "F1-C1", "period_ids": "2023-wd-1824,2024-wd-1824"},
    ).json()
    assert {i["result"]["unit"]["unit_id"] for i in body["items"]} == {"F1-C1"}
    assert body["items"][1]["index_difference"] == -25.0


@pytest.mark.parametrize(
    "params",
    [
        {"mode": "spatial", "unit_ids": "F1-C1", "period_id": "2024-wd-1824"},
        {"mode": "spatial", "unit_ids": "F1-C1,F1-C1", "period_id": "2024-wd-1824"},
        {"mode": "temporal", "unit_id": "F1-C1", "period_ids": "2024-wd-1824", "unit_ids": "F1-C2"},
        {"mode": "other"},
    ],
)
def test_ambiguous_comparisons_rejected(client, params):  # RT-02
    assert client.get("/api/v1/comparisons", params=params).status_code == 422


def test_provenance_from_a_result(client):  # RF-08, HU-24..HU-26, M-03
    body = client.get(
        "/api/v1/provenance", params={"unit_id": "F1-C1", "period_id": "2024-wd-1824"}
    ).json()
    assert body["run"]["run_id"] == "demo-run"
    assert body["meta"]["run"]["dataset_version_id"] == "demo-ds"
    assert any(s["source_id"] == "demo_source" and s["incorporated"] for s in body["sources"])
    assert any(not s["incorporated"] and s["exclusion_reason"] for s in body["sources"])
    assert set(body["variables_by_group"]) == {"occurrence", "severity", "exposure", "context"}
    assert body["variables_by_group"]["exposure"][0]["incorporated"] is False
    assert body["limitations"][0]["limitation_id"] == "L-demo"
    assert body["result_context"]["observing_sources"] == ["demo_source"]


def test_api_role_cannot_write(database):  # RT-03, persistence contract §7
    with psycopg.connect(database["reader"]) as conn, pytest.raises(psycopg.errors.Error):
        conn.execute("DELETE FROM risk_result")


def test_only_published_runs_can_be_active(database):  # atomic publication invariant
    with psycopg.connect(database["owner"]) as conn:
        conn.execute(
            """INSERT INTO model_run (run_id, status, is_demo, dataset_version_id, target_definition_id,
                 threshold_set_id, model_family, code_commit_sha, seed, config, split, metrics,
                 artifact_sha256, results_sha256, created_at)
               VALUES ('staged-run', 'staged', true, 'demo-ds', 't-demo', 'levels-v1', 'demo', 'abc', 1,
                       '{}', '{}', '{}', 'x', 'x', now())"""
        )
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE publication_pointer SET run_id = 'staged-run'")
        conn.rollback()


def test_health(client):
    body = client.get("/health").json()
    assert body == {"status": "ok", "database": "ok", "environment": body["environment"]}


def test_no_write_routes(client):  # RG-02: read-only service
    for route in client.app.routes:
        methods = getattr(route, "methods", set()) or set()
        assert methods <= {"GET", "HEAD"}, route.path


def test_series_aligns_years_and_keeps_nulls(client):  # analyst views, D-06
    body = client.get(
        "/api/v1/series", params={"unit_type": "cell", "day_type": "weekday", "time_band": 3}
    ).json()
    assert body["years"] == [2023, 2024]
    by_id = {u["unit_id"]: u for u in body["units"]}
    assert by_id["F1-C1"]["risk_index"] == [80.0, 55.0]
    assert by_id["F1-C2"]["risk_index"] == [None, 10.0]  # missing year stays null, not 0
    assert (
        client.get("/api/v1/series", params={"day_type": "weekday", "time_band": 9}).status_code
        == 422
    )


def test_temporal_comparison_accepts_all_published_years(client):  # RF-06, defect I-08
    from raster_api.config import get_settings

    assert get_settings().max_compare_periods >= 11  # 2011-2017 + 2021-2024
