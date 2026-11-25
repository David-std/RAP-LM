// Spanish (Peru) formatting and labels used by every view.

import type { DayType, Period } from "../api/types";

// Same convention as the project report: decimal comma and a thin space for
// thousands (0,36; 258 896). Intl "es-PE" would give 0.36 and 258,896.
const nf = (digits: number) => {
  const base = new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return { format: (v: number) => base.format(v).replace(/,/g, " ").replace(".", ",") };
};
export const fmtNumber = (v: number, digits = 0) => nf(digits).format(v);

export const fmtIndex = (v: number | null) => (v === null ? "Sin resultado" : nf(0).format(v));
export const fmtValue = (v: number | null, digits = 2) => (v === null ? "Sin dato" : nf(digits).format(v));
export const fmtCount = (v: number | null) =>
  v === null ? "Sin dato" : Number.isInteger(v) ? nf(0).format(v) : nf(1).format(v);

export const DAY_LABEL: Record<DayType, string> = { weekday: "Laborable", weekend: "Fin de semana" };
export const BANDS = ["0–6 h", "6–12 h", "12–18 h", "18–24 h"];

export function periodLabel(p: Pick<Period, "year" | "day_type" | "time_band">): string {
  return `${p.year}, ${DAY_LABEL[p.day_type].toLowerCase()}, ${BANDS[p.time_band].replace("–", " a ")}`;
}

export const SOURCE_LABEL: Record<string, string> = {
  mininter_cenacom: "CENACOM (MININTER/INEI)",
  onsv_georeferenced_crashes: "ONSV",
};

export const PARTITION_LABEL: Record<string, string> = {
  train: "entrenamiento",
  validation: "validación",
  test: "prueba",
};
