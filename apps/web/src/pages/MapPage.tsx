// Map workspace: EP-01 (map, legend, view), EP-02 (zone panel), EP-03 (period,
// filters). Filters are applied by the API (RF-04); units outside the filtered
// subset are drawn faded, units without result are hatched (HU-21). The area
// outside the 43 districts is dimmed so the scope is unambiguous (RG-01).

import { useCallback, useMemo, useState } from "react";

import { api } from "../api/client";
import type { Legend as LegendDto, RiskLevel, RiskResult, UnitCollection } from "../api/types";
import { useApi } from "../api/useApi";
import { Notice, PeriodPicker, Segmented } from "../components/Controls";
import { Legend } from "../components/Legend";
import { RiskMap } from "../components/RiskMap";
import { ZonePanel } from "../components/ZonePanel";
import { BANDS, DAY_LABEL, fmtIndex, periodLabel } from "../lib/format";
import { classBands, colorFor, LEVEL_LABEL } from "../lib/levels";
import { ALL_LEVELS, useQuery } from "../state/QueryContext";

type MapLayer = "risk" | "record" | "influence";
const DENSITY_RAMP = ["#F6DFC4", "#EDB97F", "#D9822B", "#A8561A", "#6B3410"];
const INFLUENCE_RAMP = ["#D7EFEB", "#9FD6CD", "#4FB3A5", "#0B7F73", "#064C45"];

/** Quantile cut points of the non-zero recorded density (events per km2) of the period. */
function quantileCuts(rows: RiskResult[]): number[] {
  const d = rows
    .map((r) => (r.observed.events ?? 0) / Math.max(r.unit.area_km2, 0.1))
    .filter((v) => v > 0)
    .sort((a, b) => a - b);
  if (!d.length) return [0, 0, 0, 0];
  return [0.2, 0.4, 0.6, 0.8].map((p) => d[Math.min(d.length - 1, Math.floor(p * d.length))]);
}

interface Props {
  units: UnitCollection;
  districts: UnitCollection;
  legend: LegendDto;
  goCompare: (mode: "spatial" | "temporal") => void;
  goCorridors: (districtId: string) => void;
}

export function MapPage({ units, districts, legend, goCompare, goCorridors }: Props) {
  const q = useQuery();
  const bands = useMemo(() => classBands(legend), [legend]);
  const periodId = q.periodId(q.active);
  const [hover, setHover] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [layer, setLayer] = useState<MapLayer>("risk");

  const risk = useApi(
    (s) => api.risk({ periodId: periodId!, unitType: q.unitType, districtIds: q.districtIds, levels: q.levels }, s),
    [periodId, q.unitType, q.districtIds.join(), q.levels.join()],
    !!periodId,
  );
  // The selected unit is fetched on its own so it stays visible even when filtered out (HU-08).
  const selected = useApi(
    (s) => api.risk({ periodId: periodId!, unitType: q.unitType, unitId: q.selectedUnitId! }, s),
    [periodId, q.unitType, q.selectedUnitId],
    !!periodId && !!q.selectedUnitId,
  );

  // Influence map (Grad-CAM style) of the selected unit, precomputed offline.
  const explanation = useApi(
    (s) => api.explanation(q.unitType, q.selectedUnitId!, s),
    [q.unitType, q.selectedUnitId],
    !!q.selectedUnitId && layer === "influence",
  );
  const results = useMemo(() => new Map((risk.data?.data ?? []).map((r) => [r.unit.unit_id, r] as [string, RiskResult])), [risk.data]);
  const visible = useMemo(() => new Set(results.keys()), [results]);
  const filtersOn = q.levels.length > 0 || q.districtIds.length > 0;
  const densityCuts = useMemo(() => quantileCuts(risk.data?.data ?? []), [risk.data]);
  const influence = useMemo(
    () => new Map((explanation.data?.saliency ?? []).map(([u, w]) => [u, w] as [string, number])),
    [explanation.data],
  );
  const colorize = useCallback(
    (id: string): string | null => {
      if (layer === "record") {
        const r = results.get(id);
        if (!r) return null;
        const d = (r.observed.events ?? 0) / Math.max(r.unit.area_km2, 0.1);
        if (d <= 0) return "#F4F3EF";
        return DENSITY_RAMP[densityCuts.filter((c) => d > c).length];
      }
      const w = influence.get(id);
      if (w === undefined) return "#F4F3EF";
      return INFLUENCE_RAMP[Math.min(4, Math.floor(w * 5))];
    },
    [layer, results, densityCuts, influence],
  );
  const counts = risk.data?.counts;
  const hovered = hover ? results.get(hover) : undefined;
  const districtOptions = useMemo(
    () => districts.features.map((f) => ({ id: f.properties.unit_id, name: f.properties.display_name })).sort((a, b) => a.name.localeCompare(b.name, "es")),
    [districts],
  );

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    const term = search.trim().toUpperCase();
    if (!term) return;
    const cell = units.features.find((f) => f.properties.unit_id.toUpperCase() === term);
    const district = districtOptions.find((d) => d.name.toUpperCase().includes(term));
    if (cell) {
      if (q.unitType !== "cell") q.setUnitType("cell");
      q.select(cell.properties.unit_id);
    } else if (district) {
      if (q.unitType !== "district") q.setUnitType("district");
      q.select(district.id);
    }
  }

  return (
    <div className="workspace">
      <aside className="rail" aria-label="Consulta">
        <div>
          <p className="eyebrow">Explorar</p>
          <h2 className="rail-title">Riesgo por zona y periodo</h2>
        </div>
        <Segmented
          label="Unidad de análisis"
          value={q.unitType}
          options={[
            { value: "cell", label: "Celda de 1 km" },
            { value: "district", label: "Distrito" },
          ]}
          onChange={q.setUnitType}
        />
        <Segmented<MapLayer>
          label="Capa del mapa"
          wrap
          value={layer}
          options={[
            { value: "risk", label: "Riesgo estimado" },
            { value: "record", label: "Registro histórico" },
            { value: "influence", label: "Influencia de la red" },
          ]}
          onChange={setLayer}
          hint="Riesgo estimado por la red; densidad de atropellos registrados; o qué celdas pesan en la estimación de la zona seleccionada"
        />
        <PeriodPicker years={q.years} value={q.active} onChange={q.setActive} />
        {!periodId && <Notice tone="warn">Este periodo no tiene resultados publicados.</Notice>}

        <fieldset className="rail-section">
          <legend className="field-label" title="Sin selección se muestran todas las unidades">Nivel de riesgo</legend>
          {ALL_LEVELS.map((level: RiskLevel) => {
            const band = legend.bands.find((b) => b.level === level)!;
            return (
              <label key={level} className="check-row">
                <input type="checkbox" checked={q.levels.includes(level)} onChange={() => q.toggleLevel(level)} />
                <span className="swatch-pair" aria-hidden="true">
                  <span style={{ background: colorFor(band.min_index, bands)! }} />
                  <span style={{ background: colorFor(band.max_index - 1, bands)! }} />
                </span>
                {LEVEL_LABEL[level]} ({band.min_index} a {level === "high" ? 100 : band.max_index - 1})
                <span className="count">{counts ? counts[level].toLocaleString("es-PE") : "…"}</span>
              </label>
            );
          })}
          {counts && counts.no_result > 0 && <p className="muted small">{counts.no_result} sin resultado</p>}
        </fieldset>

        <div className="rail-section">
          <label className="field-label" htmlFor="district-filter">Distrito (43 de la provincia de Lima)</label>
          <select id="district-filter" className="select" value={q.districtIds[0] ?? ""} onChange={(e) => q.setDistricts(e.target.value ? [e.target.value] : [])}>
            <option value="">Todos los distritos</option>
            {districtOptions.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
          {filtersOn && (
            <div className="active-filters" aria-live="polite">
              <span>
                Filtrando: {q.levels.map((l) => LEVEL_LABEL[l]).join(", ") || "todos los niveles"},{" "}
                {q.districtIds.length ? districtOptions.find((d) => d.id === q.districtIds[0])?.name : "todos los distritos"}
              </span>
              <button type="button" className="btn small" onClick={q.clearFilters}>Quitar filtros</button>
            </div>
          )}
          <form className="search" onSubmit={onSearch} role="search">
            <label htmlFor="unit-search" className="field-label">Buscar</label>
            <input id="unit-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Distrito o celda, ej. F54-C35" />
          </form>
        </div>
      </aside>

      <main className="map-area">
        {risk.error && <Notice tone="error">No se pudo cargar el riesgo: {risk.error.message}</Notice>}
        <RiskMap
          units={q.unitType === "cell" ? units : districts}
          outline={q.unitType === "cell" ? districts : undefined}
          scope={districts}
          results={results}
          bands={bands}
          visible={filtersOn && layer === "risk" ? visible : null}
          colorize={layer === "risk" ? undefined : colorize}
          selected={q.selectedUnitId ? [q.selectedUnitId] : []}
          focus={q.selectedUnitId}
          onSelect={(id) => q.select(id)}
          onHover={(id) => setHover(id)}
          ariaLabel={`Mapa de riesgo por ${q.unitType === "cell" ? "celda" : "distrito"}, ${periodId ?? ""}`}
        />
        {risk.loading && <div className="map-loading">Cargando…</div>}
        {hovered && (
          <div className="map-tip" role="tooltip">
            <strong>{hovered.unit.unit_type === "cell" ? `Celda ${hovered.unit.unit_id}` : hovered.unit.display_name}</strong>
            <span className="muted">{hovered.unit.district_name}</span>
            <span>
              {hovered.risk_level ? (
                <>
                  <b>{fmtIndex(hovered.risk_index)}</b> {LEVEL_LABEL[hovered.risk_level]}
                </>
              ) : (
                "Sin resultado"
              )}
            </span>
            <span className="muted small">{periodLabel(hovered.period)}</span>
          </div>
        )}
        <div className="legend-dock">
          {layer === "record" && (
            <section className="legend">
              <strong>Atropellos registrados por km²</strong>
              <p className="legend-sub">{q.active.year}, {DAY_LABEL[q.active.dayType].toLowerCase()}, {BANDS[q.active.band]}. Registro de las fuentes, no estimación.</p>
              <ul className="legend-classes">
                <li><span className="swatch" style={{ background: "#F4F3EF", border: "1px solid var(--line)" }} /> Sin eventos registrados</li>
                {DENSITY_RAMP.map((c, i) => (
                  <li key={c}><span className="swatch" style={{ background: c }} /> {i === 0 ? "≤" : ">"} {densityCuts[Math.max(0, i - 1)]?.toFixed(2) ?? "0"}</li>
                ))}
              </ul>
            </section>
          )}
          {layer === "influence" && (
            <section className="legend">
              <strong>Influencia en la estimación</strong>
              <p className="legend-sub">
                {q.selectedUnitId
                  ? explanation.data?.saliency
                    ? `Celdas cuyos datos más pesan en la estimación de ${q.selectedUnitId} (gradiente × entrada, estilo Grad-CAM).`
                    : "Disponible para distritos y para las celdas de mayor riesgo de 2024."
                  : "Seleccione una zona en el mapa."}
              </p>
              <ul className="legend-classes">
                {INFLUENCE_RAMP.map((c, i) => (
                  <li key={c}><span className="swatch" style={{ background: c }} /> {i * 20} a {(i + 1) * 20} % de la máxima</li>
                ))}
              </ul>
            </section>
          )}
          {layer === "risk" && <Legend
            legend={legend}
            bands={bands}
            title={`Riesgo por ${q.unitType === "cell" ? "celda de 1 km" : "distrito"}`}
            subtitle={`${q.active.year}, ${DAY_LABEL[q.active.dayType].toLowerCase()}, ${BANDS[q.active.band]}. Escala común a todos los periodos.`}
          />}
        </div>
        <div className="map-scope">Provincia de Lima, 43 distritos (Callao excluido)</div>
      </main>

      <ZonePanel
        result={selected.data?.data[0] ?? null}
        bands={bands}
        onClose={() => q.select(null)}
        onCompareZones={() => {
          if (q.selectedUnitId) q.addCompareUnit(q.selectedUnitId);
          goCompare("spatial");
        }}
        onComparePeriods={() => {
          q.setTemporalUnit(q.selectedUnitId);
          goCompare("temporal");
        }}
        onOpenCorridors={goCorridors}
      />
    </div>
  );
}
