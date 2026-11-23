"""Analyst resources (decision D-09): corridors, explanations and model card.

Read-only views over batch outputs of the active published run. They add
street-level precision and model transparency without running the network on
request (RG-02) and without prescribing interventions (RG-03).
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import Connection, bindparam, text

from raster_api.db import get_connection
from raster_api.v1 import repository as repo
from raster_api.v1.errors import ApiError
from raster_api.v1.router import UBIGEO, UnitTypeQ, _csv
from raster_api.v1.schemas import ErrorResponse, Meta
from raster_api.v1.service import Context

router = APIRouter(
    prefix="/api/v1", responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}
)
Conn = Annotated[Connection, Depends(get_connection)]


class Explanation(BaseModel):
    meta: Meta
    unit_id: str
    unit_type: str
    years: list[int]
    observing_family: list[str]
    expected_events: list[float]
    observed_events: list[float]
    attribution_year: int
    attribution_groups: list[str]
    attribution_pct: list[float]
    whatif_factors: list[float] | None
    whatif: dict[str, list[float]] | None
    saliency: list[tuple[str, float]] | None = None  # [unit_id, weight 0..1], strongest 40 cells


class ModelCard(BaseModel):
    meta: Meta
    card: dict[str, Any]
    benchmark: dict[str, Any]
    corridor_summary: dict[str, Any] | None


def _card(ctx: Context) -> dict[str, Any]:
    row = (
        ctx.conn.execute(text("SELECT * FROM model_card WHERE run_id = :r"), {"r": ctx.run_id})
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(404, "NO_MODEL_CARD", "The published run has no analyst layers yet.")
    return dict(row)


@router.get("/corridors", summary="Street corridors with recorded collisions (GeoJSON)")
def get_corridors(
    conn: Conn,
    district_ids: Annotated[str | None, Query(description="Comma-separated UBIGEO")] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 300,
    min_events: Annotated[float, Query(ge=0)] = 1,
) -> Response:
    ctx = Context(conn)
    districts = _csv(district_ids, "district_ids", UBIGEO)
    where = "AND c.district_id IN :d" if districts else ""
    q = text(
        f"""
        SELECT json_build_object('type', 'FeatureCollection', 'run_id', :r,
          'features', coalesce(json_agg(json_build_object(
            'type', 'Feature', 'id', c.corridor_id,
            'properties', json_build_object(
              'corridor_id', c.corridor_id, 'district_id', c.district_id,
              'district_name', d.name, 'street', c.street, 'length_km', c.length_km,
              'events', c.events, 'events_per_km', c.events_per_km, 'rank', c.rank,
              'cumulative_event_share', c.cumulative_event_share, 'injured', c.injured,
              'deceased', c.deceased, 'mean_risk_index', c.mean_risk_index,
              'by_family', c.by_family, 'by_year', c.by_year, 'by_subperiod', c.by_subperiod,
              'located_via', c.located_via),
            'geometry', ST_AsGeoJSON(c.geom, 6)::json) ORDER BY c.events DESC), '[]'::json))::text
        FROM (SELECT * FROM corridor c WHERE c.run_id = :r AND c.events >= :m {where}
              ORDER BY c.events DESC LIMIT :lim) c
        JOIN district d ON d.district_id = c.district_id
        """
    )
    params: dict[str, Any] = {"r": ctx.run_id, "m": min_events, "lim": limit}
    if districts:
        q = q.bindparams(bindparam("d", expanding=True))
        params["d"] = districts
    return Response(conn.execute(q, params).scalar_one(), media_type="application/geo+json")


@router.get(
    "/explanations",
    response_model=Explanation,
    summary="How the network estimates one unit: expected vs observed, drivers, what-if",
)
def get_explanation(conn: Conn, unit_id: str, unit_type: UnitTypeQ = "cell") -> Explanation:
    ctx = Context(conn)
    ctx.unit(unit_type, unit_id)
    card = _card(ctx)
    row = (
        conn.execute(
            text("""SELECT * FROM unit_explanation
                WHERE run_id = :r AND representation_id = :rep AND unit_id = :u"""),
            {"r": ctx.run_id, "rep": repo.REPRESENTATION[unit_type], "u": unit_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(
            404, "NO_EXPLANATION", "No explanation stored for this unit.", {"unit_id": unit_id}
        )
    return Explanation(
        meta=ctx.meta(),
        unit_id=unit_id,
        unit_type=unit_type,
        years=card["series_years"],
        observing_family=card["observing_family"],
        expected_events=row["expected_events"],
        observed_events=row["observed_events"],
        attribution_year=card["attribution_year"],
        attribution_groups=card["attribution_groups"],
        attribution_pct=row["attribution"],
        whatif_factors=card["whatif_factors"] if row["whatif"] else None,
        whatif=row["whatif"],
        saliency=row.get("saliency"),
    )


@router.get("/model", response_model=ModelCard, summary="Model card, training curves and benchmark")
def get_model(conn: Conn) -> ModelCard:
    ctx = Context(conn)
    card = _card(ctx)
    metrics = ctx.run["metrics"]
    metrics = json.loads(metrics) if isinstance(metrics, str) else metrics
    return ModelCard(
        meta=ctx.meta(),
        card=card["card"],
        benchmark=metrics,
        corridor_summary=card["corridor_summary"],
    )
