// Annual forecast view (D-11, D-16). Later horizons use model-generated lags.

import { useMemo, useState } from "react";

import { api } from "../api/client";
import type { DayType, ForecastRow, Legend as LegendDto, RiskResult, UnitCollection, UnitType } from "../api/types";
import { useApi } from "../api/useApi";
import { Notice, Segmented } from "../components/Controls";
import { Legend } from "../components/Legend";
import { RiskMap } from "../components/RiskMap";
import { exportCsv, type ExportColumn } from "../lib/export";
import { BANDS, DAY_LABEL } from "../lib/format";
import { classBands, colorFor, LEVEL_LABEL } from "../lib/levels";

interface Props {
  units: UnitCollection;
  districts: UnitCollection;
  legend: LegendDto;
}

const EMPTY = new Map<string, RiskResult>();
const pct = (v: number | null | undefined) => (v == null ? "n/a" : `${(v * 100).toFixed(0)} %`);

function Change({ row }: { row: ForecastRow }) {
  const d = row.risk_index - row.previous_index;
  if (Math.abs(d) < 2) return <span className="muted">estable</span>;
  return <span className={d > 0 ? "delta-up" : "delta-down"}>{d > 0 ? "▲" : "▼"} {Math.abs(d).toFixed(0)}</span>;
}

export function ForecastPage({ units, districts, legend }: Props) {
  const [unitType, setUnitType] = useState<UnitType>("district");
  const [dayType, setDayType] = useState<DayType>("weekday");
  const [band, setBand] = useState(3);
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const bands = useMemo(() => classBands(legend), [legend]);
  const [year, setYear] = useState<number | null>(null);
  const fc = useApi((s) => api.forecast(unitType, dayType, band, year, s), [unitType, dayType, band, year]);
  const model = useApi((s) => api.model(s), []);
  const current = fc.data && fc.data.unit_type === unitType && fc.data.day_type === dayType && fc.data.band === band && (year === null || fc.data.horizon_year === year) ? fc.data : null;
  const rows = useMemo(() => current?.data ?? [], [current]);
  const byId = useMemo(() => new Map(rows.map((r) => [r.unit_id, r])), [rows]);
  const rising = useMemo(() => [...rows].sort((a, b) => b.risk_index - b.previous_index - (a.risk_index - a.previous_index)).slice(0, 5), [rows]);
  const focus = byId.get(hover ?? selected ?? "") ?? null;
  const horizon = current?.horizon_year ?? year ?? fc.data?.horizon_year;
  const last = fc.data?.last_observed_year;
  const previous = horizon == null ? last : horizon - 1;
  const chained = horizon != null && last != null && horizon > last + 1;
  const test = model.data?.benchmark.test?.[0];
  const high = model.data?.card.high_level?.[0];
  const totalExpected = rows.reduce((s, r) => s + (r.expected_events ?? 0), 0);

  const columns: ExportColumn<ForecastRow>[] = [
    { header: "unit_id", value: (r) => r.unit_id },
    { header: "name", value: (r) => r.display_name },
    { header: "district", value: (r) => r.district_name },
    { header: "horizon_year", value: () => horizon ?? "" },
    { header: "day_type", value: () => dayType },
    { header: "band", value: () => BANDS[band] },
    { header: "risk_index", value: (r) => r.risk_index },
    { header: "index_low", value: (r) => r.index_low },
    { header: "index_high", value: (r) => r.index_high },
    { header: "previous_index", value: (r) => r.previous_index },
    { header: "expected_events", value: (r) => r.expected_events ?? "" },
  ];

  return (
    <div className="workspace">
      <aside className="rail" aria-label="Opciones de pronóstico">
        <div>
          <p className="eyebrow">Pronóstico</p>
          <h2 className="rail-title">{horizon ? `Riesgo esperado en ${horizon}` : "Riesgo esperado el próximo año"}</h2>
        </div>
        <Segmented<UnitType>
          label="Vista"
          value={unitType}
          options={[
            { value: "district", label: "Distritos" },
            { value: "cell", label: "Malla 1 km" },
          ]}
          onChange={(v) => {
            setUnitType(v);
            setSelected(null);
          }}
        />
        {fc.data?.horizon_years && fc.data.horizon_years.length > 1 && (
          <Segmented<number>
            label="Año pronosticado"
            value={year ?? fc.data.horizon_year}
            options={fc.data.horizon_years.map((y) => ({ value: y, label: String(y) }))}
            onChange={(y) => { setYear(y); setHover(null); }}
          />
        )}
        {chained && (
          <Notice tone="warn">
            Proyección a {horizon! - last!} años desde {last}. Usa estimaciones de años anteriores como entrada;
            el error puede acumularse. No se ha validado este horizonte con registros reales.
          </Notice>
        )}
        <Segmented<DayType>
          label="Tipo de día"
          value={dayType}
          options={[
            { value: "weekday", label: DAY_LABEL.weekday },
            { value: "weekend", label: DAY_LABEL.weekend },
          ]}
          onChange={setDayType}
        />
        <Segmented label="Franja horaria" value={band} options={BANDS.map((b, i) => ({ value: i, label: b }))} onChange={setBand} />
        <section className="card how">
          <h3>Cómo se obtiene</h3>
          <ol>
            <li>La red CNN-RNN recibe el historial de atropellos hasta {last ?? "el último año"} y el contexto urbano de cada celda, congelado a ese año (población {last ?? ""}).</li>
            <li>La parte convolucional (CNN) lee el vecindario de cada celda; la recurrente (RNN) arrastra la memoria de los años previos.</li>
            <li>{chained ? "Encadena las proyecciones anuales sin incorporar nuevos registros." : "Proyecta el año siguiente sin incorporar sus registros."}</li>
            <li>El rango muestra el desacuerdo entre los cinco modelos, no un intervalo de confianza.</li>
          </ol>
        </section>
        {current && (
          <button type="button" className="btn" onClick={() => exportCsv(`pronostico-${horizon}-${unitType}.csv`, rows, columns, current.meta, `forecast ${horizon}, ${dayType}, band ${BANDS[band]}`)}>
            Exportar CSV
          </button>
        )}
      </aside>

      <main className="map-area" aria-label="Mapa del pronóstico">
        {fc.loading && <Notice>Cargando pronóstico…</Notice>}
        {fc.error && <Notice tone="warn">La corrida publicada no tiene pronóstico ({fc.error.message}).</Notice>}
        <RiskMap
          units={unitType === "cell" ? units : districts}
          outline={unitType === "cell" ? districts : undefined}
          scope={districts}
          results={EMPTY}
          bands={bands}
          selected={selected ? [selected] : []}
          colorize={(id) => colorFor(byId.get(id)?.risk_index ?? null, bands)}
          onSelect={setSelected}
          onHover={(id) => setHover(id)}
          ariaLabel={`Mapa del pronóstico ${horizon ?? ""}`}
        />
        {focus && (
          <div className="map-tip" role="tooltip">
            <strong>{unitType === "cell" ? `Celda ${focus.unit_id}` : focus.display_name}</strong>
            <span className="muted">{focus.district_name}</span>
            <span>
              Índice {horizon}: <b>{focus.risk_index.toFixed(0)}</b> {LEVEL_LABEL[focus.risk_level]} (rango {focus.index_low.toFixed(0)} a {focus.index_high.toFixed(0)})
            </span>
            <span className="muted small">
              {previous}: {focus.previous_index.toFixed(0)}
              {focus.expected_events != null && `; ${focus.expected_events.toFixed(1)} atropellos esperados en la franja`}
            </span>
          </div>
        )}
        <div className="legend-dock">
          <Legend legend={legend} bands={bands} title={`Pronóstico ${horizon ?? ""}`} subtitle={`${DAY_LABEL[dayType].toLowerCase()}, ${BANDS[band]}. Misma escala que el mapa de riesgo.`} />
        </div>
      </main>

      <aside className="zone-panel" aria-label="Detalle del pronóstico">
        <section className="card">
          <header>
            <h2>¿Es confiable?</h2>
            <p className="card-sub">Evaluación a un año sobre ONSV {test?.year ?? 2024} (siniestros fatales); no valida 2025–2027.</p>
          </header>
          <div className="kpi-row two">
            <div className="kpi">
              <span className="kpi-value">{pct(high?.model.recall)}</span>
              <span className="kpi-foot">de las zonas de nivel alto anticipadas (promedio histórico: {pct(high?.baseline?.recall)})</span>
            </div>
            <div className="kpi">
              <span className="kpi-value">{test?.relative_improvement_pct == null ? "n/a" : `${test.relative_improvement_pct > 0 ? "+" : ""}${test.relative_improvement_pct.toFixed(1)} %`}</span>
              <span className="kpi-foot">menos error que repetir el promedio histórico</span>
            </div>
          </div>
        </section>

        <section className="card">
          <header>
            <h2>Mayor riesgo esperado</h2>
            {unitType === "district" && totalExpected > 0 && <p className="card-sub">{totalExpected.toFixed(0)} atropellos estimados en la franja, 43 distritos (escala de referencia)</p>}
          </header>
          <table className="data-table">
            <thead>
              <tr>
                <th>{unitType === "cell" ? "Celda" : "Distrito"}</th>
                <th className="num">{horizon}</th>
                <th>Rango</th>
                <th>vs {previous}</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 12).map((r) => (
                <tr key={r.unit_id} className={r.unit_id === selected ? "on" : ""} onClick={() => setSelected(r.unit_id)}>
                  <td>
                    <span className="swatch" style={{ background: colorFor(r.risk_index, bands)! }} aria-hidden="true" /> {unitType === "cell" ? `${r.unit_id}, ${r.district_name}` : r.display_name}
                  </td>
                  <td className="num">{r.risk_index.toFixed(0)}</td>
                  <td className="muted small">
                    {r.index_low.toFixed(0)} a {r.index_high.toFixed(0)}
                  </td>
                  <td>
                    <Change row={r} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="card">
          <header>
            <h2>Mayor aumento frente a {previous}</h2>
          </header>
          <ul className="plain-list">
            {rising.map((r) => (
              <li key={r.unit_id}>
                <button type="button" className="link-btn" onClick={() => setSelected(r.unit_id)}>
                  {unitType === "cell" ? `${r.unit_id}, ${r.district_name}` : r.display_name}
                </button>{" "}
                {r.previous_index.toFixed(0)} → {r.risk_index.toFixed(0)}
              </li>
            ))}
          </ul>
          <p className="card-note">Pronóstico para planificar y priorizar; no es una alerta en tiempo real ni sustituye el registro oficial.</p>
        </section>
      </aside>
    </div>
  );
}
