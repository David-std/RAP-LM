// Methodology and sources (RF-08, RD-05, RNF-01; HU-24..HU-27).
// Every number shown here comes from /provenance of the published run.

import { api } from "../api/client";
import type { EvaluationRow, Provenance } from "../api/types";
import { useApi } from "../api/useApi";
import { Notice } from "../components/Controls";
import { GROUP_LABEL } from "../components/DetailPanel";
import { fmtValue } from "../lib/format";

const VARIANT_LABEL: Record<string, string> = {
  cnn_lstm: "CNN-LSTM (arquitectura de referencia)",
  convlstm: "ConvLSTM (Shi et al., 2015; base de Hetero-ConvLSTM)",
  cnn_only: "Solo CNN (ablación)",
  lstm_only: "Solo LSTM (ablación)",
  poisson_glm: "GLM de Poisson (modelo clásico de conteos)",
};

export function MethodologyPage() {
  const prov = useApi((s) => api.provenance({}, s), []);
  if (prov.loading) return <Notice>Cargando metodología…</Notice>;
  if (prov.error || !prov.data) return <Notice tone="error">{prov.error?.message ?? "Sin datos"}</Notice>;
  const p = prov.data;
  return (
    <article className="doc">
      <h1>Metodología y fuentes</h1>
      <p className="lead">
        Qué representa el índice, cómo se obtiene, con qué datos y qué no permite concluir. Cada resultado del mapa
        remite a esta información.
      </p>
      <p className="muted">
        Corrida publicada <code>{p.run.run_id}</code>
        {p.meta.run.published_at && ` el ${new Date(p.meta.run.published_at).toLocaleDateString("es-PE")}`}. Modelo{" "}
        {p.meta.run.model_family}. Dataset <code>{p.meta.run.dataset_version_id}</code>.
      </p>

      <Section title="Qué muestra el mapa">
        <Def term="Población objetivo">{p.target.population}. {p.target.definition}</Def>
        <Def term="Indicador">{p.target.value_unit}.</Def>
        <Def term="Índice 0 a 100">{p.target.index_method}</Def>
        <Def term="Niveles">
          {p.meta.legend.bands.map((b) => `${b.label} ${b.min_index}–${b.max_index}`).join(", ")}. {p.meta.legend.method}
        </Def>
        <Def term="Sin resultado">Se dibuja con trama y nunca se interpreta como riesgo bajo.</Def>
        <Def term="Registro histórico">
          Conteos observados en las fuentes. Son referencia de frecuencia, no el riesgo estimado.
        </Def>
      </Section>

      <Section title="Cómo se obtiene">
        <ol className="steps">
          <li>
            <b>Fuentes y depuración.</b> Cada fuente se registra con URL, licencia, fecha de captura y hash.
          </li>
          <li>
            <b>Fusión.</b> Los atropellos de todas las severidades del censo policial (CENACOM 2011–2017) y los
            siniestros georreferenciados del ONSV (2021–2024) se tratan como observaciones parciales del mismo
            fenómeno, cada una con su factor de registro y su cobertura temporal.
          </li>
          <li>
            <b>Malla regular de 1 km.</b> Las referencias viales policiales se ubican por cruce o tramo de calle de
            OpenStreetMap dentro del distrito declarado; sin coincidencia, el evento queda a nivel distrito. No se
            inventan coordenadas.
          </li>
          <li>
            <b>CNN y LSTM.</b> La CNN extrae patrones espaciales de la malla en cada año; la LSTM recorre la secuencia
            de años. La estimación de un año usa solo información de años anteriores y el contexto urbano.
          </li>
          <li>
            <b>Evaluación.</b> Se compara con el promedio histórico y con modelos de la literatura bajo la misma
            partición temporal, sin usar el año de prueba para entrenar ni seleccionar.
          </li>
        </ol>
      </Section>

      <Section title="Evaluación frente al promedio histórico">
        <Evaluation p={p} />
      </Section>

      <Section title="Fuentes">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Fuente</th>
              <th scope="col">Cobertura</th>
              <th scope="col">Población</th>
              <th scope="col">Licencia</th>
              <th scope="col">Estado</th>
            </tr>
          </thead>
          <tbody>
            {p.sources.map((s) => (
              <tr key={s.source_id}>
                <th scope="row">
                  {s.url ? (
                    <a href={s.url} target="_blank" rel="noreferrer">
                      {s.publisher}
                    </a>
                  ) : (
                    s.publisher
                  )}
                  <div className="muted small">{s.name}</div>
                </th>
                <td>
                  {s.coverage_start ? `${s.coverage_start} a ${s.coverage_end}` : "—"}
                  <div className="muted small">{s.spatial_coverage}</div>
                </td>
                <td>{s.population}</td>
                <td className="small">{s.licence}</td>
                <td>{s.incorporated ? "Incorporada" : <span title={s.exclusion_reason ?? ""}>No incorporada: {s.exclusion_reason}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Variables por grupo conceptual">
        {Object.entries(p.variables_by_group).map(([g, vars]) => (
          <div key={g} className="var-group">
            <h3>{GROUP_LABEL[g]}</h3>
            <ul>
              {vars.map((v) => (
                <li key={v.variable_id} className={v.incorporated ? "" : "excluded"}>
                  <b>{v.label}</b> ({v.unit}, {v.reference_period}). {v.description}{" "}
                  {!v.incorporated && <span className="tag">dimensión no incorporada</span>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </Section>

      <Section title="Limitaciones">
        <ul className="limitations">
          {p.limitations.map((l) => (
            <li key={l.limitation_id}>
              <b>{l.dimension}.</b> {l.description}
            </li>
          ))}
        </ul>
      </Section>
    </article>
  );
}

function Evaluation({ p }: { p: Provenance }) {
  const m = p.run.metrics;
  const rows: EvaluationRow[] = m.test ?? [];
  return (
    <>
      <p>
        Modelo publicado: <b>{VARIANT_LABEL[m.selected_variant] ?? m.selected_variant}</b> ({m.selection_rule}).
        Medida principal E: error absoluto medio de atropellos por distrito y franja en el año de prueba.
      </p>
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Prueba</th>
            <th scope="col">E promedio histórico</th>
            <th scope="col">E modelo</th>
            <th scope="col">Mejora relativa (M-05)</th>
            <th scope="col">Captura 10 % celdas (base / modelo)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.family}-${r.year}`}>
              <th scope="row">
                {r.family.toUpperCase()} {r.year}
                <div className="muted small">{fmtValue(r.observed_events, 0)} eventos</div>
              </th>
              <td className="num">{r.baseline ? fmtValue(r.baseline.district_mae, 3) : "n/a"}</td>
              <td className="num">{fmtValue(r.model.district_mae, 3)}</td>
              <td className="num">{r.relative_improvement_pct === null ? "No calculable" : `${fmtValue(r.relative_improvement_pct, 1)} %`}</td>
              <td className="num">
                {r.baseline ? `${fmtValue(r.baseline.capture_top10 * 100, 0)} %` : "n/a"} /{" "}
                {fmtValue(r.model.capture_top10 * 100, 0)} %
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <details>
        <summary>Benchmark de alternativas (validación y prueba)</summary>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Alternativa</th>
              <th scope="col">NLL validación</th>
              <th scope="col">E prueba</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(m.candidates).map(([v, c]) => (
              <tr key={v} className={v === m.selected_variant ? "selected" : ""}>
                <th scope="row">{VARIANT_LABEL[v] ?? v}</th>
                <td className="num">{fmtValue(c.best_validation_nll, 4)}</td>
                <td className="num">{c.test?.[0] ? fmtValue(c.test[0].model.district_mae, 3) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
      <p className="muted small">
        Factor de registro estimado ONSV/CENACOM: {fmtValue(m.reporting_factor.onsv ?? null, 4)}. Las métricas de
        utilidad para usuarios se miden aparte en las sesiones de validación.
      </p>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="doc-section">
      <h2>{title}</h2>
      <div>{children}</div>
    </section>
  );
}

function Def({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="def">
      <dt>{term}</dt>
      <dd>{children}</dd>
    </div>
  );
}
