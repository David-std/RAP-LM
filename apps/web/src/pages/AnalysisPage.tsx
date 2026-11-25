// Analyst tools (extends EP-01, EP-03, EP-04 within scope: consultation only,
// no intervention recommendation, RG-03). Every table can be exported with
// its run, period and scope notice.
//
// * Ranking       - sortable/searchable table of the active period (RF-02, RF-04)
// * Change        - difference of index between two periods for every unit (RF-06)
// * Persistence   - years in high level across the published series (RF-06)
// * Districts     - level distribution of cells inside each district (RF-01, RF-04)

import { useCallback, useMemo, useState } from "react";

import { api } from "../api/client";
import type { Legend as LegendDto, Meta, RiskResult, SeriesUnit, UnitCollection } from "../api/types";
import { useApi } from "../api/useApi";
import { Notice, PeriodPicker, Segmented } from "../components/Controls";
import { RiskMap } from "../components/RiskMap";
import { exportCsv, exportGeoJson, type ExportColumn } from "../lib/export";
import { BANDS, DAY_LABEL, fmtCount, fmtIndex, fmtValue } from "../lib/format";
import { classBands, colorFor, LEVEL_LABEL, type ClassBand } from "../lib/levels";
import { useQuery } from "../state/QueryContext";

type Tool = "ranking" | "change" | "persistence" | "districts";
const EMPTY = new Map<string, RiskResult>();

interface Props {
  units: UnitCollection;
  districts: UnitCollection;
  legend: LegendDto;
  meta: Meta;
  openUnit: (unitId: string) => void;
}

export function AnalysisPage(props: Props) {
  const q = useQuery();
  const [tool, setTool] = useState<Tool>("ranking");
  const bands = useMemo(() => classBands(props.legend), [props.legend]);
  return (
    <div className="workspace compare">
      <aside className="rail" aria-label="Herramientas de análisis">
        <h2 className="rail-title">Análisis</h2>
        <Segmented<Tool>
          label="Herramienta"
          hint="Ranking: ordena todas las zonas del periodo por índice, indicador o registro; respeta los filtros del mapa. Cambio: diferencia de índice de cada zona entre dos periodos. Persistencia: cuántos años publicados estuvo cada zona en nivel alto, para el mismo tipo de día y franja. Distritos: cuántas celdas de cada distrito están en cada nivel."
          wrap
          value={tool}
          options={[
            { value: "ranking", label: "Ranking" },
            { value: "change", label: "Cambio" },
            { value: "persistence", label: "Persistencia" },
            { value: "districts", label: "Distritos" },
          ]}
          onChange={setTool}
        />
        {tool !== "districts" && (
          <Segmented
            label="Unidad de análisis"
            value={q.unitType}
            options={[
              { value: "cell", label: "Celda de 1 km" },
              { value: "district", label: "Distrito" },
            ]}
            onChange={q.setUnitType}
          />
        )}
        {tool === "change" ? (
          <>
            <PeriodPicker years={q.years} value={q.periodA} onChange={q.setPeriodA} title={<p className="field-label"><span className="badge">A</span> Periodo inicial</p>} />
            <PeriodPicker years={q.years} value={q.periodB} onChange={q.setPeriodB} title={<p className="field-label"><span className="badge">B</span> Periodo final</p>} />
          </>
        ) : tool === "persistence" ? (
          <PeriodPicker
            years={q.years}
            value={q.active}
            onChange={q.setActive}
            title={<p className="field-label">Tipo de día y franja (se usan todos los años)</p>}
          />
        ) : (
          <PeriodPicker years={q.years} value={q.active} onChange={q.setActive} />
        )}
      </aside>
      <main className="analysis-main">
        {tool === "ranking" && <Ranking {...props} bands={bands} />}
        {tool === "change" && <Change {...props} bands={bands} />}
        {tool === "persistence" && <Persistence {...props} bands={bands} />}
        {tool === "districts" && <Districts {...props} bands={bands} />}
      </main>
    </div>
  );
}


type Sort = { key: string; dir: 1 | -1 };

function useSorted<T>(rows: T[], sort: Sort, get: Record<string, (r: T) => number | string | null>) {
  return useMemo(() => {
    const fn = get[sort.key];
    return [...rows].sort((a, b) => {
      const va = fn(a);
      const vb = fn(b);
      if (va === null) return 1; // nulls (no result) always last
      if (vb === null) return -1;
      return (va < vb ? -1 : va > vb ? 1 : 0) * sort.dir;
    });
  }, [rows, sort, get]);
}

function SortTh({ label, k, sort, setSort }: { label: string; k: string; sort: Sort; setSort: (s: Sort) => void }) {
  const active = sort.key === k;
  return (
    <th scope="col" aria-sort={active ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <button type="button" className="sort-btn" onClick={() => setSort({ key: k, dir: active ? (-sort.dir as 1 | -1) : -1 })}>
        {label} {active ? (sort.dir === 1 ? "▲" : "▼") : ""}
      </button>
    </th>
  );
}

// ------------------------------------------------------------------ ranking
function Ranking({ meta, units, districts, bands, openUnit }: Props & { bands: ClassBand[] }) {
  const q = useQuery();
  const periodId = q.periodId(q.active);
  const [text, setText] = useState("");
  const [limit, setLimit] = useState(50);
  const [sort, setSort] = useState<Sort>({ key: "index", dir: -1 });
  const risk = useApi(
    (s) => api.risk({ periodId: periodId!, unitType: q.unitType, districtIds: q.districtIds, levels: q.levels }, s),
    [periodId, q.unitType, q.districtIds.join(), q.levels.join()],
    !!periodId,
  );
  const rows = useMemo(() => {
    const t = text.trim().toUpperCase();
    return (risk.data?.data ?? []).filter(
      (r) => !t || r.unit.unit_id.toUpperCase().includes(t) || r.unit.district_name.toUpperCase().includes(t),
    );
  }, [risk.data, text]);
  const getters = useMemo(
    () => ({
      unit: (r: RiskResult) => r.unit.unit_id,
      district: (r: RiskResult) => r.unit.district_name,
      index: (r: RiskResult) => r.risk_index,
      value: (r: RiskResult) => r.indicator_value,
      hist: (r: RiskResult) => r.historical_average,
      observed: (r: RiskResult) => r.observed.events,
    }),
    [],
  );
  const sorted = useSorted(rows, sort, getters);
  const columns: ExportColumn<RiskResult>[] = [
    { header: "rank", value: (r) => sorted.indexOf(r) + 1 },
    { header: "unit_id", value: (r) => r.unit.unit_id },
    { header: "unit_type", value: (r) => r.unit.unit_type },
    { header: "district_id", value: (r) => r.unit.district_id },
    { header: "district_name", value: (r) => r.unit.district_name },
    { header: "period_id", value: (r) => r.period.period_id },
    { header: "risk_index", value: (r) => r.risk_index },
    { header: "risk_level", value: (r) => r.risk_level },
    { header: "indicator_value", value: (r) => r.indicator_value },
    { header: "historical_average", value: (r) => r.historical_average },
    { header: "observed_events", value: (r) => r.observed.events },
    { header: "observed_injured", value: (r) => r.observed.pedestrians_injured },
    { header: "observed_deceased", value: (r) => r.observed.pedestrians_deceased },
    { header: "availability", value: (r) => r.availability },
  ];
  const context = `period ${periodId}; filters levels=${q.levels.join("|") || "all"} districts=${q.districtIds.join("|") || "all"}`;
  const geo = q.unitType === "cell" ? units : districts;

  return (
    <section className="analysis-panel">
      <header className="analysis-head">
        <h2>
          Ranking de {q.unitType === "cell" ? "celdas" : "distritos"}{" "}
          <span className="muted">
            {q.active.year}, {DAY_LABEL[q.active.dayType].toLowerCase()}, {BANDS[q.active.band]}
          </span>
        </h2>
        <div className="toolbar">
          <input aria-label="Buscar en el ranking" placeholder="Buscar celda o distrito" value={text} onChange={(e) => setText(e.target.value)} />
          <button type="button" className="btn" disabled={!sorted.length} onClick={() => exportCsv(`rap-lm-ranking-${periodId}`, sorted, columns, meta, context)}>
            Exportar CSV
          </button>
          <button
            type="button"
            className="btn"
            disabled={!sorted.length}
            onClick={() =>
              exportGeoJson(
                `rap-lm-ranking-${periodId}`,
                geo,
                new Map(sorted.map((r) => [r.unit.unit_id, rowObject(r, columns)])),
                meta,
                context,
              )
            }
          >
            Exportar GeoJSON
          </button>
        </div>
      </header>
      {risk.error && <Notice tone="error">{risk.error.message}</Notice>}
      {risk.loading && <Notice>Cargando…</Notice>}
      {(q.levels.length > 0 || q.districtIds.length > 0) && (
        <Notice>Filtros del mapa activos: {q.levels.map((l) => LEVEL_LABEL[l]).join(", ") || "todos los niveles"}; {q.districtIds.length ? q.districtIds.join(", ") : "todos los distritos"}.</Notice>
      )}
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">#</th>
              <SortTh label="Unidad" k="unit" sort={sort} setSort={setSort} />
              <SortTh label="Distrito" k="district" sort={sort} setSort={setSort} />
              <SortTh label="Índice" k="index" sort={sort} setSort={setSort} />
              <th scope="col">Nivel</th>
              <SortTh label="Indicador" k="value" sort={sort} setSort={setSort} />
              <SortTh label="Prom. histórico" k="hist" sort={sort} setSort={setSort} />
              <SortTh label="Atropellos registrados" k="observed" sort={sort} setSort={setSort} />
              <th scope="col"><span className="sr-only">Acción</span></th>
            </tr>
          </thead>
          <tbody>
            {sorted.slice(0, limit).map((r, i) => (
              <tr key={r.unit.unit_id}>
                <td className="num">{i + 1}</td>
                <th scope="row">{r.unit.unit_type === "cell" ? r.unit.unit_id : r.unit.display_name}</th>
                <td>{r.unit.district_name}</td>
                <td className="num">{fmtIndex(r.risk_index)}</td>
                <td><LevelCell r={r} bands={bands} /></td>
                <td className="num">{fmtValue(r.indicator_value)}</td>
                <td className="num">{fmtValue(r.historical_average)}</td>
                <td className="num">{fmtCount(r.observed.events)}</td>
                <td>
                  <button type="button" className="link-btn small" onClick={() => openUnit(r.unit.unit_id)}>
                    Ver en mapa
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sorted.length > limit && (
        <button type="button" className="btn" onClick={() => setLimit(limit + 100)}>
          Mostrar más ({sorted.length - limit} restantes)
        </button>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ change
interface ChangeRow {
  unit_id: string;
  name: string;
  district: string;
  a: number | null;
  b: number | null;
  delta: number | null;
  levelA: string | null;
  levelB: string | null;
}

const DIVERGING = (d: number | null) =>
  d === null ? null : d >= 20 ? "#7E1F22" : d >= 8 ? "#E0664D" : d > -8 ? "#EFEFEC" : d > -20 ? "#7FA3E6" : "#1C3E9E";

function Change({ meta, units, districts, openUnit }: Props & { bands: ClassBand[] }) {
  const q = useQuery();
  const idA = q.periodId(q.periodA);
  const idB = q.periodId(q.periodB);
  const [sort, setSort] = useState<Sort>({ key: "delta", dir: -1 });
  const a = useApi((s) => api.risk({ periodId: idA!, unitType: q.unitType }, s), [idA, q.unitType], !!idA);
  const b = useApi((s) => api.risk({ periodId: idB!, unitType: q.unitType }, s), [idB, q.unitType], !!idB);
  const rows: ChangeRow[] = useMemo(() => {
    if (!a.data || !b.data) return [];
    const mapA = new Map(a.data.data.map((r) => [r.unit.unit_id, r]));
    return b.data.data.map((rb) => {
      const ra = mapA.get(rb.unit.unit_id);
      const va = ra?.risk_index ?? null;
      const vb = rb.risk_index;
      return {
        unit_id: rb.unit.unit_id,
        name: rb.unit.unit_type === "cell" ? rb.unit.unit_id : rb.unit.display_name,
        district: rb.unit.district_name,
        a: va,
        b: vb,
        delta: va === null || vb === null ? null : vb - va,
        levelA: ra?.risk_level ?? null,
        levelB: rb.risk_level,
      };
    });
  }, [a.data, b.data]);
  const sorted = useSorted(rows, sort, useMemo(() => ({ delta: (r: ChangeRow) => r.delta, name: (r: ChangeRow) => r.name, b: (r: ChangeRow) => r.b }), []));
  const summary = useMemo(() => {
    const valid = rows.filter((r) => r.levelA && r.levelB);
    const order = { low: 0, medium: 1, high: 2 } as Record<string, number>;
    return {
      up: valid.filter((r) => order[r.levelB!] > order[r.levelA!]).length,
      same: valid.filter((r) => r.levelB === r.levelA).length,
      down: valid.filter((r) => order[r.levelB!] < order[r.levelA!]).length,
      none: rows.length - valid.length,
    };
  }, [rows]);
  const deltaColor = useMemo(() => new Map(rows.map((r) => [r.unit_id, DIVERGING(r.delta)])), [rows]);
  const colorize = useCallback((id: string) => deltaColor.get(id) ?? null, [deltaColor]);
  const geo = q.unitType === "cell" ? units : districts;
  const columns: ExportColumn<ChangeRow>[] = [
    { header: "unit_id", value: (r) => r.unit_id },
    { header: "district", value: (r) => r.district },
    { header: `index_${idA}`, value: (r) => r.a },
    { header: `index_${idB}`, value: (r) => r.b },
    { header: "index_change", value: (r) => r.delta },
    { header: `level_${idA}`, value: (r) => r.levelA },
    { header: `level_${idB}`, value: (r) => r.levelB },
  ];

  if (idA && idA === idB) return <Notice tone="warn">Elija dos periodos distintos.</Notice>;
  return (
    <section className="analysis-panel split">
      <div className="map-area">
        <div className="map-chip">
          <strong>Cambio de índice {idA} → {idB}</strong>
          <span className="muted small">Rojo sube, azul baja, gris ±8 puntos; trama = sin resultado en algún periodo</span>
        </div>
        <RiskMap
          units={geo}
          outline={q.unitType === "cell" ? districts : undefined}
          scope={districts}
          results={EMPTY}
          bands={[]}
          colorize={colorize}
          onSelect={openUnit}
          ariaLabel="Mapa de cambio de índice entre periodos"
        />
      </div>
      <div className="side-table">
        <div className="toolbar">
          <span>
            Suben de nivel <b>{summary.up}</b>, mantienen <b>{summary.same}</b>, bajan <b>{summary.down}</b>
            {summary.none > 0 && `, sin comparación ${summary.none}`}
          </span>
          <button type="button" className="btn small" disabled={!rows.length} onClick={() => exportCsv(`rap-lm-cambio-${idA}-${idB}`, sorted, columns, meta, `change ${idA} -> ${idB}`)}>
            CSV
          </button>
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <SortTh label="Unidad" k="name" sort={sort} setSort={setSort} />
                <th scope="col">A</th>
                <SortTh label="B" k="b" sort={sort} setSort={setSort} />
                <SortTh label="Cambio" k="delta" sort={sort} setSort={setSort} />
              </tr>
            </thead>
            <tbody>
              {sorted.slice(0, 200).map((r) => (
                <tr key={r.unit_id}>
                  <th scope="row">
                    <button type="button" className="link-btn" onClick={() => openUnit(r.unit_id)}>{r.name}</button>
                    <div className="muted small">{r.district}</div>
                  </th>
                  <td className="num">{fmtIndex(r.a)}</td>
                  <td className="num">{fmtIndex(r.b)}</td>
                  <td className="num">{r.delta === null ? "n/a" : `${r.delta > 0 ? "+" : ""}${Math.round(r.delta)}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ persistence
const PERSIST = ["#F4F4F1", "#F8CBB8", "#F09A80", "#E0664D", "#BF3A2E", "#7E1F22"];

function Persistence({ meta, units, districts, openUnit }: Props & { bands: ClassBand[] }) {
  const q = useQuery();
  const series = useApi(
    (s) => api.series({ unitType: q.unitType, dayType: q.active.dayType, band: q.active.band }, s),
    [q.unitType, q.active.dayType, q.active.band],
  );
  const rows = useMemo(
    () =>
      (series.data?.units ?? [])
        .map((u) => ({
          u,
          high: u.risk_level.filter((l) => l === "high").length,
          observed: u.risk_level.filter((l) => l !== null).length,
          mean: mean(u.risk_index),
        }))
        .sort((x, y) => y.high - x.high || (y.mean ?? 0) - (x.mean ?? 0)),
    [series.data],
  );
  const years = series.data?.years ?? [];
  const byId = useMemo(() => new Map(rows.map((r) => [r.u.unit_id, r])), [rows]);
  const geo = q.unitType === "cell" ? units : districts;
  const colorOf = useCallback(
    (id: string) => {
      const r = byId.get(id);
      if (!r || !r.observed) return null;
      return PERSIST[Math.min(5, Math.round((r.high / r.observed) * 5))];
    },
    [byId],
  );
  const columns: ExportColumn<(typeof rows)[number]>[] = [
    { header: "unit_id", value: (r) => r.u.unit_id },
    { header: "district_id", value: (r) => r.u.district_id },
    { header: "years_high", value: (r) => r.high },
    { header: "years_with_result", value: (r) => r.observed },
    { header: "mean_index", value: (r) => r.mean },
    ...years.map((y, i) => ({ header: `index_${y}`, value: (r: (typeof rows)[number]) => r.u.risk_index[i] })),
  ];
  return (
    <section className="analysis-panel split">
      <div className="map-area">
        <div className="map-chip">
          <strong>Años en nivel alto, {DAY_LABEL[q.active.dayType].toLowerCase()} {BANDS[q.active.band]}</strong>
          <span className="muted small">Años publicados: {years.join(", ")}</span>
        </div>
        {series.error && <Notice tone="error">{series.error.message}</Notice>}
        <RiskMap
          units={geo}
          outline={q.unitType === "cell" ? districts : undefined}
          scope={districts}
          results={EMPTY}
          bands={[]}
          colorize={colorOf}
          onSelect={openUnit}
          ariaLabel="Mapa de persistencia del nivel alto"
        />
        <div className="legend-dock">
          <section className="legend">
            <strong>Proporción de años en alto</strong>
            <ul className="legend-classes">
              {PERSIST.map((c, i) => (
                <li key={c}>
                  <span className="swatch" style={{ background: c }} aria-hidden="true" /> {i === 0 ? "Nunca" : `≈ ${i * 20} %`}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
      <div className="side-table">
        <div className="toolbar">
          <span>{rows.filter((r) => r.high === r.observed && r.observed > 0).length} unidades en alto todos los años</span>
          <button type="button" className="btn small" disabled={!rows.length} onClick={() => exportCsv(`rap-lm-persistencia-${q.active.dayType}-${q.active.band}`, rows, columns, meta, `persistence ${q.active.dayType} band ${q.active.band}`)}>
            CSV
          </button>
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Unidad</th>
                <th scope="col">Años alto</th>
                <th scope="col">Serie</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 200).map((r) => (
                <tr key={r.u.unit_id}>
                  <th scope="row">
                    <button type="button" className="link-btn" onClick={() => openUnit(r.u.unit_id)}>{r.u.display_name}</button>
                  </th>
                  <td className="num">{r.high} / {r.observed}</td>
                  <td><Spark u={r.u} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function Spark({ u }: { u: SeriesUnit }) {
  return (
    <span className="spark" aria-label={`Índices: ${u.risk_index.map((v) => (v === null ? "sin resultado" : Math.round(v))).join(", ")}`}>
      {u.risk_index.map((v, i) => (
        <span key={i} className={v === null ? "hatch" : ""} style={{ height: `${Math.max(v ?? 100, 4) * 0.22}px`, background: v === null ? undefined : v >= 70 ? "#BF3A2E" : v >= 40 ? "#F09A80" : "#D6D6D2" }} />
      ))}
    </span>
  );
}

// ------------------------------------------------------------------ districts
function Districts({ meta, districts, bands, openUnit }: Props & { bands: ClassBand[] }) {
  const q = useQuery();
  const periodId = q.periodId(q.active);
  const cells = useApi((s) => api.risk({ periodId: periodId!, unitType: "cell" }, s), [periodId], !!periodId);
  const dist = useApi((s) => api.risk({ periodId: periodId!, unitType: "district" }, s), [periodId], !!periodId);
  const rows = useMemo(() => {
    const agg = new Map<string, { low: number; medium: number; high: number; none: number }>();
    for (const r of cells.data?.data ?? []) {
      const a = agg.get(r.unit.district_id) ?? { low: 0, medium: 0, high: 0, none: 0 };
      a[r.risk_level ?? "none"] += 1;
      agg.set(r.unit.district_id, a);
    }
    return (dist.data?.data ?? [])
      .map((d) => ({ d, c: agg.get(d.unit.district_id) ?? { low: 0, medium: 0, high: 0, none: 0 } }))
      .sort((x, y) => (y.d.risk_index ?? -1) - (x.d.risk_index ?? -1));
  }, [cells.data, dist.data]);
  const columns: ExportColumn<(typeof rows)[number]>[] = [
    { header: "district_id", value: (r) => r.d.unit.district_id },
    { header: "district_name", value: (r) => r.d.unit.display_name },
    { header: "district_index", value: (r) => r.d.risk_index },
    { header: "district_level", value: (r) => r.d.risk_level },
    { header: "cells_high", value: (r) => r.c.high },
    { header: "cells_medium", value: (r) => r.c.medium },
    { header: "cells_low", value: (r) => r.c.low },
    { header: "cells_no_result", value: (r) => r.c.none },
    { header: "observed_events", value: (r) => r.d.observed.events },
  ];
  return (
    <section className="analysis-panel">
      <header className="analysis-head">
        <h2>
          Perfil distrital <span className="muted">{periodId}</span>
        </h2>
        <button type="button" className="btn" disabled={!rows.length} onClick={() => exportCsv(`rap-lm-distritos-${periodId}`, rows, columns, meta, `districts ${periodId}`)}>
          Exportar CSV
        </button>
      </header>
      {(cells.loading || dist.loading) && <Notice>Cargando…</Notice>}
      <p className="muted small">
        El índice distrital agrega intensidades de sus celdas (nunca promedia etiquetas). Las barras muestran cuántas celdas del distrito están en cada nivel.
      </p>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Distrito</th>
              <th scope="col">Índice distrital</th>
              <th scope="col">Nivel</th>
              <th scope="col">Celdas por nivel (alto / medio / bajo)</th>
              <th scope="col">Atropellos registrados</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ d, c }) => {
              const total = c.high + c.medium + c.low + c.none || 1;
              return (
                <tr key={d.unit.unit_id}>
                  <th scope="row">
                    <button type="button" className="link-btn" onClick={() => { q.setUnitType("district"); openUnit(d.unit.unit_id); }}>
                      {d.unit.display_name}
                    </button>
                  </th>
                  <td className="num">{fmtIndex(d.risk_index)}</td>
                  <td><LevelCell r={d} bands={bands} /></td>
                  <td>
                    <span className="stack" aria-label={`${c.high} alto, ${c.medium} medio, ${c.low} bajo, ${c.none} sin resultado`}>
                      <span style={{ width: `${(c.high / total) * 100}%`, background: "#BF3A2E" }} />
                      <span style={{ width: `${(c.medium / total) * 100}%`, background: "#F09A80" }} />
                      <span style={{ width: `${(c.low / total) * 100}%`, background: "#F8CBB8" }} />
                      <span className="hatch" style={{ width: `${(c.none / total) * 100}%` }} />
                    </span>
                    <span className="muted small"> {c.high} / {c.medium} / {c.low}</span>
                  </td>
                  <td className="num">{fmtCount(d.observed.events)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function LevelCell({ r, bands }: { r: RiskResult; bands: ClassBand[] }) {
  if (!r.risk_level) return <span className="muted">Sin resultado</span>;
  return (
    <span className="level-tag">
      <span className="swatch" style={{ background: colorFor(r.risk_index, bands)! }} aria-hidden="true" />
      {LEVEL_LABEL[r.risk_level]}
    </span>
  );
}

function rowObject<T>(row: T, columns: ExportColumn<T>[]): Record<string, unknown> {
  return Object.fromEntries(columns.map((c) => [c.header, c.value(row)]));
}

function mean(values: (number | null)[]): number | null {
  const v = values.filter((x): x is number => x !== null);
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
}
