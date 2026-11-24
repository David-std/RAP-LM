// Methodology and sources (RF-08, RD-05, RNF-01; HU-24..HU-27). Sources,
// variables and limitations come from /provenance of the published run.

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { Notice } from "../components/Controls";
import { DocPage, DocTable, type DocSection } from "../components/Doc";
import { GROUP_LABEL } from "../components/ZonePanel";

const year = (d?: string | null) => (d ? d.slice(0, 4) : "");
const period = (start?: string | null, end?: string | null) => {
  if (!start) return "—";
  const a = year(start);
  const b = year(end);
  return !b || a === b ? a : `${a}–${b}`;
};

export function MethodologyPage() {
  const prov = useApi((s) => api.provenance({}, s), []);
  if (prov.loading) return <div className="page"><div className="page-inner"><Notice>Cargando…</Notice></div></div>;
  if (prov.error || !prov.data) {
    return <div className="page"><div className="page-inner"><Notice tone="error">{prov.error?.message ?? "Sin datos"}</Notice></div></div>;
  }
  const p = prov.data;
  const bands = p.meta.legend.bands;
  const incorporated = p.sources.filter((s) => s.incorporated);
  const excluded = p.sources.filter((s) => !s.incorporated);

  const sections: DocSection[] = [
    {
      id: "indicadores",
      title: "Qué muestra el mapa",
      body: (
        <>
          <p>
            Cada celda o distrito tiene tres valores para el periodo elegido. Ninguno es un conteo observado ni una
            probabilidad individual de sufrir un atropello.
          </p>
          <dl className="doc-defs">
            <dt>Frecuencia</dt>
            <dd>
              {p.target.population}. Se expresa como {p.target.value_unit}. {p.target.index_method}
            </dd>
            <dt>Severidad esperada</dt>
            <dd>
              Frecuencia estimada multiplicada por la probabilidad de desenlace fatal de la zona. Esa probabilidad se
              calcula con los años de entrenamiento y se acerca a la del distrito y la ciudad cuando la zona tiene pocos
              eventos.
            </dd>
            <dt>Frente al contexto</dt>
            <dd>
              Cociente entre la frecuencia estimada por la red y la que predice un modelo de Poisson que solo usa variables
              de contexto: población, comercio, transporte, veredas y vías arteriales. Un valor mayor que 1 indica más
              atropellos de los que el contexto explica. No es una tasa por peatón, porque Lima no tiene conteos de
              peatones, y no indica causa.
            </dd>
          </dl>
        </>
      ),
    },
    {
      id: "niveles",
      title: "Niveles",
      body: (
        <>
          <p>
            El índice ordena cada valor dentro de la distribución de los años de entrenamiento. Los umbrales (
            {p.meta.legend.version}) se fijaron antes de evaluar la prueba y no cambian entre periodos.
          </p>
          <DocTable n={1} caption="Lectura del índice y de las capas del mapa.">
            <thead>
              <tr><th scope="col">Nivel</th><th scope="col">Índice</th><th scope="col">Lectura</th></tr>
            </thead>
            <tbody>
              <tr><th scope="row">Bajo</th><td className="num">0 a {bands[0].max_index - 1}</td><td>Por debajo del 40 % de los valores de referencia</td></tr>
              <tr><th scope="row">Medio</th><td className="num">{bands[1].min_index} a {bands[1].max_index - 1}</td><td>Entre el 40 % y el 70 %</td></tr>
              <tr><th scope="row">Alto</th><td className="num">{bands[2].min_index} a 100</td><td>El 30 % superior</td></tr>
              <tr className="group-start"><th scope="row">Sin resultado</th><td className="num">—</td><td>Trama rayada. No equivale a riesgo bajo</td></tr>
              <tr><th scope="row">Registro histórico</th><td className="num">—</td><td>Conteos observados en las fuentes, como referencia; no es el riesgo estimado</td></tr>
            </tbody>
          </DocTable>
        </>
      ),
    },
    {
      id: "proceso",
      title: "Proceso",
      body: (
        <ol>
          <li><strong>Captura.</strong> Cada fuente se guarda con su URL, licencia, fecha de captura y huella SHA-256.</li>
          <li><strong>Fusión.</strong> El censo de comisarías 2011–2017 (todas las severidades) y el ONSV 2021–2024 (fatales) se tratan como observaciones parciales del mismo fenómeno.</li>
          <li><strong>Ubicación.</strong> La dirección policial se busca entre las calles de OpenStreetMap del distrito. Si no coincide, el evento se conserva solo a nivel de distrito; no se inventan coordenadas.</li>
          <li><strong>Estimación.</strong> La red CNN-RNN aprende patrones espaciales de cada año y su secuencia; cada año usa solo información anterior.</li>
          <li><strong>Evaluación.</strong> Se compara con el promedio histórico en años que no intervienen en el entrenamiento. Los resultados están en la vista Modelo.</li>
          <li><strong>Publicación.</strong> Los resultados se cargan a la base de datos en una sola operación; la aplicación solo los consulta.</li>
        </ol>
      ),
    },
    {
      id: "fuentes",
      title: "Fuentes",
      body: (
        <>
          <DocTable n={2} caption={`Fuentes incorporadas (${incorporated.length}).`} wide>
            <thead>
              <tr><th scope="col">Fuente</th><th scope="col">Contenido</th><th scope="col" className="num">Periodo</th><th scope="col">Cobertura</th></tr>
            </thead>
            <tbody>
              {incorporated.map((s) => (
                <tr key={s.source_id}>
                  <th scope="row">
                    {s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.publisher}</a> : s.publisher}
                    {s.captured_at && <span className="sub">Captura {s.captured_at}</span>}
                  </th>
                  <td>{s.name}<span className="sub">{s.licence}</span></td>
                  <td className="num">{period(s.coverage_start, s.coverage_end)}</td>
                  <td>{s.spatial_coverage}. {s.population}.</td>
                </tr>
              ))}
            </tbody>
          </DocTable>
          {excluded.length > 0 && (
            <DocTable n={3} caption={`Fuentes evaluadas y no incorporadas (${excluded.length}).`} wide>
              <thead>
                <tr><th scope="col">Fuente</th><th scope="col">Contenido</th><th scope="col">Motivo</th></tr>
              </thead>
              <tbody>
                {excluded.map((s) => (
                  <tr key={s.source_id}>
                    <th scope="row">{s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.publisher}</a> : s.publisher}</th>
                    <td>{s.name}</td>
                    <td>{s.exclusion_reason ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </DocTable>
          )}
        </>
      ),
    },
    {
      id: "variables",
      title: "Variables",
      body: (
        <DocTable n={excluded.length > 0 ? 4 : 3} caption="Variables por grupo conceptual, con su periodo de referencia.">
          <thead>
            <tr><th scope="col">Grupo</th><th scope="col">Variable</th><th scope="col" className="num">Periodo</th><th scope="col">Estado</th></tr>
          </thead>
          <tbody>
            {Object.entries(p.variables_by_group).flatMap(([g, vars]) =>
              vars.map((v, i) => (
                <tr key={v.variable_id} className={i === 0 ? "group-start" : undefined} title={v.description}>
                  <th scope="row">{i === 0 ? GROUP_LABEL[g] ?? g : ""}</th>
                  <td>{v.label}</td>
                  <td className="num">{v.reference_period}</td>
                  <td>{v.incorporated ? "Incorporada" : "No incorporada"}</td>
                </tr>
              )),
            )}
          </tbody>
        </DocTable>
      ),
    },
    {
      id: "limitaciones",
      title: "Limitaciones",
      body: (
        <dl className="doc-defs">
          {p.limitations.flatMap((l) => [
            <dt key={`${l.limitation_id}t`}>{l.dimension}</dt>,
            <dd key={`${l.limitation_id}d`}>{l.description}</dd>,
          ])}
        </dl>
      ),
    },
  ];

  return (
    <DocPage
      title="Metodología y fuentes"
      lead="Qué representa cada valor del mapa, cómo se calcula y de qué registros proviene."
      meta={<>Corrida <code>{p.run.run_id}</code>, dataset <code>{p.meta.run.dataset_version_id}</code></>}
      sections={sections}
    />
  );
}
