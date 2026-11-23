// Zone panel (EP-02, EP-05; RF-02, RF-07, RF-08; HU-06..HU-08, HU-22..HU-26).
// Cards that answer, for the selected cell or district: how high is the risk,
// what the network expected vs what was recorded each year, when in the day,
// of which type and severity, what drives the estimate, what if the context
// changed, which streets concentrate the record and where the data comes from.

import { useMemo, useState } from "react";

import { api } from "../api/client";
import type { CorridorCollection, Explanation, RiskResult } from "../api/types";
import { useApi } from "../api/useApi";
import { BANDS, DAY_LABEL, fmtCount, fmtIndex, fmtValue, PARTITION_LABEL, periodLabel, SOURCE_LABEL } from "../lib/format";
import { colorFor, inkOn, LEVEL_LABEL, type ClassBand } from "../lib/levels";
import { useQuery } from "../state/QueryContext";
import { DivergingBars, LineChart, YearSeriesChart } from "./charts";
import { Notice } from "./Controls";

export const GROUP_LABEL: Record<string, string> = {
  occurrence: "Ocurrencia",
  severity: "Severidad",
  exposure: "Exposición",
  context: "Contexto",
};

const DRIVER_LABEL: Record<string, string> = {
  population: "Población",
  transit: "Transporte público",
  street_network: "Red vial",
  crossings_signals: "Cruces y semáforos",
  prior_collisions: "Atropellos del año previo",
  activity: "Comercio y servicios",
  walkability: "Infraestructura peatonal",
  traffic: "Vías arteriales",
};

export const VARIABLE_LABEL: Record<string, string> = {
  population: "Población residente",
  transit_stops: "Paraderos",
  transit_route_km: "Rutas de transporte",
  street_km: "Calles con nombre",
  traffic_lights: "Semáforos (MINAM)",
  pedestrian_crossings: "Cruces (MINAM)",
  special_road_km: "Vías especiales",
  poi_commerce: "Comercio y servicios",
  poi_education: "Centros educativos",
  poi_health: "Centros de salud",
  osm_crossings: "Cruces peatonales",
  osm_signals: "Semáforos",
  footway_km: "Veredas y vías peatonales",
  arterial_km: "Vías arteriales",
  collector_km: "Vías colectoras",
};

const SEVERITY_LABEL = { fatal: "Con fallecido", nonfatal: "Con lesionados", material_only: "Solo daños", unknown: "Sin dato" };
const TYPE_LABEL = { atropello: "Atropello", atropello_fuga: "Atropello y fuga", choque_y_atropello: "Choque y atropello", otro: "Otro con peatón" };

interface Props {
  result: RiskResult | null;
  bands: ClassBand[];
  onClose: () => void;
  onCompareZones: () => void;
  onComparePeriods: () => void;
  onOpenCorridors: (districtId: string) => void;
}

export function ZonePanel({ result, bands, onClose, onCompareZones, onComparePeriods, onOpenCorridors }: Props) {
  const q = useQuery();
  const unitId = q.selectedUnitId;
  const year = q.active.year;
  const activeId = q.periodId(q.active);
  const profileIds = (["weekday", "weekend"] as const).flatMap((d) =>
    [0, 1, 2, 3].map((b) => q.periodId({ year, dayType: d, band: b })).filter((x): x is string => !!x),
  );
  const profile = useApi((s) => api.compareTemporal(q.unitType, unitId!, profileIds, s), [unitId, q.unitType, year], !!unitId && profileIds.length >= 2);
  const explanation = useApi((s) => api.explanation(q.unitType, unitId!, s), [unitId, q.unitType], !!unitId);
  // What-if lives at district level: a cell uses its district.
  const districtId = result?.unit.district_id ?? null;
  const districtExplanation = useApi(
    (s) => api.explanation("district", districtId!, s),
    [districtId],
    !!districtId && q.unitType === "cell",
  );
  const corridors = useApi((s) => api.corridors({ districtIds: [districtId!], limit: 5 }, s), [districtId], !!districtId);
  const prov = useApi(
    (s) => api.provenance({ unitType: q.unitType, unitId: unitId!, periodId: activeId! }, s),
    [unitId, q.unitType, activeId],
    !!unitId && !!activeId,
  );

  if (!unitId) {
    return (
      <aside className="zone-panel" aria-label="Panel de zona">
        <div className="zone-empty">
          <strong>Seleccione una zona en el mapa</strong>
          <span>
            Verá su índice, cómo lo estimó la red año a año, a qué hora se concentra, qué variables lo impulsan, una
            simulación de contexto y las calles con más atropellos registrados.
          </span>
        </div>
      </aside>
    );
  }
  const whatif = q.unitType === "district" ? explanation.data : districtExplanation.data;
  return (
    <aside className="zone-panel" aria-label="Panel de zona">
      <section className="card">
        <div className="zone-head">
          <div>
            <h2>{result ? (result.unit.unit_type === "cell" ? `Celda ${result.unit.unit_id}` : result.unit.display_name) : unitId}</h2>
            {result && (
              <p className="muted">
                {result.unit.unit_type === "cell" ? `${result.unit.district_name}, UBIGEO ${result.unit.district_id}, 1 km²` : `Distrito, UBIGEO ${result.unit.district_id}`}
              </p>
            )}
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Cerrar panel">
            ×
          </button>
        </div>
        {result && (
          <div className="zone-chips">
            <span className="chip accent">{periodLabel(result.period)}</span>
            <span className="chip">Partición: {PARTITION_LABEL[result.period.partition] ?? result.period.partition}</span>
            <span className="chip">{result.period.observing_sources.map((s) => SOURCE_LABEL[s] ?? s).join(", ")}</span>
          </div>
        )}
      </section>

      {result && <RiskCard result={result} bands={bands} />}

      <section className="card">
        <header>
          <div>
            <h3>La red año a año</h3>
            <p className="card-sub">Atropellos que la CNN-LSTM esperaba registrar frente a los registrados, {DAY_LABEL[q.active.dayType].toLowerCase()} y fin de semana, todas las franjas</p>
          </div>
        </header>
        {explanation.loading && <Notice>Cargando…</Notice>}
        {explanation.error && <Notice tone="warn">Explicación no disponible para esta corrida.</Notice>}
        {explanation.data && <YearCard e={explanation.data} year={year} onYear={(y) => q.setActive({ year: y })} />}
      </section>

      <section className="card">
        <header>
          <h3>Perfil horario {year}</h3>
          <span className="card-sub">índice, clic para cambiar de franja</span>
        </header>
        <table className="heat">
          <thead>
            <tr>
              <th scope="col"><span className="sr-only">Tipo de día</span></th>
              {BANDS.map((b) => (
                <th key={b} scope="col">{b}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(["weekday", "weekend"] as const).map((d) => (
              <tr key={d}>
                <th scope="row">{DAY_LABEL[d]}</th>
                {[0, 1, 2, 3].map((b) => {
                  const item = profile.data?.items.find((i) => i.result.period.day_type === d && i.result.period.time_band === b);
                  const idx = item?.result.risk_index ?? null;
                  const c = colorFor(idx, bands);
                  const on = q.active.dayType === d && q.active.band === b;
                  return (
                    <td key={b}>
                      <button
                        type="button"
                        className={`${on ? "on" : ""}${c ? "" : " hatch"}`}
                        style={c ? { background: c, color: inkOn(c) } : undefined}
                        aria-pressed={on}
                        aria-label={`${DAY_LABEL[d]} ${BANDS[b]}: índice ${fmtIndex(idx)}`}
                        onClick={() => q.setActive({ dayType: d, band: b })}
                      >
                        {idx === null ? "–" : Math.round(idx)}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {result && <RecordCard result={result} />}

      {explanation.data && (
        <section className="card">
          <header>
            <div>
              <h3>Qué impulsa la estimación</h3>
              <p className="card-sub">
                Cambio en la estimación {explanation.data.attribution_year} si se retira cada grupo de variables (oclusión). Rojo: eleva el riesgo; petróleo: lo reduce.
              </p>
            </div>
          </header>
          <DivergingBars
            items={explanation.data.attribution_groups.map((g, i) => ({ label: DRIVER_LABEL[g] ?? g, value: explanation.data!.attribution_pct[i] }))}
          />
          <p className="card-note">Incluye el efecto del vecindario de 5 × 5 km que lee la CNN. Asociación del modelo, no causalidad.</p>
        </section>
      )}

      {whatif?.whatif && whatif.whatif_factors && <WhatIfCard e={whatif} />}

      {districtId && (
        <section className="card">
          <header>
            <h3>Calles con más atropellos registrados</h3>
            <button type="button" className="link-btn" onClick={() => onOpenCorridors(districtId)}>
              Ver corredores
            </button>
          </header>
          {corridors.data && corridors.data.features.length === 0 && <p className="empty">Sin calles con eventos ubicados.</p>}
          <CorridorList data={corridors.data} />
        </section>
      )}

      <section className="card">
        <details>
          <summary>Procedencia y limitaciones</summary>
          {prov.data && (
            <>
              <dl className="kv">
                <dt>Corrida</dt>
                <dd className="mono">{prov.data.run.run_id}</dd>
                <dt>Dataset</dt>
                <dd className="mono">{prov.data.meta.run.dataset_version_id}</dd>
                <dt>Fuentes del periodo</dt>
                <dd>{prov.data.result_context?.observing_sources.map((s) => SOURCE_LABEL[s] ?? s).join(", ")}</dd>
              </dl>
              <ul className="steps" style={{ marginTop: 8 }}>
                {prov.data.limitations.map((l) => (
                  <li key={l.limitation_id}>
                    <b>{l.dimension}.</b> {l.description}
                  </li>
                ))}
              </ul>
            </>
          )}
        </details>
      </section>

      <div className="zone-actions">
        <button type="button" className="btn primary" onClick={onCompareZones}>Comparar zonas</button>
        <button type="button" className="btn" onClick={onComparePeriods}>Comparar periodos</button>
      </div>
    </aside>
  );
}

function RiskCard({ result, bands }: { result: RiskResult; bands: ClassBand[] }) {
  const color = colorFor(result.risk_index, bands);
  const hist = result.historical_average;
  const delta = hist && result.indicator_value !== null ? ((result.indicator_value - hist) / hist) * 100 : null;
  return (
    <section className="card">
      <header>
        <h3>Riesgo estimado</h3>
        {result.risk_level ? (
          <span className="level-chip" style={{ background: color ?? undefined, color: color ? inkOn(color) : undefined }}>
            {LEVEL_LABEL[result.risk_level]}
          </span>
        ) : (
          <span className="chip warn">Sin resultado</span>
        )}
      </header>
      <div className="kpi-row">
        <div className="kpi" title="Índice de frecuencia: posición frente a la distribución de referencia">
          <span className="kpi-label">Frecuencia</span>
          <span className="kpi-value">{fmtIndex(result.risk_index)}</span>
          <span className="kpi-foot">{fmtValue(result.indicator_value)} por km² al año</span>
        </div>
        <div className="kpi" title="Atropellos esperados con desenlace fatal (frecuencia × probabilidad de fallecido de la zona)">
          <span className="kpi-label">Severidad</span>
          <span className="kpi-value">{result.severity.index === null ? "–" : Math.round(result.severity.index)}</span>
          <span className="kpi-foot">{result.severity.value === null ? "no disponible" : `${fmtValue(result.severity.value, 3)} fatales/km²`}</span>
        </div>
        <div className="kpi" title="Razón entre lo estimado y lo esperado solo por exposición (población, comercio, transporte, veredas, arterias)">
          <span className="kpi-label">Por exposición</span>
          <span className="kpi-value">{result.exposure.value === null ? "–" : `${fmtValue(result.exposure.value, 1)}×`}</span>
          <span className="kpi-foot">{result.exposure.index === null ? "no disponible" : `índice ${Math.round(result.exposure.index)}`}</span>
        </div>
      </div>
      {result.risk_index !== null && (
        <>
          <div className="index-bar" aria-hidden="true">
            <div className="index-scale">
              {bands.map((b) => (
                <span key={b.min} style={{ background: b.color, flex: b.max - b.min }} />
              ))}
            </div>
            <span className="index-mark" style={{ left: `${result.risk_index}%` }} />
          </div>
          <div className="index-ticks">
            <span>0</span>
            <span>40</span>
            <span>70</span>
            <span>100</span>
          </div>
        </>
      )}
      <p className="card-note">
        Supera al {fmtIndex(result.risk_index)} % de las {result.unit.unit_type === "cell" ? "celdas" : "distritos"} y franjas de referencia.
        {delta !== null && (
          <>
            {" "}Frente al promedio histórico de la misma fuente:{" "}
            <b className={delta > 0 ? "delta-up" : "delta-down"}>
              {delta > 0 ? "+" : ""}
              {delta.toFixed(0)} %
            </b>
            .
          </>
        )}{" "}
        Valores estimados por el modelo, no conteos ni probabilidades.
      </p>
    </section>
  );
}

function YearCard({ e, year, onYear }: { e: Explanation; year: number; onYear: (y: number) => void }) {
  const err = useMemo(() => {
    const pairs = e.years.map((_, i) => Math.abs(e.expected_events[i] - e.observed_events[i]));
    return pairs.reduce((a, b) => a + b, 0) / Math.max(pairs.length, 1);
  }, [e]);
  return (
    <>
      <YearSeriesChart
        years={e.years}
        observed={e.observed_events}
        expected={e.expected_events}
        highlightYear={year}
        expectedLabel="Esperado por la red"
        observedLabel="Registrado"
        onSelectYear={onYear}
      />
      <p className="card-note">
        Cada año la LSTM solo ve los años anteriores y el contexto. 2011-2017 se compara con el censo de comisarías (todas
        las severidades); 2021-2024, con el ONSV (fatales), escalado por su factor de registro. Error medio absoluto en
        esta zona: {err.toFixed(2)} eventos por año.
      </p>
    </>
  );
}

function RecordCard({ result }: { result: RiskResult }) {
  const b = result.breakdown;
  const total = result.observed.events ?? 0;
  return (
    <section className="card">
      <header>
        <div>
          <h3>Registro histórico del periodo</h3>
          <p className="card-sub">Conteos de las fuentes, no el riesgo estimado</p>
        </div>
        <span className="kpi-value" style={{ fontSize: 20 }}>{fmtCount(total)}</span>
      </header>
      {b ? (
        <div className="grid cols-2" style={{ gap: 10 }}>
          <Breakdown title="Por subtipo" data={b.type} labels={TYPE_LABEL} color="var(--chart-2)" />
          <Breakdown title="Por severidad" data={b.severity} labels={SEVERITY_LABEL} color="#bf3a2e" />
        </div>
      ) : (
        <p className="muted small">Desglose no disponible para esta corrida.</p>
      )}
      <p className="card-note">
        Peatones lesionados: {fmtCount(result.observed.pedestrians_injured)}; fallecidos: {fmtCount(result.observed.pedestrians_deceased)}.
        {result.unit.unit_type === "cell" && " En celdas solo cuentan eventos ubicados por punto o calle."}
      </p>
    </section>
  );
}

function Breakdown<K extends string>({ title, data, labels, color }: { title: string; data: Record<K, number>; labels: Record<K, string>; color: string }) {
  const entries = Object.entries(data) as [K, number][];
  const max = Math.max(...entries.map(([, v]) => v), 1);
  return (
    <div>
      <p className="field-label">{title}</p>
      {entries.map(([k, v]) => (
        <div key={k} className="bar-row" style={{ gridTemplateColumns: "96px 1fr 34px" }}>
          <span className="small">{labels[k]}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ left: 0, width: `${(v / max) * 100}%`, background: color }} />
          </span>
          <span className="num small">{fmtCount(v)}</span>
        </div>
      ))}
    </div>
  );
}

function WhatIfCard({ e }: { e: Explanation }) {
  const vars = Object.keys(e.whatif!);
  const [variable, setVariable] = useState(vars.includes("poi_commerce") ? "poi_commerce" : vars[0]);
  const factors = e.whatif_factors!;
  const [fi, setFi] = useState(factors.indexOf(1));
  const curve = e.whatif![variable];
  const change = curve[fi];
  return (
    <section className="card">
      <header>
        <div>
          <h3>Simular contexto del distrito</h3>
          <p className="card-sub">Respuesta precalculada de la red al multiplicar una variable en las celdas de {e.unit_id}</p>
        </div>
      </header>
      <label className="field-label" htmlFor="whatif-var">Variable</label>
      <select id="whatif-var" className="select" value={variable} onChange={(ev) => setVariable(ev.target.value)}>
        {vars.map((v) => (
          <option key={v} value={v}>{VARIABLE_LABEL[v] ?? v}</option>
        ))}
      </select>
      <label className="field-label" htmlFor="whatif-factor" style={{ marginTop: 10, display: "block" }}>
        Factor: <b>{factors[fi]}×</b> el valor actual
      </label>
      <input id="whatif-factor" type="range" min={0} max={factors.length - 1} step={1} value={fi} onChange={(ev) => setFi(Number(ev.target.value))} />
      <p style={{ margin: "8px 0" }}>
        Riesgo estimado del distrito:{" "}
        <b className={change > 0 ? "delta-up" : change < 0 ? "delta-down" : ""}>
          {change > 0 ? "+" : ""}
          {change.toFixed(1)} %
        </b>
      </p>
      <LineChart
        series={[{ name: VARIABLE_LABEL[variable] ?? variable, color: "var(--chart-1)", points: factors.map((f, i) => [f, curve[i]]) }]}
        height={130}
        xLabel="factor sobre el valor actual"
        xFormat={(v) => `${v}×`}
        yFormat={(v) => `${v.toFixed(0)} %`}
        marker={{ x: factors[fi], label: "" }}
      />
      <p className="card-note">Dependencia parcial (como en el What-If Tool): las demás variables se mantienen. Describe al modelo; no es una recomendación de intervención.</p>
    </section>
  );
}

function CorridorList({ data }: { data: CorridorCollection | null }) {
  if (!data) return null;
  return (
    <ul className="ranked-list">
      {data.features.map((f) => (
        <li key={f.id}>
          <span>
            <b>{f.properties.street}</b>
            <span className="muted small"> {f.properties.length_km.toFixed(1)} km</span>
          </span>
          <span className="num">{fmtCount(f.properties.events)} eventos</span>
        </li>
      ))}
    </ul>
  );
}
