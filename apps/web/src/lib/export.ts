// Client-side export of what the analyst is viewing. Every file carries the
// run, period and scope notice so that it remains interpretable outside the
// application (RF-07, RF-08).

import type { Meta, UnitCollection } from "../api/types";

export interface ExportColumn<T> {
  header: string;
  value: (row: T) => string | number | null;
}

function download(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

const csvCell = (v: string | number | null) => {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function exportCsv<T>(name: string, rows: T[], columns: ExportColumn<T>[], meta: Meta, context: string) {
  const header = [
    `# RAP-LM export; run ${meta.run.run_id}; dataset ${meta.run.dataset_version_id}; ${context}`,
    `# ${meta.scope_notice}`,
    `# Unit of indicator: ${meta.run.value_unit}. Empty cells = no result (not zero).`,
  ];
  const lines = [columns.map((c) => csvCell(c.header)).join(",")];
  for (const row of rows) lines.push(columns.map((c) => csvCell(c.value(row))).join(","));
  // BOM so that Excel opens accents correctly.
  download(`${name}.csv`, "﻿" + [...header, ...lines].join("\n"), "text/csv;charset=utf-8");
}

export function exportGeoJson(
  name: string,
  units: UnitCollection,
  properties: Map<string, Record<string, unknown>>,
  meta: Meta,
  context: string,
) {
  const features = units.features
    .filter((f) => properties.has(f.properties.unit_id))
    .map((f) => ({ ...f, properties: { ...f.properties, ...properties.get(f.properties.unit_id) } }));
  const fc = {
    type: "FeatureCollection",
    metadata: {
      run_id: meta.run.run_id,
      dataset_version_id: meta.run.dataset_version_id,
      context,
      scope_notice: meta.scope_notice,
      value_unit: meta.run.value_unit,
      crs: "EPSG:4326",
    },
    features,
  };
  download(`${name}.geojson`, JSON.stringify(fc), "application/geo+json");
}
