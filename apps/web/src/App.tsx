// Application shell: top bar, views and status bar. Loads the reference data
// (periods, cell and district geometry) once and shares it with every view.

import { useEffect, useMemo, useState } from "react";

import { api } from "./api/client";
import type { Meta, UnitCollection } from "./api/types";
import { useApi } from "./api/useApi";
import { Notice } from "./components/Controls";
import { BANDS, DAY_LABEL, fmtNumber } from "./lib/format";
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
        <section className="boot-card" role="alert">
          <h1>No se pudieron cargar los resultados</h1>
          <p>
            El servicio de datos no respondió. Si usa la demostración en línea, el servidor puede tardar hasta un minuto
            en activarse; vuelva a intentarlo. La aplicación no muestra datos simulados en su lugar.
          </p>
          <button type="button" className="btn primary" onClick={() => window.location.reload()}>
            Volver a intentar
          </button>
          <p className="boot-detail">Detalle técnico: {error.message}</p>
        </section>
      </div>
    );
  }
  if (!periods.data || !cells.data || !districts.data) {
    return <Booting />;
  }
  return (
    <QueryProvider periods={periods.data.data}>
      <Shell meta={periods.data.meta} cells={cells.data} districts={districts.data} />
    </QueryProvider>
  );
}

function Booting() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setSlow(true), 6000);
    return () => window.clearTimeout(id);
  }, []);
  return (
    <div className="boot" role="status">
      <section className="boot-card">
        <h1>Cargando RAP-LM</h1>
        <p>{slow ? "El servidor se está activando. Puede tardar hasta un minuto la primera vez." : "Cargando periodos, malla y distritos."}</p>
      </section>
    </div>
  );
}

function Shell({ meta, cells, districts }: { meta: Meta; cells: UnitCollection; districts: UnitCollection }) {
  const [view, setView] = useState<View>("map");
  const [corridorDistrict, setCorridorDistrict] = useState<string | null>(null);
  const q = useQuery();
  const bands = useMemo(() => classBands(meta.legend), [meta.legend]);
  // Task views first; documentation is a separate, quieter group (information architecture).
  const tabs: { id: View; label: string; doc?: boolean }[] = [
    { id: "map", label: "Mapa de riesgo" },
    { id: "forecast", label: "Pronóstico" },
    { id: "corridors", label: "Vías críticas" },
    { id: "compare", label: "Comparar" },
    { id: "analysis", label: "Análisis" },
    { id: "model", label: "Modelo", doc: true },
    { id: "method", label: "Metodología y fuentes", doc: true },
  ];
  const modelLabel = meta.run.is_demo ? "Datos de ejemplo" : `Modelo ${meta.run.run_id.split("-").pop()}`;
  return (
    <div className="app">
      <header className="topbar">
        <button type="button" className="brand" aria-label="RAP-LM, ir al mapa de riesgo" onClick={() => setView("map")}>
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-text">
            <span className="brand-name"><span className="brand-accent">RAP</span>-<span className="brand-accent2">LM</span></span>
            <small>Riesgo de atropello peatonal, Lima Metropolitana</small>
          </span>
        </button>
        <nav aria-label="Vistas">
          {tabs.map((t, i) => (
            <button
              key={t.id}
              type="button"
              className={`tab${view === t.id ? " on" : ""}${t.doc ? " tab-doc" : ""}${t.doc && !tabs[i - 1]?.doc ? " tab-doc-first" : ""}`}
              aria-current={view === t.id ? "page" : undefined}
              onClick={() => setView(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="topbar-meta">
          <span title={`Corrida ${meta.run.run_id}`}>
            {modelLabel}
          </span>
          <a href="https://github.com/David-std2/RAP-LM" target="_blank" rel="noreferrer" className="topbar-link">
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            Código
          </a>
        </div>
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
          Zona: <b>{q.selectedUnitId ?? "ninguna"}</b>
        </span>
        <span>
          Periodo:{" "}
          <b>
            {q.active.year}, {DAY_LABEL[q.active.dayType].toLowerCase()}, {BANDS[q.active.band]}
          </b>
        </span>
        <span>
          Malla: <b>1 km, {fmtNumber(cells.features.length)} celdas, {districts.features.length} distritos</b>
        </span>
        <span className="grow" />
        <span className={meta.run.is_demo ? "status-demo" : "status-run"} title={`Corrida ${meta.run.run_id}. ${meta.scope_notice}`}>
          Dataset {meta.run.dataset_version_id.replace("fused-", "")}, corrida {meta.run.run_id}
        </span>
      </footer>
    </div>
  );
}
