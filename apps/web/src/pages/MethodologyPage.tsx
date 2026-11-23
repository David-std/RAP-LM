// Methodology and sources (RF-08, RD-05, RNF-01; HU-24..HU-27). Sources,
// variables and limitations come from /provenance of the published run.

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { Notice } from "../components/Controls";
import { GROUP_LABEL } from "../components/ZonePanel";

export function MethodologyPage() {
  const prov = useApi((s) => api.provenance({}, s), []);
  if (prov.loading) return <div className="page"><div className="page-inner"><Notice>Cargando…</Notice></div></div>;
  if (prov.error || !prov.data) return <div className="page"><div className="page-inner"><Notice tone="error">{prov.error?.message ?? "Sin datos"}</Notice></div></div>;
  const p = prov.data;
  const bands = p.meta.legend.bands;
  return (
    <div className="page">
      <div className="page-inner">
        <header className="page-header">
          <div>
            <p className="eyebrow">Metodología y fuentes</p>
            <h1>Qué representa cada resultado y de dónde viene</h1>
            <p>Corrida <code>{p.run.run_id}</code>, dataset <code>{p.meta.run.dataset_version_id}</code>. Cada valor del mapa remite a esta información.</p>
          </div>
        </header>

        <div className="grid cols-3">
          <section className="card">
            <h3>Frecuencia</h3>
            <p className="card-sub">Índice principal del mapa</p>
            <p className="card-note" style={{ color: "var(--ink-2)" }}>{p.target.population}. Indicador: {p.target.value_unit}. {p.target.index_method}</p>
          </section>
          <section className="card">
            <h3>Severidad esperada</h3>
            <p className="card-sub">Componente de consecuencias</p>
            <p className="card-note" style={{ color: "var(--ink-2)" }}>Frecuencia estimada × probabilidad de desenlace fatal de la zona, calculada con los años de entrenamiento y suavizada hacia el distrito y la ciudad cuando hay pocos eventos.</p>
          </section>
          <section className="card">
            <h3>Riesgo por exposición</h3>
            <p className="card-sub">Componente de exposición</p>
            <p className="card-note" style={{ color: "var(--ink-2)" }}>Razón entre la frecuencia estimada y la que explicaría solo la exposición (población, comercio, transporte, veredas y vías arteriales). Mayor que 1: más atropellos de los esperados por la exposición.</p>
          </section>
        </div>

        <div className="grid cols-2">
          <section className="card">
            <header><h2>Niveles y lectura</h2></header>
            <dl className="kv">
              <dt>Bajo</dt><dd>índice menor que {bands[0].max_index}</dd>
              <dt>Medio</dt><dd>de {bands[1].min_index} a {bands[1].max_index - 1}</dd>
              <dt>Alto</dt><dd>desde {bands[2].min_index} (umbrales {p.meta.legend.version}, fijados antes de la prueba)</dd>
              <dt>Sin resultado</dt><dd>trama rayada; no equivale a riesgo bajo</dd>
              <dt>Registro histórico</dt><dd>conteos observados; referencia de frecuencia, no el riesgo estimado</dd>
            </dl>
          </section>
          <section className="card">
            <header><h2>Cómo se obtiene</h2></header>
            <ol className="steps">
              <li><b>Fuentes:</b> cada una con URL, licencia, fecha de captura y hash.</li>
              <li><b>Fusión:</b> censo de comisarías 2011-2017 (todas las severidades) y ONSV 2021-2024 como observaciones parciales del mismo fenómeno.</li>
              <li><b>Ubicación:</b> referencias policiales comparadas con calles de OpenStreetMap del distrito; sin coincidencia, el evento queda a nivel distrito. No se inventan coordenadas.</li>
              <li><b>Red CNN-RNN:</b> patrones espaciales por año y secuencia de años; cada año usa solo información anterior.</li>
              <li><b>Evaluación:</b> frente al promedio histórico y otras arquitecturas, ver la vista Modelo.</li>
            </ol>
          </section>
        </div>

        <section>
          <h2 style={{ fontSize: 15, marginBottom: 10 }}>Fuentes</h2>
          <div className="doc-grid">
            {p.sources.map((s) => (
              <article key={s.source_id} className="card">
                <header>
                  <h3>{s.publisher}</h3>
                  <span className={s.incorporated ? "chip accent" : "chip"}>{s.incorporated ? "Incorporada" : "No incorporada"}</span>
                </header>
                <p className="small">{s.name}</p>
                <div className="meta-row">
                  {s.coverage_start && <span className="chip">{s.coverage_start.slice(0, 4)}-{s.coverage_end?.slice(0, 4)}</span>}
                  {s.captured_at && <span className="chip">capturada {s.captured_at}</span>}
                </div>
                <p className="small muted">{s.spatial_coverage}. {s.population}.</p>
                {!s.incorporated && s.exclusion_reason && <p className="small" style={{ marginTop: 6 }}><b>Motivo:</b> {s.exclusion_reason}</p>}
                <p className="small muted" style={{ marginTop: 6 }}>{s.licence}</p>
                {s.url && <a className="link-btn small" href={s.url} target="_blank" rel="noreferrer">Abrir fuente</a>}
              </article>
            ))}
          </div>
        </section>

        <section>
          <h2 style={{ fontSize: 15, marginBottom: 10 }}>Variables por grupo conceptual</h2>
          <div className="grid cols-4">
            {Object.entries(p.variables_by_group).map(([g, vars]) => (
              <article key={g} className="card">
                <h3>{GROUP_LABEL[g] ?? g}</h3>
                <ul className="steps" style={{ marginTop: 8 }}>
                  {vars.map((v) => (
                    <li key={v.variable_id} className={v.incorporated ? "" : "excluded"} title={v.description}>
                      {v.label} <span className="muted small">({v.reference_period})</span>
                      {!v.incorporated && <span className="tag">no incorporada</span>}
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section>
          <h2 style={{ fontSize: 15, marginBottom: 10 }}>Limitaciones</h2>
          <div className="doc-grid">
            {p.limitations.map((l) => (
              <article key={l.limitation_id} className="card">
                <h3>{l.dimension}</h3>
                <p className="small" style={{ marginTop: 6, color: "var(--ink-2)" }}>{l.description}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
