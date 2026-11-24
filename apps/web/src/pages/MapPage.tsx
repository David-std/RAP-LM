// Map workspace: EP-01 (map, legend, view), EP-02 (zone panel), EP-03 (period,
// filters). Filters are applied by the API (RF-04); units outside the filtered
// subset are drawn faded, units without result are hatched (HU-21). The area
// outside the 43 districts is dimmed so the scope is unambiguous (RG-01).

import { useCallback, useMemo, useState } from "react";

import { api } from "../api/client";
import type { Legend as LegendDto, RiskLevel, RiskResult, UnitCollection } from "../api/types";
import { useApi } from "../api/useApi";
import { FilterChips, Notice, OptionList, PeriodPicker, SearchSelect, Segmented } from "../components/Controls";
import { HeatMap } from "../components/HeatMap";
import { Legend } from "../components/Legend";
import { RiskMap } from "../components/RiskMap";
import { ZonePanel } from "../components/ZonePanel";
import { BANDS, DAY_LABEL, fmtIndex, periodLabel } from "../lib/format";
import { classBands, colorFor, LEVEL_LABEL } from "../lib/levels";
import { heatLegend } from "../lib/heatSurface";
import { ALL_LEVELS, useQuery } from "../state/QueryContext";

type MapLayer = "risk" | "record" | "influence";
type MapView = "cells" | "districts" | "heat";
const DENSITY_RAMP = ["#F6DFC4", "#EDB97F", "#D9822B", "#A8561A", "#6B3410"];
const HOT_RAMP = { 0: "#493BC5", 0.2: "#344BE3", 0.35: "#10C8F0", 0.5: "#17E653", 0.65: "#F5ED21", 0.76: "#FF8C12", 0.88: "#F02010", 1: "#B91008" };
const INFLUENCE_RAMP = ["#A3DED8", "#65C9C0", "#27A99D", "#087D74", "#064C45"];
const HEAT_GRADIENT: Record<MapLayer, Record<number, string>> = {
  risk: HOT_RAMP,
  record: HOT_RAMP,
  influence: { 0: "#E6F6F4", 0.2: INFLUENCE_RAMP[0], 0.4: INFLUENCE_RAMP[1], 0.6: INFLUENCE_RAMP[2], 0.8: INFLUENCE_RAMP[3], 1: INFLUENCE_RAMP[4] },
};

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
  const [heat, setHeat] = useState(false);
  const view: MapView = heat ? "heat" : q.unitType === "cell" ? "cells" : "districts";
  const changeView = (v: MapView) => {
    setHeat(v === "heat");
    const unit = v === "districts" ? "district" : "cell";
    if (q.unitType !== unit) q.setUnitType(unit);
  };

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

  // Grad-CAM map of the selected unit, precomputed offline.
  const explanation = useApi(
    (s) => api.explanation(q.unitType, q.selectedUnitId!, s),
    [q.unitType, q.selectedUnitId],
    !!q.selectedUnitId && layer === "influence",
  );
  const results = useMemo(() => new Map((risk.data?.data ?? []).map((r) => [r.unit.unit_id, r] as [string, RiskResult])), [risk.data]);
  const visible = useMemo(() => new Set(results.keys()), [results]);
  const filtersOn = q.levels.length > 0 || q.districtIds.length > 0;
  const densityCuts = useMemo(() => quantileCuts(risk.data?.data ?? []), [risk.data]);
  const activeExplanation = explanation.data?.unit_id === q.selectedUnitId && explanation.data?.unit_type === q.unitType
    ? explanation.data : null;
  const influence = useMemo(
    () => new Map((activeExplanation?.saliency ?? []).map(([u, w]) => [u, w] as [string, number])),
    [activeExplanation],
  );
  const influenceStatus = !q.selectedUnitId
    ? "Seleccione una zona para ver su explicación."
    : explanation.loading
      ? "Cargando explicación…"
      : influence.size > 0
        ? "Grad-CAM: celdas con mayor influencia en la estimación anual de " + q.selectedUnitId + " (2024, todas las franjas)."
        : "Sin explicación disponible para esta zona. Disponible en los 43 distritos y las 400 celdas de mayor riesgo de 2024.";
  const maxDensity = useMemo(
    () => Math.max(...(risk.data?.data ?? []).map((r) => (r.observed.events ?? 0) / Math.max(r.unit.area_km2, 0.1)), 0.0001),
    [risk.data],
  );
  const heatWeight = useCallback(
    (id: string): number => {
      if (layer === "influence") return influence.get(id) ?? 0;
      const r = results.get(id);
      if (!r) return 0;
      if (layer === "record") return Math.sqrt(((r.observed.events ?? 0) / Math.max(r.unit.area_km2, 0.1)) / maxDensity);
      return r.risk_index === null ? 0 : r.risk_index / 100;
    },
    [layer, results, influence, maxDensity],
  );
  // With the Grad-CAM layer the grid is drawn in the district view too: a click
  // on a cell then selects its district, which keeps the district explanation.
  const cellDistrict = useMemo(
    () => new Map(units.features.map((f) => [f.properties.unit_id, f.properties.district_id])),
    [units],
  );
  const selectUnit = useCallback(
    (id: string) => q.select(q.unitType === "district" && layer === "influence" ? (cellDistrict.get(id) ?? id) : id),
    [q, layer, cellDistrict],
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
        <Segmented<MapView>
          label="Vista"
          value={view}
          options={[
            { value: "cells", label: "Malla 1 km" },
            { value: "districts", label: "Distritos" },
            { value: "heat", label: "Calor" },
          ]}
          onChange={changeView}
          hint="Malla: celdas de 1 km con las que trabaja la red. Distritos: valores agregados. Calor: superficie continua; pase el cursor por cualquier punto."
        />
        <OptionList<MapLayer>
          label="Qué mostrar"
          value={layer}
          onChange={setLayer}
          options={[
            { value: "risk", label: "Riesgo estimado", description: "Índice de la red CNN-RNN para el periodo" },
            { value: "record", label: "Atropellos registrados", description: "Densidad observada en las fuentes" },
            { value: "influence", label: "Grad-CAM", description: "Qué zonas pesan en la estimación de la zona elegida" },
          ]}
        />
        <div className="rail-section">
          <PeriodPicker years={q.years} value={q.active} onChange={q.setActive} />
          {!periodId && <Notice tone="warn">Este periodo no tiene resultados publicados.</Notice>}
        </div>
        <div className="rail-section">
          <FilterChips<RiskLevel>
            label="Filtrar por nivel"
            selected={q.levels}
            onToggle={q.toggleLevel}
            items={ALL_LEVELS.map((level) => {
              const band = legend.bands.find((b) => b.level === level)!;
              return {
                value: level,
                label: LEVEL_LABEL[level],
                count: counts?.[level],
                swatch: <span className="swatch" style={{ background: colorFor(band.max_index - 1, bands)! }} aria-hidden="true" />,
              };
            })}
          />
          <SearchSelect
            label="Filtrar por distrito"
            options={districtOptions}
            value={q.districtIds[0] ?? null}
            onChange={(id) => q.setDistricts(id ? [id] : [])}
            placeholder="Escriba un distrito"
          />
          {filtersOn ? (
            <div className="active-filters" aria-live="polite">
              <span>
                Mostrando {q.levels.map((l) => LEVEL_LABEL[l].toLowerCase()).join(" y ") || "todos los niveles"} en{" "}
                {q.districtIds.length ? districtOptions.find((d) => d.id === q.districtIds[0])?.name : "los 43 distritos"}
              </span>
              <button type="button" className="btn small" onClick={q.clearFilters}>Quitar filtros</button>
            </div>
          ) : (
            counts && (
              <p className="rail-summary">
                {(counts.high + counts.medium + counts.low).toLocaleString("es-PE")} {q.unitType === "cell" ? "celdas" : "distritos"} con resultado
                {counts.no_result > 0 && `, ${counts.no_result} sin resultado`}
              </p>
            )
          )}
        </div>
        <form className="rail-section search" onSubmit={onSearch} role="search">
          <label htmlFor="unit-search" className="field-label">Ir a una zona</label>
          <input id="unit-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Distrito o celda, ej. F54-C35" />
        </form>
      </aside>

      <main className="map-area">
        {risk.error && <Notice tone="error">No se pudo cargar el riesgo: {risk.error.message}</Notice>}
        {view === "heat" ? (
          <HeatMap
            cells={units}
            scope={districts}
            weight={heatWeight}
            gradient={HEAT_GRADIENT[layer]}
            version={`${layer}|${periodId}|${q.selectedUnitId}|${risk.data ? "1" : "0"}|${explanation.data ? "1" : "0"}`}
            selected={q.selectedUnitId}
            onSelect={(id) => q.select(id)}
            onHover={setHover}
          />
        ) : (
          <RiskMap
            // Grad-CAM maps are cell-level: the grid is drawn even in the district view.
            units={q.unitType === "cell" || layer === "influence" ? units : districts}
            outline={q.unitType === "cell" || layer === "influence" ? districts : undefined}
            scope={districts}
            results={results}
            bands={bands}
            visible={filtersOn && layer === "risk" ? visible : null}
            colorize={layer === "risk" ? undefined : colorize}
            selected={q.selectedUnitId ? [q.selectedUnitId] : []}
            focus={q.selectedUnitId}
            onSelect={selectUnit}
            onHover={(id) => setHover(id)}
            ariaLabel={`Mapa de riesgo por ${q.unitType === "cell" ? "celda" : "distrito"}, ${periodId ?? ""}`}
          />
        )}
        {risk.loading && <div className="map-loading">Cargando…</div>}
        {hovered && (
          <div className="map-tip" role="tooltip">
            <strong>{hovered.unit.unit_type === "cell" ? `Celda ${hovered.unit.unit_id}` : hovered.unit.display_name}</strong>
            <span className="muted">{hovered.unit.district_name}</span>
            <span>
              {layer === "record" ? (
                hovered.observed.events === null ? "Sin registro disponible" : <><b>{hovered.observed.events}</b> registros · {(hovered.observed.events / Math.max(hovered.unit.area_km2, 0.1)).toFixed(2)} /km²</>
              ) : layer === "influence" ? (
                influence.has(hovered.unit.unit_id) ? <><b>{(influence.get(hovered.unit.unit_id)! * 100).toFixed(1)}%</b> de la influencia máxima</> : "Sin atribución mostrada"
              ) : hovered.risk_level ? (
                <>
                  <b>{fmtIndex(hovered.risk_index)}</b> {LEVEL_LABEL[hovered.risk_level]}
                </>
              ) : (
                "Sin resultado"
              )}
            </span>
            <span className="muted small">{layer === "influence" ? "Explicación anual 2024" : periodLabel(hovered.period)}</span>
          </div>
        )}
        <div className="legend-dock">
          {view !== "heat" && layer === "record" && (
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
          {view !== "heat" && layer === "influence" && (
            <section className="legend">
              <strong>Influencia en la estimación (Grad-CAM)</strong>
              <p className="legend-sub">
                {influenceStatus}
              </p>
              <ul className="legend-classes">
                <li><span className="swatch" style={{ background: "#F4F3EF", border: "1px solid var(--line)" }} /> Sin atribución mostrada</li>
                {INFLUENCE_RAMP.map((c, i) => (
                  <li key={c}><span className="swatch" style={{ background: c }} /> {i * 20} a {(i + 1) * 20} % de la máxima</li>
                ))}
              </ul>
            </section>
          )}
          {view === "heat" && (
            <section className="legend">
              <strong>Mapa de calor</strong>
              <p className="legend-sub">{layer === "risk" ? "Índice de riesgo estimado (0 a 100)" : layer === "record" ? "Atropellos registrados por km²" : "Influencia Grad-CAM"}</p>
              <div style={{ height: 12, borderRadius: 6, background: heatLegend(HEAT_GRADIENT[layer]) }} />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}><span>Bajo</span><span>Alto</span></div>
              {layer === "record" && <p className="legend-sub">Escala relativa a la densidad máxima visible: {maxDensity > 0.0001 ? maxDensity.toFixed(2) : "0"} eventos/km². La ausencia de color no demuestra ausencia de atropellos.</p>}
              {layer === "influence" && <p className="legend-sub">{influenceStatus} Se muestran hasta las 40 celdas de mayor influencia, respecto a la máxima.</p>}
              <p className="legend-sub">Superficie interpolada de la malla de 1 km. Consulte la celda para su valor exacto.</p>
            </section>
          )}
          {view !== "heat" && layer === "risk" && <Legend
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
