"""Application services of the read API (Figure 5D).

Rules enforced here (docs/api/contract.md):
* the active published run is resolved **once per request** and every value
  in the response comes from that run;
* unknown units/periods are errors, never substitutions by another unit or
  period;
* a unit-period without a stored estimate is returned as ``no_result`` with
  null indicator/level, never as zero or "low";
* comparisons across spatial representations are rejected (HU-18).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection

from raster_api.v1 import repository as repo
from raster_api.v1.errors import ApiError
from raster_api.v1.schemas import (
    Breakdown,
    Comparison,
    ComparisonItem,
    Component,
    Legend,
    LevelBand,
    LevelCounts,
    Limitation,
    Meta,
    Observed,
    Period,
    PeriodList,
    Provenance,
    ResultContext,
    RiskList,
    RiskResult,
    RunSummary,
    Series,
    SeriesUnit,
    Source,
    UnitRef,
    Variable,
)

SCOPE_NOTICE = (
    "Índice relativo de riesgo de atropello peatonal (todas las severidades) estimado por un "
    "modelo CNN-RNN a partir de registros fusionados del censo de comisarías y del ONSV. "
    "Referencia analítica: no es una predicción en tiempo real ni recomienda intervenciones."
)
DEMO_NOTICE = (
    "DATOS DE EJEMPLO (DEMO): valores sintéticos para probar la interfaz, "
    "no son resultados del modelo."
)
GROUPS = ("occurrence", "severity", "exposure", "context")


class Context:
    """Request-scoped snapshot: one connection, one pinned run."""

    def __init__(self, conn: Connection):
        self.conn = conn
        run = repo.active_run(conn)
        if run is None:
            raise ApiError(503, "NO_PUBLISHED_RUN", "No approved run is published yet.")
        self.run = run
        self._periods = {p["period_id"]: p for p in repo.periods(conn, run["run_id"])}

    @property
    def run_id(self) -> str:
        return self.run["run_id"]

    def meta(self) -> Meta:
        r = self.run
        low, mid = r["low_max"], r["medium_max"]
        legend = Legend(
            threshold_set_id=r["threshold_set_id"],
            version=r["th_version"],
            method=r["th_method"],
            bands=[
                LevelBand(level="low", min_index=0, max_index=low, label="Bajo"),
                LevelBand(level="medium", min_index=low, max_index=mid, label="Medio"),
                LevelBand(level="high", min_index=mid, max_index=100, label="Alto"),
            ],
            no_result_label="Sin resultado (no equivale a riesgo bajo)",
        )
        return Meta(
            run=RunSummary(
                run_id=r["run_id"],
                is_demo=r["is_demo"],
                model_family=r["model_family"],
                dataset_version_id=r["dataset_version_id"],
                target_definition_id=r["target_definition_id"],
                population=r["population"],
                value_unit=r["value_unit"],
                published_at=r["published_at"],
            ),
            legend=legend,
            scope_notice=DEMO_NOTICE if r["is_demo"] else SCOPE_NOTICE,
            generated_at=datetime.now(UTC),
        )

    def period(self, period_id: str) -> Period:
        p = self._periods.get(period_id)
        if p is None:
            raise ApiError(
                404,
                "UNKNOWN_PERIOD",
                "The period is not available in the published run.",
                {"period_id": period_id},
            )
        return Period(**p)

    def unit(self, unit_type: str, unit_id: str) -> dict[str, Any]:
        u = repo.unit_exists(self.conn, unit_type, unit_id)
        if u is None:
            raise ApiError(
                404,
                "UNKNOWN_UNIT",
                "The spatial unit does not exist in this view.",
                {"unit_id": unit_id, "unit_type": unit_type},
            )
        return u

    def to_result(self, row: dict[str, Any]) -> RiskResult:
        estimated = row["availability"] == "estimated"
        return RiskResult(
            unit=UnitRef(**{k: row[k] for k in UnitRef.model_fields}),
            period=self.period(row["period_id"]),
            run_id=self.run_id,
            availability=row["availability"],
            indicator_value=row["indicator_value"] if estimated else None,
            value_unit=self.run["value_unit"],
            risk_index=row["risk_index"] if estimated else None,
            risk_level=row["risk_level"] if estimated else None,
            historical_average=row["historical_average"],
            observed=Observed(
                events=row["observed_events"],
                pedestrians_injured=row["observed_injured"],
                pedestrians_deceased=row["observed_deceased"],
            ),
            severity=Component(
                value=row.get("severity_value") if estimated else None,
                index=row.get("severity_index") if estimated else None,
            ),
            exposure=Component(
                value=row.get("exposure_ratio") if estimated else None,
                index=row.get("exposure_index") if estimated else None,
            ),
            breakdown=_breakdown(row.get("breakdown")),
        )


SEVERITY_KEYS = ("fatal", "nonfatal", "material_only", "unknown")
TYPE_KEYS = ("atropello", "atropello_fuga", "choque_y_atropello", "otro")
VEHICLE_KEYS = (
    "auto",
    "camioneta",
    "combi_minibus",
    "bus",
    "carga",
    "moto",
    "mototaxi",
    "bicicleta",
    "no_identificado",
)
SERVICE_KEYS = ("publico", "particular", "carga", "no_identificado")


def _breakdown(raw: Any) -> Breakdown | None:
    if not raw:
        return None
    vehicle, service = raw.get("vehicle"), raw.get("service")  # dataset v1.2 onwards (D-12)
    return Breakdown(
        severity=dict(zip(SEVERITY_KEYS, raw["severity"], strict=True)),
        type=dict(zip(TYPE_KEYS, raw["type"], strict=True)),
        vehicle=dict(zip(VEHICLE_KEYS, vehicle, strict=True)) if vehicle else None,
        service=dict(zip(SERVICE_KEYS, service, strict=True)) if service else None,
    )


def list_periods(ctx: Context) -> PeriodList:
    return PeriodList(meta=ctx.meta(), data=[ctx.period(p) for p in ctx._periods])


def list_risk(
    ctx: Context,
    period_id: str,
    unit_type: str,
    unit_id: str | None,
    district_ids: list[str] | None,
    levels: list[str] | None,
) -> RiskList:
    ctx.period(period_id)
    if unit_id:
        ctx.unit(unit_type, unit_id)
    rows = repo.results(
        ctx.conn,
        ctx.run_id,
        unit_type,
        [period_id],
        unit_ids=[unit_id] if unit_id else None,
        district_ids=district_ids,
    )
    counts = LevelCounts()
    for r in rows:
        key = r["risk_level"] or "no_result"
        setattr(counts, key, getattr(counts, key) + 1)
    if levels:
        rows = [r for r in rows if r["risk_level"] in levels]
    return RiskList(
        meta=ctx.meta(),
        filters={
            "period_id": period_id,
            "unit_type": unit_type,
            "unit_id": unit_id,
            "district_ids": district_ids or [],
            "levels": levels or [],
        },
        counts=counts,
        data=[ctx.to_result(r) for r in rows],
    )


def _difference(first: RiskResult, other: RiskResult) -> float | None:
    if first.risk_index is None or other.risk_index is None:
        return None
    return round(other.risk_index - first.risk_index, 4)


def compare_spatial(
    ctx: Context, unit_type: str, unit_ids: list[str], period_id: str
) -> Comparison:
    _check_representation(ctx, unit_type, unit_ids)
    for u in unit_ids:
        ctx.unit(unit_type, u)
    ctx.period(period_id)
    rows = repo.results(ctx.conn, ctx.run_id, unit_type, [period_id], unit_ids=unit_ids)
    by_unit = {r["unit_id"]: ctx.to_result(r) for r in rows}
    ordered = [by_unit[u] for u in unit_ids]
    return _comparison(ctx, "spatial", ordered, f"unit {unit_ids[0]}")


def compare_temporal(
    ctx: Context, unit_type: str, unit_id: str, period_ids: list[str]
) -> Comparison:
    ctx.unit(unit_type, unit_id)
    for p in period_ids:
        ctx.period(p)
    rows = repo.results(ctx.conn, ctx.run_id, unit_type, period_ids, unit_ids=[unit_id])
    by_period = {r["period_id"]: ctx.to_result(r) for r in rows}
    ordered = [by_period[p] for p in period_ids]
    return _comparison(ctx, "temporal", ordered, f"period {period_ids[0]}")


def _comparison(ctx: Context, mode: str, results: list[RiskResult], reference: str) -> Comparison:
    missing = [r for r in results if r.availability != "estimated"]
    reason = None
    if missing:
        labels = ", ".join(f"{r.unit.unit_id}/{r.period.period_id}" for r in missing)
        reason = f"Some items have no result and are not compared: {labels}."
    first = results[0]
    return Comparison(
        meta=ctx.meta(),
        mode=mode,
        comparable=len(results) - len(missing) >= 2,
        reason=reason,
        reference=reference,
        items=[ComparisonItem(result=r, index_difference=_difference(first, r)) for r in results],
    )


def _check_representation(ctx: Context, unit_type: str, unit_ids: list[str]) -> None:
    types = repo.unit_types_of(ctx.conn, unit_ids)
    mixed = [u for u in unit_ids if u in types and unit_type not in types[u]]
    if mixed:
        raise ApiError(
            409,
            "INCOMPATIBLE_COMPARISON",
            "Units of different spatial representations (cell vs district) use different "
            "scales and cannot be compared.",
            {"unit_type": unit_type, "incompatible_units": mixed},
        )


def provenance(
    ctx: Context, unit_type: str, unit_id: str | None, period_id: str | None
) -> Provenance:
    data = repo.provenance(ctx.conn, ctx.run_id)
    groups: dict[str, list[Variable]] = {g: [] for g in GROUPS}
    for v in data["variables"]:
        groups[v["concept_group"]].append(
            Variable(
                **{k: v[k] for k in Variable.model_fields if k != "incorporated"},
                incorporated=v["incorporated"] and v["used"],
            )
        )
    r = ctx.run
    result_context = None
    if unit_id or period_id:
        if not (unit_id and period_id):
            raise ApiError(
                422, "INVALID_PARAMETERS", "unit_id and period_id must be provided together."
            )
        ctx.unit(unit_type, unit_id)
        period = ctx.period(period_id)
        row = repo.results(ctx.conn, ctx.run_id, unit_type, [period_id], unit_ids=[unit_id])[0]
        res = ctx.to_result(row)
        result_context = ResultContext(
            unit=res.unit,
            period=period,
            availability=res.availability,
            observing_sources=period.observing_sources,
            observed=res.observed,
        )
    years = sorted({p.year for p in (ctx.period(x) for x in ctx._periods)})
    return Provenance(
        meta=ctx.meta(),
        run={
            "run_id": r["run_id"],
            "is_demo": r["is_demo"],
            "model_family": r["model_family"],
            "dataset_version_id": r["dataset_version_id"],
            "code_commit_sha": r["code_commit_sha"],
            "seed": r["seed"],
            "published_at": r["published_at"],
            "split": r["split"],
            "metrics": r["metrics"],
            "artifact_sha256": r["artifact_sha256"],
            "results_sha256": r["results_sha256"],
        },
        target={
            "target_definition_id": r["target_definition_id"],
            "population": r["population"],
            "definition": r["definition"],
            "value_unit": r["value_unit"],
            "index_method": r["index_method"],
        },
        sources=[Source(**{k: s[k] for k in Source.model_fields}) for s in data["sources"]],
        variables_by_group=groups,
        limitations=[Limitation(**x) for x in data["limitations"]],
        coverage={
            "spatial": "43 districts of the province of Lima (Callao excluded)",
            "published_years": years,
            "periods": len(ctx._periods),
        },
        result_context=result_context,
    )


def yearly_series(
    ctx: Context, unit_type: str, day_type: str, time_band: int, district_ids: list[str] | None
) -> Series:
    periods = sorted(
        (
            p
            for p in ctx._periods.values()
            if p["day_type"] == day_type and p["time_band"] == time_band
        ),
        key=lambda p: p["year"],
    )
    years = [p["year"] for p in periods]
    pos = {y: i for i, y in enumerate(years)}
    units: dict[str, SeriesUnit] = {}
    for row in repo.series(ctx.conn, ctx.run_id, unit_type, day_type, time_band, district_ids):
        unit = units.get(row["unit_id"])
        if unit is None:
            n = len(years)
            unit = units[row["unit_id"]] = SeriesUnit(
                unit_id=row["unit_id"],
                display_name=row["display_name"],
                district_id=row["district_id"],
                risk_index=[None] * n,
                risk_level=[None] * n,
                indicator_value=[None] * n,
                observed_events=[None] * n,
            )
        i = pos[row["year"]]
        unit.risk_index[i] = row["risk_index"]
        unit.risk_level[i] = row["risk_level"]
        unit.indicator_value[i] = row["indicator_value"]
        unit.observed_events[i] = row["observed_events"]
    return Series(
        meta=ctx.meta(),
        unit_type=unit_type,
        day_type=day_type,
        time_band=time_band,
        years=years,
        period_ids=[p["period_id"] for p in periods],
        units=list(units.values()),
    )
