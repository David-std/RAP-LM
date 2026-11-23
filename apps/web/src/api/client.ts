// Typed API client: the only HTTP boundary of the SPA (Figure 5C).
// Every call accepts an AbortSignal so that a period or filter change cancels
// stale requests instead of letting them overwrite newer state.

import type {
  ApiErrorBody,
  Comparison,
  CorridorCollection,
  Explanation,
  ModelCardDto,
  PeriodList,
  Provenance,
  RiskLevel,
  RiskList,
  Series,
  UnitCollection,
  UnitType,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

type Params = Record<string, string | number | string[] | undefined | null>;

function query(params: Params): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      if (value.length) search.set(key, value.join(","));
    } else {
      search.set(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function get<T>(path: string, params: Params, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${BASE}/api/v1${path}${query(params)}`, { signal });
  if (!response.ok) {
    let code = "HTTP_ERROR";
    let message = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      code = body.error.code;
      message = body.error.message;
    } catch {
      /* non-JSON error body: keep the HTTP status */
    }
    throw new ApiError(response.status, code, message);
  }
  return (await response.json()) as T;
}

export const api = {
  periods: (signal?: AbortSignal) => get<PeriodList>("/periods", {}, signal),

  units: (unitType: UnitType, signal?: AbortSignal) =>
    get<UnitCollection>("/units", { unit_type: unitType }, signal),

  risk: (
    args: {
      periodId: string;
      unitType: UnitType;
      unitId?: string;
      districtIds?: string[];
      levels?: RiskLevel[];
    },
    signal?: AbortSignal,
  ) =>
    get<RiskList>(
      "/risk",
      {
        period_id: args.periodId,
        unit_type: args.unitType,
        unit_id: args.unitId,
        district_ids: args.districtIds,
        levels: args.levels,
      },
      signal,
    ),

  compareSpatial: (unitType: UnitType, unitIds: string[], periodId: string, signal?: AbortSignal) =>
    get<Comparison>(
      "/comparisons",
      { mode: "spatial", unit_type: unitType, unit_ids: unitIds, period_id: periodId },
      signal,
    ),

  compareTemporal: (unitType: UnitType, unitId: string, periodIds: string[], signal?: AbortSignal) =>
    get<Comparison>(
      "/comparisons",
      { mode: "temporal", unit_type: unitType, unit_id: unitId, period_ids: periodIds },
      signal,
    ),

  series: (
    args: { unitType: UnitType; dayType: string; band: number; districtIds?: string[] },
    signal?: AbortSignal,
  ) =>
    get<Series>(
      "/series",
      { unit_type: args.unitType, day_type: args.dayType, time_band: args.band, district_ids: args.districtIds },
      signal,
    ),

  corridors: (args: { districtIds?: string[]; limit?: number; minEvents?: number }, signal?: AbortSignal) =>
    get<CorridorCollection>(
      "/corridors",
      { district_ids: args.districtIds, limit: args.limit, min_events: args.minEvents },
      signal,
    ),

  explanation: (unitType: UnitType, unitId: string, signal?: AbortSignal) =>
    get<Explanation>("/explanations", { unit_type: unitType, unit_id: unitId }, signal),

  model: (signal?: AbortSignal) => get<ModelCardDto>("/model", {}, signal),

  provenance: (
    args: { unitType?: UnitType; unitId?: string; periodId?: string },
    signal?: AbortSignal,
  ) =>
    get<Provenance>(
      "/provenance",
      { unit_type: args.unitType, unit_id: args.unitId, period_id: args.periodId },
      signal,
    ),
};
