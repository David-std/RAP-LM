"""Five read-only resources of the API (Figure 5D, RT-02, HT-09).

English resource names (decision D-02 in docs/architecture/registro-de-decisiones.md) map to
the report's names: /periods = /periodos, /units = /unidades, /risk = /riesgo,
/comparisons = /comparaciones, /provenance = /procedencia.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from threading import Lock
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import Connection

from raster_api.config import get_settings
from raster_api.db import get_connection
from raster_api.v1 import repository as repo
from raster_api.v1 import service
from raster_api.v1.errors import ApiError
from raster_api.v1.schemas import (
    Comparison,
    ErrorResponse,
    PeriodList,
    Provenance,
    RiskList,
    Series,
)

router = APIRouter(
    prefix="/api/v1",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)

ID_PATTERN = r"^[A-Za-z0-9-]{1,24}$"
UBIGEO = re.compile(r"^1501[0-9]{2}$")
UnitTypeQ = Annotated[Literal["cell", "district"], Query(description="Spatial view")]
Conn = Annotated[Connection, Depends(get_connection)]


def _csv(value: str | None, name: str, pattern: re.Pattern[str] | None = None) -> list[str] | None:
    if value is None or value == "":
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    if len(items) != len(set(items)):
        raise ApiError(
            422, "INVALID_PARAMETERS", f"Duplicated values in {name}.", {"parameter": name}
        )
    for item in items:
        if not re.fullmatch(ID_PATTERN, item) or (pattern and not pattern.fullmatch(item)):
            raise ApiError(
                422,
                "INVALID_PARAMETERS",
                f"Invalid value in {name}.",
                {"parameter": name, "value": item},
            )
    return items


@router.get("/periods", response_model=PeriodList, summary="Available periods (RF-03)")
def get_periods(conn: Conn) -> PeriodList:
    return service.list_periods(service.Context(conn))


@router.get(
    "/units",
    summary="Spatial units as GeoJSON (RF-01, RG-01)",
    responses={200: {"content": {"application/geo+json": {}}}},
)
def get_units(
    conn: Conn,
    unit_type: UnitTypeQ = "cell",
    district_ids: Annotated[str | None, Query(description="Comma-separated UBIGEO")] = None,
) -> Response:
    districts = _csv(district_ids, "district_ids", UBIGEO)
    body = repo.units_geojson(conn, unit_type, districts)
    return Response(
        content=body,
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


class _LruCache:
    """Small thread-safe LRU cache of response bodies (per worker process)."""

    def __init__(self, size: int):
        self.size = size
        self._data: OrderedDict[tuple, bytes] = OrderedDict()
        self._lock = Lock()

    def get(self, key: tuple) -> bytes | None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
            return None

    def put(self, key: tuple, value: bytes) -> None:
        if self.size <= 0:
            return
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.size:
                self._data.popitem(last=False)


_RISK_CACHE = _LruCache(get_settings().risk_cache_entries)


@router.get(
    "/risk", response_model=RiskList, summary="Indicator, level and context (RF-01..RF-04, RF-07)"
)
def get_risk(
    conn: Conn,
    period_id: Annotated[str, Query(pattern=ID_PATTERN)],
    unit_type: UnitTypeQ = "cell",
    unit_id: Annotated[str | None, Query(pattern=ID_PATTERN)] = None,
    district_ids: Annotated[str | None, Query(description="Comma-separated UBIGEO")] = None,
    levels: Annotated[str | None, Query(description="Comma-separated: low,medium,high")] = None,
) -> RiskList:
    level_list = _csv(levels, "levels")
    if level_list and not set(level_list) <= {"low", "medium", "high"}:
        raise ApiError(
            422, "INVALID_PARAMETERS", "levels accepts low, medium, high.", {"parameter": "levels"}
        )
    ctx = service.Context(conn)
    districts = _csv(district_ids, "district_ids", UBIGEO)
    # Published results are immutable: the active run id is part of the key, so a new
    # publication never serves a stale answer. The cached value is the serialised body.
    key = (
        ctx.run_id,
        period_id,
        unit_type,
        unit_id,
        tuple(districts or ()),
        tuple(level_list or ()),
    )
    body = _RISK_CACHE.get(key)
    if body is None:
        result = service.list_risk(ctx, period_id, unit_type, unit_id, districts, level_list)
        body = result.model_dump_json().encode()
        _RISK_CACHE.put(key, body)
    return Response(body, media_type="application/json")


@router.get(
    "/comparisons",
    response_model=Comparison,
    summary="Units in one period (RF-05) or one unit across periods (RF-06)",
)
def get_comparisons(
    conn: Conn,
    mode: Literal["spatial", "temporal"],
    unit_type: UnitTypeQ = "cell",
    unit_ids: Annotated[
        str | None, Query(description="spatial: 2-4 comma-separated unit ids")
    ] = None,
    period_id: Annotated[str | None, Query(pattern=ID_PATTERN)] = None,
    unit_id: Annotated[str | None, Query(pattern=ID_PATTERN)] = None,
    period_ids: Annotated[
        str | None, Query(description="temporal: 2-24 comma-separated period ids")
    ] = None,
) -> Comparison:
    settings = get_settings()
    if mode == "spatial":
        units = _csv(unit_ids, "unit_ids")
        if unit_id or period_ids or not units or not period_id:
            raise ApiError(
                422, "INVALID_PARAMETERS", "Spatial mode requires unit_ids and period_id only."
            )
        if not 2 <= len(units) <= settings.max_compare_units:
            raise ApiError(
                422,
                "INVALID_PARAMETERS",
                f"Spatial mode compares 2 to {settings.max_compare_units} units.",
            )
        return service.compare_spatial(service.Context(conn), unit_type, units, period_id)
    periods = _csv(period_ids, "period_ids")
    if unit_ids or period_id or not unit_id or not periods:
        raise ApiError(
            422, "INVALID_PARAMETERS", "Temporal mode requires unit_id and period_ids only."
        )
    if not 2 <= len(periods) <= settings.max_compare_periods:
        raise ApiError(
            422,
            "INVALID_PARAMETERS",
            f"Temporal mode compares 2 to {settings.max_compare_periods} periods.",
        )
    return service.compare_temporal(service.Context(conn), unit_type, unit_id, periods)


@router.get(
    "/provenance",
    response_model=Provenance,
    summary="Sources, variables, coverage and limitations (RF-08, RD-05)",
)
def get_provenance(
    conn: Conn,
    unit_type: UnitTypeQ = "cell",
    unit_id: Annotated[str | None, Query(pattern=ID_PATTERN)] = None,
    period_id: Annotated[str | None, Query(pattern=ID_PATTERN)] = None,
) -> Provenance:
    return service.provenance(service.Context(conn), unit_type, unit_id, period_id)


@router.get(
    "/series",
    response_model=Series,
    summary="Yearly index series per unit for one day type and band (analyst views)",
)
def get_series(
    conn: Conn,
    day_type: Literal["weekday", "weekend"],
    time_band: Annotated[int, Query(ge=0, le=3)],
    unit_type: UnitTypeQ = "cell",
    district_ids: Annotated[str | None, Query(description="Comma-separated UBIGEO")] = None,
) -> Series:
    return service.yearly_series(
        service.Context(conn),
        unit_type,
        day_type,
        time_band,
        _csv(district_ids, "district_ids", UBIGEO),
    )
