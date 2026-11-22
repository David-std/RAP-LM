// Temporal evolution strip (RF-03, RF-06): index of the selected unit for the
// active day type and band across every published year. A click changes the
// active period; years without a source are simply not listed (no fake zeros).

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { BANDS, DAY_LABEL, fmtIndex } from "../lib/format";
import { colorFor, type ClassBand } from "../lib/levels";
import { useQuery } from "../state/QueryContext";

export function Timeline({ bands }: { bands: ClassBand[] }) {
  const q = useQuery();
  const ids = q.years
    .map((year) => q.periodId({ ...q.active, year }))
    .filter((x): x is string => !!x);
  const series = useApi(
    (s) => api.compareTemporal(q.unitType, q.selectedUnitId!, ids, s),
    [q.selectedUnitId, q.unitType, q.active.dayType, q.active.band, ids.join()],
    !!q.selectedUnitId && ids.length >= 2,
  );
  if (!q.selectedUnitId) {
    return (
      <section className="timeline empty" aria-label="Evolución temporal">
        <p className="muted">Seleccione una unidad en el mapa para ver su evolución entre años.</p>
      </section>
    );
  }
  return (
    <section className="timeline" aria-label="Evolución temporal">
      <h3>
        Evolución temporal{" "}
        <span className="muted">
          Índice de {q.selectedUnitId}, {DAY_LABEL[q.active.dayType].toLowerCase()} {BANDS[q.active.band]}. Clic en
          una barra para cambiar de año.
        </span>
      </h3>
      <div className="bars">
        {series.data?.items.map(({ result }) => {
          const idx = result.risk_index;
          const color = colorFor(idx, bands);
          const active = result.period.year === q.active.year;
          return (
            <button
              key={result.period.period_id}
              type="button"
              className={`bar${active ? " on" : ""}`}
              aria-pressed={active}
              aria-label={`${result.period.year}: índice ${fmtIndex(idx)}`}
              onClick={() => q.setActive({ year: result.period.year })}
            >
              <span
                className={`bar-fill${color ? "" : " hatch"}`}
                style={{ height: `${Math.max(idx ?? 100, 3)}%`, background: color ?? undefined }}
              />
              <span className="bar-label">{result.period.year}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
