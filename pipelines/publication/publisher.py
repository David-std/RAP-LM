"""Atomic publication of a run into PostGIS (HT-11, RM-04; WBS 3.4.4).

Usage::

    python -m pipelines.publication.publisher \
        --dataset artifacts/datasets/fused-v1.0.0 \
        --run artifacts/runs/<run_id> \
        --catalog data/catalog/provenance.json

Connection: ``RAPLM_PUBLISHER_URL`` (raplm_publisher role).

Everything happens in **one transaction**:
1. reference data (districts, units, periods, catalog) is upserted;
2. the run is inserted as ``staged`` and its results are copied;
3. reconciliation checks compare the database with ``results.csv``
   (row count, per-representation sums, level/threshold coherence);
4. only then the run becomes ``published``, the previous one ``superseded``
   and the active pointer moves.
Any failure rolls back the whole transaction: the previously active run stays
visible and unchanged.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

REPRESENTATIONS = {
    "grid-1km": ("cell", "Regular 1 km grid (EPSG:32718) clipped to the 43 districts", 1000),
    "district-43": ("district", "43 districts of the province of Lima", None),
}


class ReconciliationError(RuntimeError):
    """Raised when the staged rows do not match the exported run."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _geom_sql(geojson: dict) -> str:
    return json.dumps(geojson, separators=(",", ":"))


# --------------------------------------------------------------------------- reference data
def upsert_reference(cur: psycopg.Cursor, dataset: Path, catalog: dict) -> None:
    districts = json.loads((dataset / "districts.geojson").read_text(encoding="utf-8"))
    grid = json.loads((dataset / "grid.geojson").read_text(encoding="utf-8"))
    names = {
        f["properties"]["ubigeo"]: f["properties"]["name"].title() for f in districts["features"]
    }

    for f in districts["features"]:
        p = f["properties"]
        cur.execute(
            """INSERT INTO district (district_id, name, area_km2, geom)
               VALUES (%s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))
               ON CONFLICT (district_id) DO NOTHING""",
            (p["ubigeo"], names[p["ubigeo"]], p["area_km2"], _geom_sql(f["geometry"])),
        )
    for rep_id, (unit_type, label, resolution) in REPRESENTATIONS.items():
        cur.execute(
            """INSERT INTO spatial_representation VALUES (%s, %s, %s, %s, 'EPSG:32718', %s, %s)
               ON CONFLICT (representation_id) DO NOTHING""",
            (
                rep_id,
                unit_type,
                label,
                resolution,
                Jsonb(grid["grid"]) if unit_type == "cell" else None,
                "Cell owner = district with the largest area share; event counts by "
                "point-in-polygon; district values aggregate cell intensities by area share."
                if unit_type == "cell"
                else "Official INEI polygons",
            ),
        )
    # Units are immutable per representation: insert only when missing.
    cur.execute("SELECT count(*) FROM spatial_unit WHERE representation_id = 'grid-1km'")
    if cur.fetchone()[0] == 0:
        for f in grid["features"]:
            p = f["properties"]
            cur.execute(
                """INSERT INTO spatial_unit VALUES
                   ('grid-1km', %s, 'cell', %s, %s, %s, %s, %s,
                    ST_Multi(ST_CollectionExtract(ST_MakeValid(
                        ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 3)))""",
                (
                    p["unit_id"],
                    f"Cell {p['unit_id']}",
                    p["district_ubigeo"],
                    p["row"],
                    p["col"],
                    p["area_km2"],
                    _geom_sql(f["geometry"]),
                ),
            )
            for district_id, share in p["district_fractions"].items():
                cur.execute(
                    "INSERT INTO unit_district_relation VALUES ('grid-1km', %s, %s, %s)",
                    (p["unit_id"], district_id, share),
                )
        for f in districts["features"]:
            p = f["properties"]
            cur.execute(
                """INSERT INTO spatial_unit
                   SELECT 'district-43', district_id, 'district', name, district_id,
                          NULL, NULL, area_km2, geom FROM district WHERE district_id = %s""",
                (p["ubigeo"],),
            )
            cur.execute(
                "INSERT INTO unit_district_relation VALUES ('district-43', %s, %s, 1.0)",
                (p["ubigeo"], p["ubigeo"]),
            )

    for s in catalog["sources"]:
        cur.execute(
            """INSERT INTO source_snapshot VALUES
               (%(source_id)s, %(publisher)s, %(name)s, %(url)s, %(licence)s, %(captured_at)s,
                NULL, %(coverage_start)s, %(coverage_end)s, %(spatial_coverage)s, %(population)s,
                %(incorporated)s, %(exclusion_reason)s)
               ON CONFLICT (source_id) DO NOTHING""",
            {"exclusion_reason": None} | s,
        )
    for v in catalog["variables"]:
        cur.execute(
            """INSERT INTO variable VALUES (%(variable_id)s, %(label)s, %(concept_group)s, %(unit)s,
               %(source_id)s, %(reference_period)s, %(description)s, %(incorporated)s)
               ON CONFLICT (variable_id) DO NOTHING""",
            v,
        )
    for lim in catalog["limitations"]:
        cur.execute(
            "INSERT INTO limitation VALUES (%(limitation_id)s, %(dimension)s, %(description)s) "
            "ON CONFLICT (limitation_id) DO NOTHING",
            lim,
        )
    td = catalog["target_definition"]
    cur.execute(
        """INSERT INTO target_definition VALUES (%(target_definition_id)s, %(population)s,
           %(definition)s, %(value_unit)s, %(index_method)s)
           ON CONFLICT (target_definition_id) DO NOTHING""",
        td,
    )


def upsert_periods(cur: psycopg.Cursor, periods_csv: Path) -> list[dict]:
    rows = list(csv.DictReader(periods_csv.open(encoding="utf-8")))
    for r in rows:
        cur.execute(
            """INSERT INTO analysis_period VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
               'year x day type x 6-hour band', %s) ON CONFLICT (period_id) DO NOTHING""",
            (
                r["period_id"],
                int(r["year"]),
                r["day_type"],
                int(r["time_band"]),
                r["start_date"],
                r["end_date"],
                int(r["start_hour"]),
                int(r["end_hour"]),
                r["label"],
            ),
        )
    return rows


# --------------------------------------------------------------------------- run
def stage_run(
    cur: psycopg.Cursor, dataset: Path, run: Path, catalog: dict, periods: list[dict]
) -> str:
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    export = json.loads((run / "export_manifest.json").read_text(encoding="utf-8"))
    dataset_manifest = json.loads((dataset / "dataset_manifest.json").read_text(encoding="utf-8"))
    cfg = manifest["config"]
    run_id = cfg["run_id"]
    th = cfg["thresholds"]

    if sha256(run / "results.csv") != export["results_sha256"]:
        raise ReconciliationError("results.csv does not match export_manifest.json")

    cur.execute(
        """INSERT INTO dataset_version VALUES (%s, %s, %s, now())
           ON CONFLICT (dataset_version_id) DO NOTHING""",
        (
            dataset_manifest["dataset_version"],
            Jsonb(dataset_manifest),
            sha256(dataset / "dataset_manifest.json"),
        ),
    )
    cur.execute(
        """INSERT INTO threshold_set VALUES (%s, %s, %s, %s, %s, now())
           ON CONFLICT (threshold_set_id) DO NOTHING""",
        (th["version"], th["version"], th["low_max"], th["medium_max"], th["method"]),
    )
    cur.execute("SELECT status FROM model_run WHERE run_id = %s", (run_id,))
    existing = cur.fetchone()
    if existing:
        raise ReconciliationError(
            f"run {run_id} already exists with status {existing[0]}; runs are immutable"
        )
    cur.execute(
        """INSERT INTO model_run (run_id, status, is_demo, dataset_version_id, target_definition_id,
               threshold_set_id, model_family, code_commit_sha, seed, config, split, metrics,
               artifact_sha256, results_sha256, created_at)
           VALUES (%s, 'staged', false, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())""",
        (
            run_id,
            dataset_manifest["dataset_version"],
            catalog["target_definition"]["target_definition_id"],
            th["version"],
            manifest["model_family"],
            manifest["code_commit_sha"][:40],
            cfg["seed"],
            Jsonb(cfg),
            Jsonb(cfg["split"]),
            Jsonb(metrics),
            manifest["weights_sha256"],
            export["results_sha256"],
        ),
    )
    for s in catalog["sources"]:
        if s["incorporated"]:
            cur.execute("INSERT INTO run_source VALUES (%s, %s)", (run_id, s["source_id"]))
    for v in catalog["variables"]:
        if v["incorporated"]:
            cur.execute("INSERT INTO run_variable VALUES (%s, %s)", (run_id, v["variable_id"]))
    for lim in catalog["limitations"]:
        cur.execute("INSERT INTO run_limitation VALUES (%s, %s)", (run_id, lim["limitation_id"]))
    for p in periods:
        cur.execute(
            "INSERT INTO run_period VALUES (%s, %s, %s, %s)",
            (run_id, p["period_id"], p["partition"], p["observing_sources"].split("|")),
        )

    # Bulk copy of results, prefixed with the run id.
    buffer = io.StringIO()
    with (run / "results.csv").open(encoding="utf-8") as handle:
        next(handle)
        for line in handle:
            buffer.write(f"{run_id},{line}")
    buffer.seek(0)
    with cur.copy(
        """COPY risk_result (run_id, representation_id, unit_id, period_id, availability,
               indicator_value, risk_index, risk_level, historical_average, observed_events,
               observed_injured, observed_deceased) FROM STDIN WITH (FORMAT csv, NULL '')"""
    ) as copy:
        while chunk := buffer.read(1 << 20):
            copy.write(chunk)
    return run_id


def reconcile(cur: psycopg.Cursor, run: Path, run_id: str) -> dict:
    """Compare staged rows with results.csv; raise on any mismatch."""
    expected: dict[str, list[float]] = {}
    with (run / "results.csv").open(encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            agg = expected.setdefault(r["representation_id"], [0, 0.0, 0.0])
            agg[0] += 1
            agg[1] += float(r["indicator_value"] or 0)
            agg[2] += float(r["observed_events"] or 0)
    cur.execute(
        """SELECT representation_id, count(*), sum(indicator_value), sum(observed_events)
           FROM risk_result WHERE run_id = %s GROUP BY representation_id""",
        (run_id,),
    )
    actual = {rep: (n, float(v or 0), float(o or 0)) for rep, n, v, o in cur.fetchall()}
    report = {}
    for rep, (n, v, o) in expected.items():
        got = actual.get(rep)
        if (
            got is None
            or got[0] != n
            or abs(got[1] - v) > 1e-6 * max(1, abs(v))
            or abs(got[2] - o) > 1e-6 * max(1, abs(o))
        ):
            raise ReconciliationError(f"{rep}: expected {(n, v, o)}, staged {got}")
        report[rep] = {"rows": n, "indicator_sum": v, "observed_sum": o}

    cur.execute(
        """SELECT count(*) FROM risk_result r JOIN model_run m USING (run_id)
           JOIN threshold_set t USING (threshold_set_id)
           WHERE r.run_id = %s AND r.risk_level <> CASE
               WHEN r.risk_index < t.low_max THEN 'low'
               WHEN r.risk_index < t.medium_max THEN 'medium' ELSE 'high' END""",
        (run_id,),
    )
    if (bad := cur.fetchone()[0]) != 0:
        raise ReconciliationError(f"{bad} rows have a level inconsistent with the thresholds")
    cur.execute(
        """SELECT u.representation_id,
                  count(*) * (SELECT count(*) FROM run_period WHERE run_id = %s)
           FROM spatial_unit u GROUP BY 1""",
        (run_id,),
    )
    for rep, expected_rows in cur.fetchall():
        if report.get(rep, {}).get("rows") != expected_rows:
            raise ReconciliationError(f"{rep}: not every unit x period has a row")
    return report


def activate(cur: psycopg.Cursor, run_id: str, report: dict) -> None:
    now = datetime.now(UTC)
    cur.execute(
        "UPDATE model_run SET status = 'superseded' WHERE status = 'published' AND run_id <> %s",
        (run_id,),
    )
    cur.execute(
        "UPDATE model_run SET status = 'published', published_at = %s WHERE run_id = %s",
        (now, run_id),
    )
    cur.execute(
        """INSERT INTO publication_pointer VALUES ('active', %s, %s)
           ON CONFLICT (pointer_key) DO UPDATE SET run_id = EXCLUDED.run_id,
               activated_at = EXCLUDED.activated_at""",
        (run_id, now),
    )
    cur.execute(
        "INSERT INTO publication_log (run_id, action, detail) VALUES (%s, 'published', %s)",
        (run_id, Jsonb(report)),
    )


def publish(url: str, dataset: Path, run: Path, catalog_path: Path) -> dict:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    with psycopg.connect(url) as conn:  # one transaction; commit only on success
        with conn.cursor() as cur:
            upsert_reference(cur, dataset, catalog)
            periods = upsert_periods(cur, run / "periods.csv")
            run_id = stage_run(cur, dataset, run, catalog, periods)
            report = reconcile(cur, run, run_id)
            activate(cur, run_id, report)
    return {"run_id": run_id, "reconciliation": report}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog/provenance.json"))
    args = parser.parse_args()
    url = os.environ.get("RAPLM_PUBLISHER_URL")
    if not url:
        raise SystemExit("Set RAPLM_PUBLISHER_URL (raplm_publisher role)")
    url = url.replace("postgresql+psycopg://", "postgresql://")
    print(json.dumps(publish(url, args.dataset, args.run, args.catalog), indent=2))


if __name__ == "__main__":
    main()
