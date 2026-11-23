"""Pydantic DTOs of the read API v1 (contract: docs/api/contract.md)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

UnitType = Literal["cell", "district"]
RiskLevel = Literal["low", "medium", "high"]
Availability = Literal["estimated", "no_result", "outside_source_coverage"]
CONTRACT_VERSION = "1.0"


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class LevelBand(BaseModel):
    level: RiskLevel
    min_index: float
    max_index: float  # exclusive except for "high" (inclusive 100)
    label: str


class Legend(BaseModel):
    threshold_set_id: str
    version: str
    method: str
    bands: list[LevelBand]
    no_result_label: str


class RunSummary(BaseModel):
    run_id: str
    is_demo: bool
    model_family: str
    dataset_version_id: str
    target_definition_id: str
    population: str
    value_unit: str
    published_at: datetime | None


class Meta(BaseModel):
    contract_version: str = CONTRACT_VERSION
    run: RunSummary
    legend: Legend
    scope_notice: str
    generated_at: datetime


class Period(BaseModel):
    period_id: str
    year: int
    day_type: Literal["weekday", "weekend"]
    time_band: int
    start_date: date
    end_date: date  # exclusive
    start_hour: int
    end_hour: int  # exclusive
    granularity: str
    label: str
    partition: str
    observing_sources: list[str]


class PeriodList(BaseModel):
    meta: Meta
    data: list[Period]


class UnitRef(BaseModel):
    unit_id: str
    unit_type: UnitType
    display_name: str
    district_id: str
    district_name: str
    area_km2: float


class Observed(BaseModel):
    """Historical record (frequency reference), not the estimated risk."""

    events: float | None
    pedestrians_injured: int | None
    pedestrians_deceased: int | None


class Component(BaseModel):
    """Secondary risk component on its own frozen percentile scale (D-10)."""

    value: float | None
    index: float | None


class Breakdown(BaseModel):
    """Historical record by severity, subtype, vehicle type and transport service (counts).

    ``vehicle`` and ``service`` exist from dataset v1.2 (D-12); an event with several
    vehicles splits its count equally among them.
    """

    severity: dict[str, float]
    type: dict[str, float]
    vehicle: dict[str, float] | None = None
    service: dict[str, float] | None = None
    factor: dict[str, float] | None = None  # events per recorded factor (multi-label)


class RiskResult(BaseModel):
    unit: UnitRef
    period: Period
    run_id: str
    availability: Availability
    indicator_value: float | None
    value_unit: str
    risk_index: float | None
    risk_level: RiskLevel | None
    historical_average: float | None
    observed: Observed
    severity: Component = Component(value=None, index=None)
    exposure: Component = Component(value=None, index=None)
    breakdown: Breakdown | None = None


class LevelCounts(BaseModel):
    low: int = 0
    medium: int = 0
    high: int = 0
    no_result: int = 0


class RiskList(BaseModel):
    meta: Meta
    filters: dict[str, Any]
    counts: LevelCounts
    data: list[RiskResult]


class ComparisonItem(BaseModel):
    result: RiskResult
    index_difference: float | None  # vs. the first item; null if either has no result


class Comparison(BaseModel):
    meta: Meta
    mode: Literal["spatial", "temporal"]
    comparable: bool
    reason: str | None
    reference: str
    items: list[ComparisonItem]


class Source(BaseModel):
    source_id: str
    publisher: str
    name: str
    url: str | None
    licence: str
    captured_at: date | None
    coverage_start: date | None
    coverage_end: date | None
    spatial_coverage: str
    population: str
    incorporated: bool
    exclusion_reason: str | None


class Variable(BaseModel):
    variable_id: str
    label: str
    unit: str
    source_id: str | None
    reference_period: str
    description: str
    incorporated: bool


class Limitation(BaseModel):
    limitation_id: str
    dimension: str
    description: str


class ResultContext(BaseModel):
    unit: UnitRef
    period: Period
    availability: Availability
    observing_sources: list[str]
    observed: Observed


class Provenance(BaseModel):
    meta: Meta
    run: dict[str, Any]
    target: dict[str, Any]
    sources: list[Source]
    variables_by_group: dict[str, list[Variable]]
    limitations: list[Limitation]
    coverage: dict[str, Any]
    result_context: ResultContext | None


class SeriesUnit(BaseModel):
    unit_id: str
    display_name: str
    district_id: str
    risk_index: list[float | None]  # aligned with Series.years; null = no result
    risk_level: list[RiskLevel | None]
    indicator_value: list[float | None]
    observed_events: list[float | None]


class Series(BaseModel):
    """Compact yearly series for analyst views (decision D-06)."""

    meta: Meta
    unit_type: UnitType
    day_type: Literal["weekday", "weekend"]
    time_band: int
    years: list[int]
    period_ids: list[str]
    units: list[SeriesUnit]
