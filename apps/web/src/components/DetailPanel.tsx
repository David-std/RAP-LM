// Unit detail (RF-02, RF-07, RF-08; HU-06..HU-08, HU-22..HU-26).
// Keeps the estimated indicator and the observed historical record visibly
// separate (HU-23) and links every value to its provenance.

import { api } from "../api/client";
import type { RiskResult } from "../api/types";
import { useApi } from "../api/useApi";
import { BANDS, DAY_LABEL, fmtCount, fmtIndex, fmtValue, PARTITION_LABEL, periodLabel, SOURCE_LABEL } from "../lib/format";
import { colorFor, inkOn, LEVEL_LABEL, type ClassBand } from "../lib/levels";
import { useQuery } from "../state/QueryContext";
import { Notice } from "./Controls";

interface Props {
  result: RiskResult | null;
  bands: ClassBand[];
  onClose: () => void;
  onCompareZones: () => void;
  onComparePeriods: () => void;
}

export function DetailPanel({ result, bands, onClose, onCompareZones, onComparePeriods }: Props) {
  const q = useQuery();
  const unitId = q.selectedUnitId;
  const year = q.active.year;

  // Hour profile of the selected year: one temporal comparison over its 8 periods.
  const profileIds = (["weekday", "weekend"] as const).flatMap((d) =>
    [0, 1, 2, 3].map((b) => q.periodId({ year, dayType: d, band: b })).filter((x): x is string => !!x),
  );
  const profile = useApi(
    (s) => api.compareTemporal(q.unitType, unitId!, profileIds, s),
    [unitId, q.unitType, year],
    !!unitId && profileIds.length >= 2,
  );
  const activeId = q.periodId(q.active);
  const prov = useApi(
    (s) => api.provenance({ unitType: q.unitType, unitId: unitId!, periodId: activeId! }, s),
    [unitId, q.unitType, activeId],
    !!unitId && !!activeId,
  );

  if (!unitId) return null;
  const unit = result?.unit;
  const estimated = result?.availability === "estimated";
  const color = colorFor(result?.risk_index ?? null, bands);

  return (
    <aside className="detail" aria-label="Detalle de la unidad seleccionada">
      <header className="detail-head">
        <div>
          <h2>{unit ? (unit.unit_type === "cell" ? `Celda ${unit.unit_id}` : unit.display_name) : unitId}</h2>
          {unit && (
            <p className="muted">
              {unit.unit_type === "cell" ? `${unit.district_name}, UBIGEO ${unit.district_id}` : `UBIGEO ${unit.district_id}`}
            </p>
          )}
        </div>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Cerrar detalle">
          ×
        </button>
      </header>

      {!result && <Notice>Cargando resultado…</Notice>}
      {result && (
        <section className="detail-block">
          <dl className="kv">
            <dt>Índice de riesgo</dt>
            <dd>
              <strong>{fmtIndex(result.risk_index)}</strong> {estimated && "de 100"}
            </dd>
            <dt>Nivel</dt>
            <dd>
              {result.risk_level ? (
                <>
                  <span className="swatch" style={{ background: color ?? undefined }} aria-hidden="true" />{" "}
                  {LEVEL_LABEL[result.risk_level]}
                </>
              ) : (
                "Sin resultado (no equivale a bajo)"
              )}
            </dd>
            <dt>Periodo</dt>
            <dd>{periodLabel(result.period)}</dd>
            <dt>Unidad espacial</dt>
            <dd>{result.unit.unit_type === "cell" ? "Celda de 1 km" : "Distrito"}</dd>
            <dt>Indicador estimado</dt>
            <dd title={result.value_unit}>{fmtValue(result.indicator_value)} atropellos/km²·año</dd>
            <dt>Promedio histórico</dt>
            <dd title="Enfoque base: promedio de años previos de la misma fuente, unidad y franja">
              {fmtValue(result.historical_average)}
            </dd>
            <dt>Posición en Lima</dt>
            <dd>
              {estimated
                ? `supera al ${fmtIndex(result.risk_index)} % de las ${result.unit.unit_type === "cell" ? "celdas" : "distritos"} de referencia`
                : "—"}
            </dd>
          </dl>
          {estimated && (
            <div className="index-bar" aria-hidden="true">
              <div className="index-scale">
                {bands.map((b) => (
                  <span key={b.min} style={{ background: b.color, flex: b.max - b.min }} />
                ))}
              </div>
              <span className="index-mark" style={{ left: `${result.risk_index}%` }} />
            </div>
          )}
          <p className="model-note">
            Indicador <strong>estimado por el modelo</strong> CNN-LSTM. No es el conteo de atropellos ni una
            probabilidad.
          </p>
        </section>
      )}

      <section className="detail-block">
        <h3>
          Perfil horario {year} <span className="muted small">clic para cambiar el periodo</span>
        </h3>
        {profile.error && <Notice tone="error">{profile.error.message}</Notice>}
        <table className="profile">
          <thead>
            <tr>
              <th scope="col">
                <span className="sr-only">Tipo de día</span>
              </th>
              {BANDS.map((b) => (
                <th key={b} scope="col">
                  {b}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(["weekday", "weekend"] as const).map((d) => (
              <tr key={d}>
                <th scope="row">{DAY_LABEL[d]}</th>
                {[0, 1, 2, 3].map((b) => {
                  const item = profile.data?.items.find(
                    (i) => i.result.period.day_type === d && i.result.period.time_band === b,
                  );
                  const idx = item?.result.risk_index ?? null;
                  const c = colorFor(idx, bands);
                  const active = q.active.dayType === d && q.active.band === b;
                  return (
                    <td key={b}>
                      <button
                        type="button"
                        className={`profile-cell${active ? " on" : ""}${c ? "" : " hatch"}`}
                        style={c ? { background: c, color: inkOn(c) } : undefined}
                        aria-label={`${DAY_LABEL[d]} ${BANDS[b]}: ${fmtIndex(idx)}`}
                        aria-pressed={active}
                        onClick={() => q.setActive({ dayType: d, band: b })}
                      >
                        {idx === null ? "—" : Math.round(idx)}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {result && (
        <section className="detail-block">
          <h3>Registro histórico observado en el periodo</h3>
          <dl className="kv">
            <dt>Atropellos registrados</dt>
            <dd>{fmtCount(result.observed.events)}</dd>
            <dt>Peatones lesionados</dt>
            <dd>{fmtCount(result.observed.pedestrians_injured)}</dd>
            <dt>Peatones fallecidos</dt>
            <dd>{fmtCount(result.observed.pedestrians_deceased)}</dd>
          </dl>
          <p className="muted small">
            Son la referencia de frecuencia de las fuentes, no el riesgo estimado.{" "}
            {result.unit.unit_type === "cell" &&
              "En celdas solo cuentan los eventos ubicados por punto o calle; los ubicados solo por distrito aparecen en la vista distrital."}
          </p>
        </section>
      )}

      <section className="detail-block">
        <h3>Procedencia</h3>
        {prov.loading && <Notice>Cargando procedencia…</Notice>}
        {prov.data && (
          <>
            <dl className="kv">
              <dt>Fuentes del periodo</dt>
              <dd>
                {prov.data.result_context?.observing_sources.map((s) => SOURCE_LABEL[s] ?? s).join(", ") ||
                  "Ninguna"}
              </dd>
              <dt>Partición</dt>
              <dd>{PARTITION_LABEL[result?.period.partition ?? ""] ?? result?.period.partition}</dd>
              <dt>Corrida</dt>
              <dd className="mono">{prov.data.run.run_id}</dd>
              <dt>Dataset</dt>
              <dd className="mono">{prov.data.meta.run.dataset_version_id}</dd>
            </dl>
            <details>
              <summary>Variables por grupo ({Object.values(prov.data.variables_by_group).flat().length})</summary>
              {Object.entries(prov.data.variables_by_group).map(([group, vars]) => (
                <div key={group} className="var-group">
                  <h4>{GROUP_LABEL[group] ?? group}</h4>
                  <ul>
                    {vars.map((v) => (
                      <li key={v.variable_id} className={v.incorporated ? "" : "excluded"}>
                        {v.label} <span className="muted small">({v.reference_period})</span>
                        {!v.incorporated && <span className="tag">no incorporada</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </details>
            <details>
              <summary>Limitaciones ({prov.data.limitations.length})</summary>
              <ul className="limitations">
                {prov.data.limitations.map((l) => (
                  <li key={l.limitation_id}>
                    <strong>{l.dimension}.</strong> {l.description}
                  </li>
                ))}
              </ul>
            </details>
          </>
        )}
      </section>

      <footer className="detail-actions">
        <button type="button" className="btn primary" onClick={onCompareZones}>
          Comparar zonas
        </button>
        <button type="button" className="btn" onClick={onComparePeriods}>
          Comparar periodos
        </button>
      </footer>
    </aside>
  );
}

export const GROUP_LABEL: Record<string, string> = {
  occurrence: "Ocurrencia",
  severity: "Severidad",
  exposure: "Exposición",
  context: "Contexto",
};
