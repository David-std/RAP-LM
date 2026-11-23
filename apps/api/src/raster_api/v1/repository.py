"""Parameterised read queries against published results (Figure 5D repository).

No function here writes, trains or runs inference. Every result query is
scoped to the ``run_id`` resolved once per request by the service layer.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, bindparam, text

REPRESENTATION = {"cell": "grid-1km", "district": "district-43"}

_UNIT_COLUMNS = """
    u.unit_id, u.unit_type, u.display_name, u.district_id, d.name AS district_name, u.area_km2
"""


def active_run(conn: Connection) -> dict[str, Any] | None:
    row = (
        conn.execute(
            text(
                """
            SELECT r.run_id, r.is_demo, r.model_family, r.dataset_version_id,
                   r.target_definition_id, r.threshold_set_id, r.published_at, r.config,
                   r.split, r.metrics, r.code_commit_sha, r.seed, r.artifact_sha256,
                   r.results_sha256, t.population, t.value_unit, t.definition, t.index_method,
                   th.version AS th_version, th.low_max, th.medium_max, th.method AS th_method
            FROM publication_pointer p
            JOIN model_run r ON r.run_id = p.run_id AND r.status = 'published'
            JOIN target_definition t USING (target_definition_id)
            JOIN threshold_set th USING (threshold_set_id)
            WHERE p.pointer_key = 'active'
            """
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def periods(conn: Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT p.*, rp.partition, rp.observing_sources
            FROM run_period rp JOIN analysis_period p USING (period_id)
            WHERE rp.run_id = :run_id
            ORDER BY p.year, p.day_type, p.time_band
            """
        ),
        {"run_id": run_id},
    ).mappings()
    return [dict(r) for r in rows]


def units_geojson(conn: Connection, unit_type: str, district_ids: list[str] | None) -> str:
    query = text(
        f"""
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', coalesce(json_agg(json_build_object(
                'type', 'Feature',
                'id', u.unit_id,
                'properties', json_build_object(
                    'unit_id', u.unit_id, 'unit_type', u.unit_type,
                    'display_name', u.display_name, 'district_id', u.district_id,
                    'district_name', d.name, 'area_km2', round(u.area_km2::numeric, 4),
                    'row', u.grid_row, 'col', u.grid_col),
                'geometry', ST_AsGeoJSON(u.geom, 6)::json
            ) ORDER BY u.unit_id), '[]'::json)
        )::text
        FROM spatial_unit u JOIN district d ON d.district_id = u.district_id
        WHERE u.representation_id = :rep
          {"AND u.district_id IN :districts" if district_ids else ""}
        """
    )
    params: dict[str, Any] = {"rep": REPRESENTATION[unit_type]}
    if district_ids:
        query = query.bindparams(bindparam("districts", expanding=True))
        params["districts"] = district_ids
    return conn.execute(query, params).scalar_one()


def unit_exists(conn: Connection, unit_type: str, unit_id: str) -> dict[str, Any] | None:
    row = (
        conn.execute(
            text(
                f"""SELECT {_UNIT_COLUMNS}
                FROM spatial_unit u JOIN district d ON d.district_id = u.district_id
                WHERE u.representation_id = :rep AND u.unit_id = :unit_id"""
            ),
            {"rep": REPRESENTATION[unit_type], "unit_id": unit_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def unit_types_of(conn: Connection, unit_ids: list[str]) -> dict[str, set[str]]:
    rows = conn.execute(
        text("SELECT unit_id, unit_type FROM spatial_unit WHERE unit_id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        ),
        {"ids": unit_ids},
    )
    out: dict[str, set[str]] = {}
    for unit_id, unit_type in rows:
        out.setdefault(unit_id, set()).add(unit_type)
    return out


def results(
    conn: Connection,
    run_id: str,
    unit_type: str,
    period_ids: list[str],
    unit_ids: list[str] | None = None,
    district_ids: list[str] | None = None,
    levels: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Results of the pinned run. Units without a stored row appear as ``no_result``."""
    filters = []
    params: dict[str, Any] = {
        "run_id": run_id,
        "rep": REPRESENTATION[unit_type],
        "periods": period_ids,
    }
    binds = [bindparam("periods", expanding=True)]
    if unit_ids:
        filters.append("u.unit_id IN :units")
        params["units"] = unit_ids
        binds.append(bindparam("units", expanding=True))
    if district_ids:
        filters.append("u.district_id IN :districts")
        params["districts"] = district_ids
        binds.append(bindparam("districts", expanding=True))
    where = " AND ".join(filters) if filters else "TRUE"
    query = text(
        f"""
        SELECT {_UNIT_COLUMNS}, p.period_id,
               coalesce(r.availability, 'no_result') AS availability,
               r.indicator_value, r.risk_index, r.risk_level, r.historical_average,
               r.observed_events, r.observed_injured, r.observed_deceased,
               r.severity_value, r.severity_index, r.exposure_ratio, r.exposure_index,
               r.breakdown
        FROM spatial_unit u
        JOIN district d ON d.district_id = u.district_id
        CROSS JOIN analysis_period p
        LEFT JOIN risk_result r
               ON r.run_id = :run_id AND r.representation_id = u.representation_id
              AND r.unit_id = u.unit_id AND r.period_id = p.period_id
        WHERE u.representation_id = :rep AND p.period_id IN :periods AND {where}
        ORDER BY p.year, p.day_type, p.time_band, u.unit_id
        """
    ).bindparams(*binds)
    rows = [dict(r) for r in conn.execute(query, params).mappings()]
    if levels:
        rows = [r for r in rows if r["risk_level"] in levels]
    return rows


def provenance(conn: Connection, run_id: str) -> dict[str, Any]:
    sources = conn.execute(
        text(
            """SELECT s.* FROM source_snapshot s
               WHERE s.source_id IN (SELECT source_id FROM run_source WHERE run_id = :r)
                  OR NOT s.incorporated
               ORDER BY s.incorporated DESC, s.source_id"""
        ),
        {"r": run_id},
    ).mappings()
    variables = conn.execute(
        text(
            """SELECT v.*, (rv.run_id IS NOT NULL) AS used FROM variable v
               LEFT JOIN run_variable rv ON rv.variable_id = v.variable_id AND rv.run_id = :r
               ORDER BY v.concept_group, v.variable_id"""
        ),
        {"r": run_id},
    ).mappings()
    limitations = conn.execute(
        text(
            """SELECT l.* FROM limitation l JOIN run_limitation rl USING (limitation_id)
               WHERE rl.run_id = :r ORDER BY l.limitation_id"""
        ),
        {"r": run_id},
    ).mappings()
    return {
        "sources": [dict(s) for s in sources],
        "variables": [dict(v) for v in variables],
        "limitations": [dict(x) for x in limitations],
    }


def series(
    conn: Connection,
    run_id: str,
    unit_type: str,
    day_type: str,
    time_band: int,
    district_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Risk index per unit for every published year of one day type and band.

    Compact rows (unit, year, index, level) used by analyst views such as
    persistence of high-risk units. Units without a stored row are omitted
    here; the service fills them as null for each published year.
    """
    district_filter = "AND u.district_id IN :districts" if district_ids else ""
    query = text(
        f"""
        SELECT u.unit_id, u.display_name, u.district_id, p.year,
               r.risk_index, r.risk_level, r.indicator_value, r.observed_events
        FROM run_period rp
        JOIN analysis_period p USING (period_id)
        JOIN risk_result r ON r.run_id = rp.run_id AND r.period_id = p.period_id
        JOIN spatial_unit u ON u.representation_id = r.representation_id AND u.unit_id = r.unit_id
        WHERE rp.run_id = :run_id AND r.representation_id = :rep
          AND p.day_type = :day_type AND p.time_band = :band {district_filter}
        ORDER BY u.unit_id, p.year
        """
    )
    params: dict[str, Any] = {
        "run_id": run_id,
        "rep": REPRESENTATION[unit_type],
        "day_type": day_type,
        "band": time_band,
    }
    if district_ids:
        query = query.bindparams(bindparam("districts", expanding=True))
        params["districts"] = district_ids
    return [dict(r) for r in conn.execute(query, params).mappings()]
