// Map workspace: EP-01 (map, legend, view), EP-02 (detail), EP-03 (period,
// filters). Filters are applied by the API (RF-04); units outside the filtered
// subset are drawn faded, units without result are hatched (HU-21).

import { useMemo, useState } from "react";

import { api } from "../api/client";
import type { Legend as LegendDto, RiskLevel, RiskResult, UnitCollection } from "../api/types";
import { useApi } from "../api/useApi";
import { Notice, PeriodPicker, Segmented } from "../components/Controls";
import { DetailPanel } from "../components/DetailPanel";
import { Legend } from "../components/Legend";
import { RiskMap } from "../components/RiskMap";
import { Timeline } from "../components/Timeline";
import { BANDS, DAY_LABEL, fmtIndex, periodLabel } from "../lib/format";
import { classBands, colorFor, LEVEL_LABEL } from "../lib/levels";
import { ALL_LEVELS, useQuery } from "../state/QueryContext";

interface Props {
  units: UnitCollection;
  districts: UnitCollection;
  legend: LegendDto;
  goCompare: (mode: "spatial" | "temporal") => void;
}

export function MapPage({ units, districts, legend, goCompare }: Props) {
  const q = useQuery();
  const bands = useMemo(() => classBands(legend), [legend]);
  const periodId = q.periodId(q.active);
  const [hover, setHover] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const risk = useApi(
    (s) => api.risk({ periodId: periodId!, unitType: q.unitType, districtIds: q.districtIds, levels: q.levels }, s),
    [periodId, q.unitType, q.districtIds.join(), q.levels.join()],
    !!periodId,
  );
  // Selected unit is fetched on its own so it stays visible even when filtered out (HU-08).
  const selected = useApi(
    (s) => api.risk({ periodId: periodId!, unitType: q.unitType, unitId: q.selectedUnitId! }, s),
    [periodId, q.unitType, q.selectedUnitId],
    !!periodId && !!q.selectedUnitId,
  );

  const results = useMemo(() => {
    const m = new Map<string, RiskResult>();
    risk.data?.data.forEach((r) => m.set(r.unit.unit_id, r));
    return m;
  }, [risk.data]);
  const visible = useMemo(() => new Set(results.keys()), [results]);
  const mapUnits = q.unitType === "cell" ? units : districts;
  const hovered = hover ? results.get(hover) : undefined;
  const filtersOn = q.levels.length > 0 || q.districtIds.length > 0;
  const counts = risk.data?.counts;
  const districtOptions = useMemo(
    () =>
      districts.features
        .map((f) => ({ id: f.properties.unit_id, name: f.properties.display_name }))
        .sort((a, b) => a.name.localeCompare(b.name, "es")),
    [districts],
  );

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    const term = search.trim().toUpperCase();
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
        <h2 className="rail-title">Consulta</h2>
        <PeriodPicker years={q.years} value={q.active} onChange={q.setActive} />
        {!periodId && <Notice tone="warn">Este periodo no tiene resultados publicados.</Notice>}

        <fieldset className="filter">
          <legend className="field-label" title="Muestra solo las unidades del nivel elegido. Sin selección se muestran todas.">
            Nivel de riesgo
          </legend>
          {ALL_LEVELS.map((level: RiskLevel) => {
            const band = legend.bands.find((b) => b.level === level)!;
            return (
              <label key={level} className="check-row">
                <input type="checkbox" checked={q.levels.includes(level)} onChange={() => q.toggleLevel(level)} />
                <span className="swatch-pair" aria-hidden="true">
                  <span style={{ background: colorFor(band.min_index, bands)! }} />
                  <span style={{ background: colorFor(band.max_index - 1, bands)! }} />
                </span>
                {LEVEL_LABEL[level]} {band.min_index} a {level === "high" ? 100 : band.max_index - 1}
                <span className="count">{counts ? counts[level].toLocaleString("es-PE") : "…"}</span>
              </label>
            );
          })}
          <p className="muted small">
            {q.unitType === "cell" ? "Celdas" : "Distritos"} por nivel en el periodo activo
            {counts && counts.no_result > 0 && `; ${counts.no_result} sin resultado`}
          </p>
        </fieldset>

        <label className="field-label" htmlFor="district-filter" title="Filtra por jurisdicción (43 distritos de Lima, sin Callao)">
          Distrito
        </label>
        <select
          id="district-filter"
          className="select"
          value={q.districtIds[0] ?? ""}
          onChange={(e) => q.setDistricts(e.target.value ? [e.target.value] : [])}
        >
          <option value="">Los 43 distritos</option>
          {districtOptions.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>

        {filtersOn && (
          <div className="active-filters" aria-live="polite">
            <span>
              Filtros: {q.levels.map((l) => LEVEL_LABEL[l]).join(", ") || "todos los niveles"};{" "}
              {q.districtIds.length ? districtOptions.find((d) => d.id === q.districtIds[0])?.name : "todos los distritos"}
            </span>
            <button type="button" className="btn small" onClick={q.clearFilters}>
              Quitar filtros
            </button>
          </div>
        )}

        <Segmented
          label="Unidad de análisis"
          value={q.unitType}
          options={[
            { value: "cell", label: "Celda de 1 km" },
            { value: "district", label: "Distrito" },
          ]}
          onChange={q.setUnitType}
        />

        <form className="search" onSubmit={onSearch} role="search">
          <label htmlFor="unit-search" className="sr-only">
            Buscar distrito o celda
          </label>
          <input
            id="unit-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar distrito o celda (F54-C35)"
          />
        </form>
      </aside>

      <main className="map-area">
        {risk.error && <Notice tone="error">No se pudo cargar el riesgo: {risk.error.message}</Notice>}
        <RiskMap
          units={mapUnits}
          outline={q.unitType === "cell" ? districts : undefined}
          results={results}
          bands={bands}
          visible={filtersOn ? visible : null}
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
          <Legend
            legend={legend}
            bands={bands}
            title={`Riesgo por ${q.unitType === "cell" ? "celda de 1 km" : "distrito"}`}
            subtitle={`${q.active.year}, ${DAY_LABEL[q.active.dayType].toLowerCase()}, ${BANDS[q.active.band]}. Escala común a todos los periodos.`}
          />
        </div>
        <Timeline bands={bands} />
      </main>

      <DetailPanel
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
      />
    </div>
  );
}
