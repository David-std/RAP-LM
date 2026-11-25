// Comparators (RF-05, RF-06; HU-12, HU-17..HU-21). Spatial comparison always
// uses the shared active period, so changing it updates the comparison too.

import { useMemo } from "react";

import { api } from "../api/client";
import type { Comparison, Legend as LegendDto, RiskResult, UnitCollection } from "../api/types";
import { useApi } from "../api/useApi";
import { InfoTip, Notice, PeriodPicker, Segmented } from "../components/Controls";
import { RiskMap } from "../components/RiskMap";
import { fmtCount, fmtIndex, fmtValue, periodLabel } from "../lib/format";
import { classBands, colorFor, LEVEL_LABEL, type ClassBand } from "../lib/levels";
import { MAX_COMPARE, useQuery } from "../state/QueryContext";

const LETTERS = ["A", "B", "C", "D"];

interface Props {
  units: UnitCollection;
  districts: UnitCollection;
  legend: LegendDto;
}

export function ComparePage({ units, districts, legend }: Props) {
  const q = useQuery();
  const bands = useMemo(() => classBands(legend), [legend]);
  return (
    <div className="workspace compare">
      <aside className="rail" aria-label="Comparar">
        <h2 className="rail-title">Comparar</h2>
        <Segmented
          label="Modo"
          value={q.compareMode}
          options={[
            { value: "spatial", label: "Zonas en un periodo" },
            { value: "temporal", label: "Zona entre periodos" },
          ]}
          onChange={q.setCompareMode}
        />
        <Segmented
          label="Unidad de análisis"
          value={q.unitType}
          options={[
            { value: "cell", label: "Celda de 1 km" },
            { value: "district", label: "Distrito" },
          ]}
          onChange={q.setUnitType}
          hint="Celdas y distritos usan escalas distintas: no se comparan entre sí."
        />
        {q.compareMode === "spatial" ? <SpatialControls districts={districts} /> : <TemporalControls units={units} districts={districts} />}
      </aside>
      {q.compareMode === "spatial" ? (
        <SpatialView units={units} districts={districts} bands={bands} />
      ) : (
        <TemporalView units={units} districts={districts} bands={bands} />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ spatial
function SpatialControls({ districts }: { districts: UnitCollection }) {
  const q = useQuery();
  return (
    <>
      <PeriodPicker
        years={q.years}
        value={q.active}
        onChange={q.setActive}
        title={<p className="field-label">Periodo, el mismo para todas</p>}
      />
      <div className="zones">
        <p className="field-label">
          Zonas <span className="muted">{q.compareUnitIds.length} de {MAX_COMPARE}</span>
        </p>
        <ol className="zone-list">
          {q.compareUnitIds.map((id, i) => (
            <li key={id}>
              <span className="badge">{LETTERS[i]}</span>
              <span className="zone-name">{unitName(id, q.unitType, districts)}</span>
              <button type="button" className="icon-btn" aria-label={`Quitar ${id}`} onClick={() => q.removeCompareUnit(id)}>
                ×
              </button>
            </li>
          ))}
        </ol>
        {q.compareUnitIds.length < MAX_COMPARE && q.unitType === "district" && (
          <select
            className="select"
            aria-label="Añadir distrito"
            value=""
            onChange={(e) => e.target.value && q.addCompareUnit(e.target.value)}
          >
            <option value="">+ Añadir distrito</option>
            {districts.features
              .filter((f) => !q.compareUnitIds.includes(f.properties.unit_id))
              .sort((a, b) => a.properties.display_name.localeCompare(b.properties.display_name, "es"))
              .map((f) => (
                <option key={f.properties.unit_id} value={f.properties.unit_id}>
                  {f.properties.display_name}
                </option>
              ))}
          </select>
        )}
        <p className="muted small">Haga clic en el mapa para añadir {q.unitType === "cell" ? "una celda" : "un distrito"}.</p>
      </div>
    </>
  );
}

function SpatialView({ units, districts, bands }: { units: UnitCollection; districts: UnitCollection; bands: ClassBand[] }) {
  const q = useQuery();
  const periodId = q.periodId(q.active);
  const cmp = useApi(
    (s) => api.compareSpatial(q.unitType, q.compareUnitIds, periodId!, s),
    [q.unitType, q.compareUnitIds.join(), periodId],
    !!periodId && q.compareUnitIds.length >= 2,
  );
  const map = useApi(
    (s) => api.risk({ periodId: periodId!, unitType: q.unitType }, s),
    [periodId, q.unitType],
    !!periodId,
  );
  const results = useMemo(() => toMap(map.data?.data), [map.data]);
  const labels = useMemo(() => new Map(q.compareUnitIds.map((id, i) => [id, LETTERS[i]])), [q.compareUnitIds]);

  return (
    <main className="compare-main">
      <div className="map-area">
        <div className="map-chip">
          <strong>{periodId ? periodLabel({ year: q.active.year, day_type: q.active.dayType, time_band: q.active.band }) : "Periodo sin resultados"}</strong>
          <span className="muted small">Mismo periodo, corrida y escala para todas las zonas</span>
        </div>
        <RiskMap
          units={q.unitType === "cell" ? units : districts}
          outline={q.unitType === "cell" ? districts : undefined}
          scope={districts}
          results={results}
          bands={bands}
          selected={q.compareUnitIds}
          labels={labels}
          onSelect={q.addCompareUnit}
          ariaLabel="Mapa para elegir zonas a comparar"
        />
      </div>
      <section className="compare-bottom">
        {q.compareUnitIds.length < 2 && <Notice>Elija al menos dos zonas para comparar.</Notice>}
        {cmp.error && <Notice tone="error">{cmp.error.message}</Notice>}
        {cmp.data && <SpatialTable cmp={cmp.data} bands={bands} />}
      </section>
    </main>
  );
}

function SpatialTable({ cmp, bands }: { cmp: Comparison; bands: ClassBand[] }) {
  return (
    <div className="compare-grid">
      <div className="scale-block">
        <h3>Posición en la escala común <InfoTip text="Todas las zonas se ubican en la misma escala de 0 a 100 del periodo elegido, por lo que sus índices son directamente comparables." /></h3>
        <div className="index-bar wide" aria-hidden="true">
          <div className="index-scale">
            {bands.map((b) => (
              <span key={b.min} style={{ background: b.color, flex: b.max - b.min }} />
            ))}
          </div>
          {cmp.items.map((it, i) =>
            it.result.risk_index === null ? null : (
              <span key={i} className="badge floating" style={{ left: `${it.result.risk_index}%` }}>
                {LETTERS[i]}
              </span>
            ),
          )}
        </div>
        {!cmp.comparable && <Notice tone="warn">{cmp.reason}</Notice>}
        {cmp.comparable && cmp.reason && <Notice>{cmp.reason}</Notice>}
      </div>
      <table className="data-table">
        <caption className="sr-only">Comparación de zonas en el periodo activo</caption>
        <thead>
          <tr>
            <th scope="col">Zona</th>
            <th scope="col">Índice</th>
            <th scope="col">Nivel</th>
            <th scope="col">Dif. con A</th>
            <th scope="col">Prom. histórico</th>
            <th scope="col">Atropellos registrados</th>
          </tr>
        </thead>
        <tbody>
          {cmp.items.map((it, i) => (
            <tr key={it.result.unit.unit_id}>
              <th scope="row">
                <span className="badge">{LETTERS[i]}</span> {displayName(it.result)}
              </th>
              <td className="num">{fmtIndex(it.result.risk_index)}</td>
              <td>
                <LevelTag result={it.result} bands={bands} />
              </td>
              <td className="num">{i === 0 ? "—" : it.index_difference === null ? "n/a" : signed(it.index_difference)}</td>
              <td className="num">{fmtValue(it.result.historical_average)}</td>
              <td className="num">{fmtCount(it.result.observed.events)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------------ temporal
function TemporalControls({ units, districts }: { units: UnitCollection; districts: UnitCollection }) {
  const q = useQuery();
  const options = q.unitType === "district" ? districts.features : [];
  return (
    <>
      <label className="field-label" htmlFor="temporal-unit">
        Zona
      </label>
      {q.unitType === "district" ? (
        <select
          id="temporal-unit"
          className="select"
          value={q.temporalUnitId ?? ""}
          onChange={(e) => q.setTemporalUnit(e.target.value || null)}
        >
          <option value="">Elija un distrito</option>
          {options
            .slice()
            .sort((a, b) => a.properties.display_name.localeCompare(b.properties.display_name, "es"))
            .map((f) => (
              <option key={f.properties.unit_id} value={f.properties.unit_id}>
                {f.properties.display_name}
              </option>
            ))}
        </select>
      ) : (
        <p id="temporal-unit">
          {q.temporalUnitId ? `Celda ${q.temporalUnitId}, ${unitName(q.temporalUnitId, "cell", units)}` : "Haga clic en una celda del mapa."}
        </p>
      )}
      <p className="muted small">La geometría y la definición del índice no cambian entre periodos.</p>
      <PeriodPicker years={q.years} value={q.periodA} onChange={q.setPeriodA} title={<p className="field-label"><span className="badge">A</span> Periodo A</p>} />
      <PeriodPicker years={q.years} value={q.periodB} onChange={q.setPeriodB} title={<p className="field-label"><span className="badge">B</span> Periodo B</p>} />
    </>
  );
}

function TemporalView({ units, districts, bands }: { units: UnitCollection; districts: UnitCollection; bands: ClassBand[] }) {
  const q = useQuery();
  const idA = q.periodId(q.periodA);
  const idB = q.periodId(q.periodB);
  const unitId = q.temporalUnitId;
  const geo = q.unitType === "cell" ? units : districts;
  const mapA = useApi((s) => api.risk({ periodId: idA!, unitType: q.unitType }, s), [idA, q.unitType], !!idA);
  const mapB = useApi((s) => api.risk({ periodId: idB!, unitType: q.unitType }, s), [idB, q.unitType], !!idB);
  const cmp = useApi(
    (s) => api.compareTemporal(q.unitType, unitId!, [idA!, idB!], s),
    [unitId, idA, idB, q.unitType],
    !!unitId && !!idA && !!idB && idA !== idB,
  );
  const seriesIds = q.years.map((year) => q.periodId({ ...q.periodB, year })).filter((x): x is string => !!x);
  const series = useApi(
    (s) => api.compareTemporal(q.unitType, unitId!, seriesIds, s),
    [unitId, q.unitType, seriesIds.join()],
    !!unitId && seriesIds.length >= 2,
  );
  const resA = useMemo(() => toMap(mapA.data?.data), [mapA.data]);
  const resB = useMemo(() => toMap(mapB.data?.data), [mapB.data]);
  const selected = unitId ? [unitId] : [];

  return (
    <main className="compare-main">
      <div className="twin-maps">
        {[
          { key: "A", id: idA, res: resA },
          { key: "B", id: idB, res: resB },
        ].map((m) => (
          <div key={m.key} className="map-area">
            <div className="map-chip">
              <span className="badge">{m.key}</span> {m.id ?? "Periodo sin resultados"}
            </div>
            <RiskMap
              units={geo}
              outline={q.unitType === "cell" ? districts : undefined}
          scope={districts}
              results={m.res}
              bands={bands}
              selected={selected}
              focus={unitId}
              onSelect={q.setTemporalUnit}
              ariaLabel={`Mapa del periodo ${m.key}`}
            />
          </div>
        ))}
      </div>
      <section className="compare-bottom">
        {!unitId && <Notice>Elija una zona para comparar entre periodos.</Notice>}
        {idA && idA === idB && <Notice tone="warn">Elija dos periodos distintos.</Notice>}
        {cmp.error && <Notice tone="error">{cmp.error.message}</Notice>}
        {cmp.data && (
          <div className="compare-grid three">
            <div>
              <h3>{displayName(cmp.data.items[0].result)}</h3>
              <dl className="kv">
                <dt>Periodo A</dt>
                <dd>
                  <b>{fmtIndex(cmp.data.items[0].result.risk_index)}</b>, <LevelTag result={cmp.data.items[0].result} bands={bands} plain />
                </dd>
                <dt>Periodo B</dt>
                <dd>
                  <b>{fmtIndex(cmp.data.items[1].result.risk_index)}</b>, <LevelTag result={cmp.data.items[1].result} bands={bands} plain />
                </dd>
                <dt>Variación</dt>
                <dd>{cmp.data.items[1].index_difference === null ? "No comparable" : `${signed(cmp.data.items[1].index_difference)} puntos`}</dd>
              </dl>
              {!cmp.data.comparable && <Notice tone="warn">{cmp.data.reason}</Notice>}
            </div>
            <div>
              <h3>Registro histórico</h3>
              <dl className="kv">
                <dt>Atropellos A</dt>
                <dd>{fmtCount(cmp.data.items[0].result.observed.events)}</dd>
                <dt>Atropellos B</dt>
                <dd>{fmtCount(cmp.data.items[1].result.observed.events)}</dd>
              </dl>
            </div>
            <Series cmp={series.data} />
          </div>
        )}
      </section>
    </main>
  );
}

function Series({ cmp }: { cmp: Comparison | null }) {
  if (!cmp) return null;
  const pts = cmp.items.map((it) => ({ year: it.result.period.year, v: it.result.risk_index }));
  const W = 320;
  const H = 120;
  const xs = (i: number) => 24 + (i * (W - 40)) / Math.max(1, pts.length - 1);
  const ys = (v: number) => H - 20 - (v / 100) * (H - 30);
  return (
    <div>
      <h3>Serie de años</h3>
      <svg viewBox={`0 0 ${W} ${H}`} className="series" role="img" aria-label="Índice por año para el tipo de día y franja del periodo B">
        <rect x={24} y={ys(100)} width={W - 40} height={ys(70) - ys(100)} fill="#FBEEEA" />
        {[0, 40, 70, 100].map((v) => (
          <g key={v}>
            <line x1={24} x2={W - 16} y1={ys(v)} y2={ys(v)} stroke="#E3E3E0" strokeDasharray="3 3" />
            <text x={2} y={ys(v) + 3} fontSize="9" fill="#646870">
              {v}
            </text>
          </g>
        ))}
        {pts.map((p, i) =>
          p.v === null ? null : (
            <g key={p.year}>
              {i > 0 && pts[i - 1].v !== null && pts[i].year - pts[i - 1].year === 1 && (
                <line x1={xs(i - 1)} y1={ys(pts[i - 1].v!)} x2={xs(i)} y2={ys(p.v)} stroke="#18191B" strokeWidth="1.5" />
              )}
              <circle cx={xs(i)} cy={ys(p.v)} r="3" fill="#18191B" />
              <text x={xs(i)} y={H - 4} fontSize="8" textAnchor="middle" fill="#646870">
                {String(p.year).slice(2)}
              </text>
            </g>
          ),
        )}
      </svg>
      <p className="muted small">Las líneas no unen años sin fuente (2018–2020).</p>
    </div>
  );
}

// ------------------------------------------------------------------ helpers
function LevelTag({ result, bands, plain }: { result: RiskResult; bands: ClassBand[]; plain?: boolean }) {
  if (!result.risk_level) return <span>Sin resultado</span>;
  const c = colorFor(result.risk_index, bands)!;
  return (
    <span className="level-tag">
      {!plain && <span className="swatch" style={{ background: c }} aria-hidden="true" />}
      {LEVEL_LABEL[result.risk_level].toLowerCase()}
    </span>
  );
}

const toMap = (rows?: RiskResult[]) => new Map((rows ?? []).map((r) => [r.unit.unit_id, r]));
const signed = (v: number) => `${v > 0 ? "+" : ""}${Math.round(v)}`;
const displayName = (r: RiskResult) =>
  r.unit.unit_type === "cell" ? `Celda ${r.unit.unit_id}, ${r.unit.district_name}` : r.unit.display_name;

function unitName(id: string, unitType: string, coll: UnitCollection): string {
  const f = coll.features.find((x) => x.properties.unit_id === id);
  if (!f) return id;
  return unitType === "cell" ? `${id}, ${f.properties.district_name}` : f.properties.display_name;
}
