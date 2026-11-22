// DTOs of the read API v1 (docs/api/contract.md). Keep in sync with
// apps/api/src/raster_api/v1/schemas.py; the contract test checks the API side.

export type UnitType = "cell" | "district";
export type RiskLevel = "low" | "medium" | "high";
export type Availability = "estimated" | "no_result" | "outside_source_coverage";
export type DayType = "weekday" | "weekend";

export interface LevelBand {
  level: RiskLevel;
  min_index: number;
  max_index: number;
  label: string;
}

export interface Legend {
  threshold_set_id: string;
  version: string;
  method: string;
  bands: LevelBand[];
  no_result_label: string;
}

export interface RunSummary {
  run_id: string;
  is_demo: boolean;
  model_family: string;
  dataset_version_id: string;
  target_definition_id: string;
  population: string;
  value_unit: string;
  published_at: string | null;
}

export interface Meta {
  contract_version: string;
  run: RunSummary;
  legend: Legend;
  scope_notice: string;
  generated_at: string;
}

export interface Period {
  period_id: string;
  year: number;
  day_type: DayType;
  time_band: number;
  start_date: string;
  end_date: string;
  start_hour: number;
  end_hour: number;
  granularity: string;
  label: string;
  partition: string;
  observing_sources: string[];
}

export interface UnitRef {
  unit_id: string;
  unit_type: UnitType;
  display_name: string;
  district_id: string;
  district_name: string;
  area_km2: number;
}

export interface Observed {
  events: number | null;
  pedestrians_injured: number | null;
  pedestrians_deceased: number | null;
}

export interface RiskResult {
  unit: UnitRef;
  period: Period;
  run_id: string;
  availability: Availability;
  indicator_value: number | null;
  value_unit: string;
  risk_index: number | null;
  risk_level: RiskLevel | null;
  historical_average: number | null;
  observed: Observed;
}

export interface LevelCounts {
  low: number;
  medium: number;
  high: number;
  no_result: number;
}

export interface PeriodList {
  meta: Meta;
  data: Period[];
}

export interface RiskList {
  meta: Meta;
  filters: Record<string, unknown>;
  counts: LevelCounts;
  data: RiskResult[];
}

export interface ComparisonItem {
  result: RiskResult;
  index_difference: number | null;
}

export interface Comparison {
  meta: Meta;
  mode: "spatial" | "temporal";
  comparable: boolean;
  reason: string | null;
  reference: string;
  items: ComparisonItem[];
}

export interface Source {
  source_id: string;
  publisher: string;
  name: string;
  url: string | null;
  licence: string;
  captured_at: string | null;
  coverage_start: string | null;
  coverage_end: string | null;
  spatial_coverage: string;
  population: string;
  incorporated: boolean;
  exclusion_reason: string | null;
}

export interface Variable {
  variable_id: string;
  label: string;
  unit: string;
  source_id: string | null;
  reference_period: string;
  description: string;
  incorporated: boolean;
}

export interface Limitation {
  limitation_id: string;
  dimension: string;
  description: string;
}

export interface Provenance {
  meta: Meta;
  run: Record<string, unknown> & { run_id: string; metrics: BenchmarkMetrics; split: unknown };
  target: Record<string, string>;
  sources: Source[];
  variables_by_group: Record<"occurrence" | "severity" | "exposure" | "context", Variable[]>;
  limitations: Limitation[];
  coverage: { spatial: string; published_years: number[]; periods: number };
  result_context: {
    unit: UnitRef;
    period: Period;
    availability: Availability;
    observing_sources: string[];
    observed: Observed;
  } | null;
}

export interface ErrorMeasures {
  district_mae: number;
  cell_mae: number;
  cell_deviance: number;
  capture_top10: number;
}

export interface EvaluationRow {
  family: string;
  year: number;
  observed_events: number;
  located_events: number;
  model: ErrorMeasures;
  baseline: ErrorMeasures | null;
  relative_improvement_pct: number | null;
  note?: string;
}

export interface BenchmarkMetrics {
  selected_variant: string;
  selection_rule: string;
  candidates: Record<string, { best_validation_nll: number; test?: EvaluationRow[] }>;
  validation: EvaluationRow[];
  test: EvaluationRow[];
  reporting_factor: Record<string, number>;
}

export interface UnitFeature {
  type: "Feature";
  id: string;
  properties: {
    unit_id: string;
    unit_type: UnitType;
    display_name: string;
    district_id: string;
    district_name: string;
    area_km2: number;
    row: number | null;
    col: number | null;
  };
  geometry: GeoJSON.MultiPolygon | GeoJSON.Polygon;
}

export interface UnitCollection {
  type: "FeatureCollection";
  features: UnitFeature[];
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> };
}

export interface SeriesUnit {
  unit_id: string;
  display_name: string;
  district_id: string;
  risk_index: (number | null)[];
  risk_level: (RiskLevel | null)[];
  indicator_value: (number | null)[];
  observed_events: (number | null)[];
}

export interface Series {
  meta: Meta;
  unit_type: UnitType;
  day_type: DayType;
  time_band: number;
  years: number[];
  period_ids: string[];
  units: SeriesUnit[];
}
