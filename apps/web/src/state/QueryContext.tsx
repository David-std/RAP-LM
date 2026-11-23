// Single query state shared by every view (Figure 5C "shared query state").
// Changing the active period here re-renders the map, the detail panel and
// the open comparisons together (RF-03, HU-11, HU-12).

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { DayType, Period, RiskLevel, UnitType } from "../api/types";

export interface PeriodKey {
  year: number;
  dayType: DayType;
  band: number;
}

export interface QueryState {
  periods: Period[];
  active: PeriodKey;
  unitType: UnitType;
  levels: RiskLevel[]; // empty = all
  districtIds: string[]; // empty = all
  selectedUnitId: string | null;
  compareUnitIds: string[];
  compareMode: "spatial" | "temporal";
  temporalUnitId: string | null;
  periodA: PeriodKey;
  periodB: PeriodKey;
}

interface QueryActions {
  setActive: (patch: Partial<PeriodKey>) => void;
  setUnitType: (t: UnitType) => void;
  toggleLevel: (level: RiskLevel) => void;
  setDistricts: (ids: string[]) => void;
  clearFilters: () => void;
  select: (unitId: string | null) => void;
  addCompareUnit: (unitId: string) => void;
  removeCompareUnit: (unitId: string) => void;
  setCompareMode: (m: "spatial" | "temporal") => void;
  setTemporalUnit: (unitId: string | null) => void;
  setPeriodA: (patch: Partial<PeriodKey>) => void;
  setPeriodB: (patch: Partial<PeriodKey>) => void;
  periodId: (key: PeriodKey) => string | null;
  years: number[];
}

const Ctx = createContext<(QueryState & QueryActions) | null>(null);
export const MAX_COMPARE = 4;
export const ALL_LEVELS: RiskLevel[] = ["high", "medium", "low"];

export function QueryProvider({ periods, children }: { periods: Period[]; children: ReactNode }) {
  const years = useMemo(() => [...new Set(periods.map((p) => p.year))].sort(), [periods]);
  const index = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of periods) map.set(`${p.year}|${p.day_type}|${p.time_band}`, p.period_id);
    return map;
  }, [periods]);
  const last = years[years.length - 1];
  const first = years[0];

  const fromUrl = useMemo(() => readHash(years), [years]);
  const [state, setState] = useState<Omit<QueryState, "periods">>({
    active: fromUrl.active ?? { year: last, dayType: "weekday", band: 3 },
    unitType: fromUrl.unitType ?? "cell",
    levels: fromUrl.levels ?? [],
    districtIds: fromUrl.districtIds ?? [],
    selectedUnitId: fromUrl.selectedUnitId ?? null,
    compareUnitIds: [],
    compareMode: "spatial",
    temporalUnitId: null,
    periodA: { year: first, dayType: "weekday", band: 3 },
    periodB: { year: last, dayType: "weekday", band: 3 },
  });

  // Shareable link: keep the main query in the URL hash (no history spam).
  useEffect(() => {
    const params = new URLSearchParams({
      y: String(state.active.year),
      d: state.active.dayType,
      b: String(state.active.band),
      u: state.unitType,
    });
    if (state.levels.length) params.set("lv", state.levels.join(","));
    if (state.districtIds.length) params.set("dist", state.districtIds.join(","));
    if (state.selectedUnitId) params.set("sel", state.selectedUnitId);
    window.history.replaceState(null, "", `#${params.toString()}`);
  }, [state.active, state.unitType, state.levels, state.districtIds, state.selectedUnitId]);

  const patch = useCallback((p: Partial<Omit<QueryState, "periods">>) => setState((s) => ({ ...s, ...p })), []);

  const actions: QueryActions = useMemo(
    () => ({
      years,
      periodId: (k) => index.get(`${k.year}|${k.dayType}|${k.band}`) ?? null,
      setActive: (p) => setState((s) => ({ ...s, active: { ...s.active, ...p } })),
      // Changing the view resets selections: ids of cells and districts differ.
      setUnitType: (t) =>
        patch({ unitType: t, selectedUnitId: null, compareUnitIds: [], temporalUnitId: null }),
      toggleLevel: (level) =>
        setState((s) => ({
          ...s,
          levels: s.levels.includes(level) ? s.levels.filter((l) => l !== level) : [...s.levels, level],
        })),
      setDistricts: (ids) => patch({ districtIds: ids }),
      clearFilters: () => patch({ levels: [], districtIds: [] }),
      select: (unitId) => patch({ selectedUnitId: unitId }),
      addCompareUnit: (unitId) =>
        setState((s) =>
          s.compareUnitIds.includes(unitId) || s.compareUnitIds.length >= MAX_COMPARE
            ? s
            : { ...s, compareUnitIds: [...s.compareUnitIds, unitId] },
        ),
      removeCompareUnit: (unitId) =>
        setState((s) => ({ ...s, compareUnitIds: s.compareUnitIds.filter((u) => u !== unitId) })),
      setCompareMode: (m) => patch({ compareMode: m }),
      setTemporalUnit: (unitId) => patch({ temporalUnitId: unitId }),
      setPeriodA: (p) => setState((s) => ({ ...s, periodA: { ...s.periodA, ...p } })),
      setPeriodB: (p) => setState((s) => ({ ...s, periodB: { ...s.periodB, ...p } })),
    }),
    [years, index, patch],
  );

  return <Ctx.Provider value={{ periods, ...state, ...actions }}>{children}</Ctx.Provider>;
}

export function useQuery() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useQuery must be used inside QueryProvider");
  return ctx;
}

/** Parse a shared link; unknown or invalid values fall back to defaults. */
function readHash(years: number[]): Partial<Omit<QueryState, "periods">> {
  const p = new URLSearchParams(window.location.hash.slice(1));
  const out: Partial<Omit<QueryState, "periods">> = {};
  const year = Number(p.get("y"));
  const dayType = p.get("d");
  const band = Number(p.get("b"));
  if (years.includes(year) && (dayType === "weekday" || dayType === "weekend") && band >= 0 && band <= 3) {
    out.active = { year, dayType, band };
  }
  const unitType = p.get("u");
  if (unitType === "cell" || unitType === "district") out.unitType = unitType;
  const levels = (p.get("lv") ?? "").split(",").filter((l): l is RiskLevel => ["low", "medium", "high"].includes(l));
  if (levels.length) out.levels = levels;
  const districts = (p.get("dist") ?? "").split(",").filter((d) => /^1501\d{2}$/.test(d));
  if (districts.length) out.districtIds = districts;
  const sel = p.get("sel");
  if (sel && /^[A-Za-z0-9-]{1,24}$/.test(sel)) out.selectedUnitId = sel;
  return out;
}
