// Application shell: top bar, views and status bar. Loads the reference data
// (periods, cell and district geometry) once and shares it with every view.

import { useMemo, useState } from "react";

import { api } from "./api/client";
import type { Meta, UnitCollection } from "./api/types";
import { useApi } from "./api/useApi";
import { Notice } from "./components/Controls";
import { BANDS, DAY_LABEL } from "./lib/format";
import { classBands } from "./lib/levels";
import { AnalysisPage } from "./pages/AnalysisPage";
import { ComparePage } from "./pages/ComparePage";
import { CorridorsPage } from "./pages/CorridorsPage";
import { ForecastPage } from "./pages/ForecastPage";
import { MapPage } from "./pages/MapPage";
import { MethodologyPage } from "./pages/MethodologyPage";
import { ModelPage } from "./pages/ModelPage";
import { QueryProvider, useQuery } from "./state/QueryContext";

type View = "map" | "forecast" | "corridors" | "compare" | "analysis" | "model" | "method";

export default function App() {
  const periods = useApi((s) => api.periods(s), []);
  const cells = useApi((s) => api.units("cell", s), []);
  const districts = useApi((s) => api.units("district", s), []);

  const error = periods.error ?? cells.error ?? districts.error;
  if (error) {
    return (
      <div className="boot">
        <Notice tone="error">
          No se pudo conectar con la API de resultados publicados: {error.message}. No se muestran datos simulados en su
          lugar.
        </Notice>
      </div>
    );
  }
  if (!periods.data || !cells.data || !districts.data) {
    return <div className="boot">Cargando RAP-LM…</div>;
  }
  return (
    <QueryProvider periods={periods.data.data}>
      <Shell meta={periods.data.meta} cells={cells.data} districts={districts.data} />
    </QueryProvider>
  );
}

function Shell({ meta, cells, districts }: { meta: Meta; cells: UnitCollection; districts: UnitCollection }) {
  const [view, setView] = useState<View>("map");
  const [corridorDistrict, setCorridorDistrict] = useState<string | null>(null);
  const q = useQuery();
  const bands = useMemo(() => classBands(meta.legend), [meta.legend]);
  const tabs: { id: View; label: string }[] = [
    { id: "map", label: "Mapa de riesgo" },
    { id: "forecast", label: "Pronóstico" },
    { id: "corridors", label: "Vías críticas" },
    { id: "compare", label: "Comparar" },
    { id: "analysis", label: "Análisis" },
    { id: "model", label: "Modelo" },
    { id: "method", label: "Metodología y fuentes" },
  ];
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand" aria-label="RAP-LM">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-text">
            <span className="brand-name"><span className="brand-accent">RAP</span>-<span className="brand-accent2">LM</span></span>
            <small>Riesgo de atropello peatonal, Lima Metropolitana</small>
          </span>
        </span>
        <nav aria-label="Vistas">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              className={view === t.id ? "tab on" : "tab"}
              aria-current={view === t.id ? "page" : undefined}
              onClick={() => setView(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <span className="topbar-run" title={meta.scope_notice}>{meta.run.is_demo ? "Datos de ejemplo" : `corrida ${meta.run.run_id}`}</span>
      </header>

      {meta.run.is_demo && <div className="demo-banner">{meta.scope_notice}</div>}

      <div className="views">
        {view === "map" && (
          <MapPage
            units={cells}
            districts={districts}
            legend={meta.legend}
            goCompare={(mode) => {
              q.setCompareMode(mode);
              setView("compare");
            }}
            goCorridors={(d) => {
              setCorridorDistrict(d);
              setView("corridors");
            }}
          />
        )}
        {view === "compare" && <ComparePage units={cells} districts={districts} legend={meta.legend} />}
        {view === "analysis" && (
          <AnalysisPage
            units={cells}
            districts={districts}
            legend={meta.legend}
            meta={meta}
            openUnit={(id) => {
              q.select(id);
              setView("map");
            }}
          />
        )}
        {view === "corridors" && <CorridorsPage districts={districts} meta={meta} bands={bands} initialDistrict={corridorDistrict} />}
        {view === "forecast" && <ForecastPage units={cells} districts={districts} legend={meta.legend} />}
        {view === "model" && <ModelPage />}
        {view === "method" && <MethodologyPage />}
      </div>

      <footer className="statusbar">
        <span>
          Unidad: <b>{q.selectedUnitId ?? "—"}</b>
        </span>
        <span>
          Periodo:{" "}
          <b>
            {q.active.year}, {DAY_LABEL[q.active.dayType].toLowerCase()}, {BANDS[q.active.band]}
          </b>
        </span>
        <span>
          Malla: <b>1 km, {cells.features.length.toLocaleString("es-PE")} celdas, {districts.features.length} distritos</b>
        </span>
        <span className="grow" />
        <span className={meta.run.is_demo ? "status-demo" : "status-run"} title={meta.scope_notice}>
          {meta.run.is_demo ? "Datos de ejemplo" : `Corrida publicada ${meta.run.run_id}`}
        </span>
      </footer>
    </div>
  );
}
