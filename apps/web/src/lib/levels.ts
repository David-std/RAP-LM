// Visual encoding of the risk index. Six classes subdivide the three levels
// (low 0-39, medium 40-69, high 70-100); level cut points come from the API
// legend, so a new threshold version re-colours the map without code edits.

import type { Legend, RiskLevel } from "../api/types";

export const RAMP = ["#FDEEE8", "#F8CBB8", "#F09A80", "#E0664D", "#BF3A2E", "#7E1F22"] as const;
export const NO_RESULT_FILL = "url(#no-result-hatch)";

export const LEVEL_LABEL: Record<RiskLevel, string> = { low: "Bajo", medium: "Medio", high: "Alto" };

export interface ClassBand {
  min: number;
  max: number;
  color: string;
  level: RiskLevel;
}

/** Split each level band in two equal halves -> six classes. */
export function classBands(legend: Legend): ClassBand[] {
  const out: ClassBand[] = [];
  legend.bands.forEach((band, i) => {
    const mid = Math.round((band.min_index + band.max_index) / 2);
    out.push({ min: band.min_index, max: mid, color: RAMP[i * 2], level: band.level });
    out.push({ min: mid, max: band.max_index, color: RAMP[i * 2 + 1], level: band.level });
  });
  return out;
}

export function colorFor(index: number | null, bands: ClassBand[]): string | null {
  if (index === null) return null;
  for (let i = bands.length - 1; i >= 0; i--) if (index >= bands[i].min) return bands[i].color;
  return bands[0].color;
}

/** Text colour with enough contrast on top of a ramp colour (WCAG AA). */
export function inkOn(color: string): string {
  return RAMP.indexOf(color as (typeof RAMP)[number]) >= 3 ? "#FFFFFF" : "#18191B";
}
