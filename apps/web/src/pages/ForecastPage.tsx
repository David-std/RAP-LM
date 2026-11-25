// Annual forecast view (D-11, D-16). Later horizons use model-generated lags.

import { useMemo, useState } from "react";

import { api } from "../api/client";
import type { DayType, ForecastRow, Legend as LegendDto, RiskResult, UnitCollection, UnitType } from "../api/types";
import { useApi } from "../api/useApi";
import { Disclosure, InfoTip, Notice, Segmented } from "../components/Controls";
import { Legend } from "../components/Legend";
import { RiskMap } from "../components/RiskMap";
import { exportCsv, type ExportColumn } from "../lib/export";
import { BANDS, DAY_LABEL, fmtValue } from "../lib/format";
import { classBands, colorFor, LEVEL_LABEL } from "../lib/levels";

interface Props {
  units: UnitCollection;
  districts: UnitCollection;
  legend: LegendDto;
}

const EMPTY = new Map<string, RiskResult>();
const pct = (v: number | null | undefined) => (v == null ? "n/a" : `${(v * 100).toFixed(0)} %`);
const signedPct = (v: number | null | undefined) =>
  v == null ? "n/a" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${fmtValue(Math.abs(v), 1)} %`;

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
  const prio = model.data?.card.prioritisation?.find((r) => r.fold === "onsv");
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
          <h2 className="rail-title">{horizon ? `Riesgo esperado en ${horizon}` : "Riesgo esperado el próximo año"}</h2>
          <p className="rail-lead">
            Índice de riesgo estimado por la red entrenada con registros hasta {last ?? "el último año observado"}, en la
            misma escala que el mapa de riesgo.
          </p>
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
            hint="Desde el segundo año, cada pronóstico usa como entrada la estimación del año previo, por lo que la incertidumbre crece. Con años conocidos, la red mantuvo su ventaja sobre el promedio histórico hasta tres años después."
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
        <Disclosure
          summary="Cómo se obtiene"
          items={[
            ["Entradas", <>Historial de atropellos y contexto urbano de cada celda, con la población fijada en {last ?? "el último año observado"}.</>],
            ["Años siguientes", "Cada año proyectado sirve de entrada al siguiente; no se incorporan registros nuevos."],
            ["Rango", "Mínimo y máximo entre las cinco redes del ensamble. Mide su desacuerdo, no es un intervalo de confianza."],
          ]}
        />
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
              {focus.expected_events != null && `; ${fmtValue(focus.expected_events, 1)} atropellos esperados en la franja`}
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
            <h2>Fiabilidad <InfoTip text="Medidas de un modelo entrenado sin el año evaluado. Captura: parte de los siniestros que cae en el 20 % de celdas con mayor riesgo estimado. AUC: 1 es un orden perfecto y 0,5 el azar." align="right" /></h2>
          </header>
          <p className="panel-text">
            Probado sobre {prio?.test_year ?? test?.year ?? 2024} sin usar sus registros, con los siniestros fatales con
            peatón del ONSV. Es una evaluación a un año: 2026 y 2027 no tienen con qué contrastarse.
          </p>
          <table className="panel-table static">
            <thead>
              <tr><th scope="col">Medida</th><th scope="col" className="num">Red</th><th scope="col" className="num">Histórico</th></tr>
            </thead>
            <tbody>
              {prio && (
                <>
                  <tr><td>Siniestros en el 20 % de celdas priorizadas</td><td className="num strong">{pct(prio.cell_year.model.capture_top20)}</td><td className="num">{pct(prio.cell_year.historical_average.capture_top20)}</td></tr>
                  <tr><td>Área bajo la curva ROC</td><td className="num strong">{fmtValue(prio.cell_year.model.auc, 2)}</td><td className="num">{fmtValue(prio.cell_year.historical_average.auc, 2)}</td></tr>
                </>
              )}
              <tr><td>Error por distrito frente al histórico</td><td className="num strong">{signedPct(test?.relative_improvement_pct == null ? null : -test.relative_improvement_pct)}</td><td className="num">referencia</td></tr>
            </tbody>
          </table>
        </section>

        <section className="card">
          <header>
            <h2>Mayor riesgo esperado <InfoTip text="Índice pronosticado en la escala del mapa de riesgo. Rango: valores mínimo y máximo entre las cinco redes del ensamble; mide su desacuerdo, no un intervalo de confianza." align="right" /></h2>
            {unitType === "district" && totalExpected > 0 && <p className="card-sub">{fmtValue(totalExpected, 0)} atropellos esperados en la franja, en la escala de registro del censo de comisarías; no es el total real de Lima</p>}
          </header>
          <table className="panel-table">
            <thead>
              <tr>
                <th scope="col">{unitType === "cell" ? "Celda" : "Distrito"}</th>
                <th scope="col" className="num">{horizon}</th>
                <th scope="col" className="num">Rango</th>
                <th scope="col">vs {previous}</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 12).map((r) => (
                <tr key={r.unit_id} className={r.unit_id === selected ? "on" : ""} onClick={() => setSelected(r.unit_id)}>
                  <td>
                    <span className="swatch" style={{ background: colorFor(r.risk_index, bands)! }} aria-hidden="true" /> {unitType === "cell" ? `${r.unit_id}, ${r.district_name}` : r.display_name}
                  </td>
                  <td className="num">{r.risk_index.toFixed(0)}</td>
                  <td className="num muted">
                    {r.index_low.toFixed(0)}–{r.index_high.toFixed(0)}
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
            <h2>Mayor aumento frente a {previous} <InfoTip align="right" text="Zonas cuyo índice pronosticado sube más respecto al año anterior en el mismo tipo de día y franja." /></h2>
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
