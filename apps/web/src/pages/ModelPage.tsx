// Model view: technical documentation of the published CNN-RNN (RM-01..RM-05, RNF-02).
// Every number comes from /model (model card of the published run).

import { api } from "../api/client";
import type { ModelCardDto, NoiseCeilingRow, PrioritisationRow, RankingScores } from "../api/types";
import { useApi } from "../api/useApi";
import { LineChart } from "../components/charts";
import { Notice } from "../components/Controls";
import { DocPage, DocTable, Figure, type DocSection } from "../components/Doc";
import { VARIABLE_LABEL } from "../components/ZonePanel";
import { fmtNumber } from "../lib/format";

type Card = ModelCardDto["card"];

const VARIANT_LABEL: Record<string, string> = {
  cnn_lstm: "CNN seguida de LSTM",
  convlstm: "ConvLSTM",
  cnn_only: "Solo CNN (ablación)",
  lstm_only: "Solo LSTM (ablación)",
  poisson_glm: "GLM de Poisson",
};
const FAMILY_LABEL: Record<string, string> = { cenacom: "CENACOM", onsv: "ONSV" };
const FAMILY_POPULATION: Record<string, string> = {
  cenacom: "atropellos de todas las severidades",
  onsv: "siniestros fatales con peatón",
};
const CHANNEL_LABEL: Record<string, string> = {
  valid_cell: "Celda dentro de los 43 distritos",
  cenacom_prev_cell_rate: "CENACOM del año anterior, por celda",
  cenacom_prev_district_density: "CENACOM del año anterior, densidad del distrito",
  cenacom_prev_observed: "Año anterior observado por CENACOM",
  onsv_prev_cell_rate: "ONSV del año anterior, por celda",
  onsv_prev_district_density: "ONSV del año anterior, densidad del distrito",
  onsv_prev_observed: "Año anterior observado por ONSV",
};

const dec = (v: number | null | undefined, d = 2) => (v == null ? "n/a" : v.toFixed(d).replace(".", ","));
const pct = (v: number | null | undefined, d = 1) => (v == null ? "n/a" : `${(v * 100).toFixed(d).replace(".", ",")} %`);
const signed = (v: number | null | undefined, d = 1) =>
  v == null ? "n/a" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(d).replace(".", ",")} %`;
const int = (v: number) => fmtNumber(v);

export function ModelPage() {
  const model = useApi((s) => api.model(s), []);
  if (model.loading) return <div className="page"><div className="page-inner"><Notice>Cargando…</Notice></div></div>;
  if (model.error || !model.data) {
    return (
      <div className="page">
        <div className="page-inner">
          <Notice tone="warn">La corrida publicada aún no tiene ficha del modelo ({model.error?.message}).</Notice>
        </div>
      </div>
    );
  }
  return <ModelDoc data={model.data} />;
}

function ModelDoc({ data }: { data: ModelCardDto }) {
  const { card, benchmark } = data;
  const prio = card.prioritisation ?? [];
  const ceiling = card.noise_ceiling ?? [];
  const main = benchmark.test?.[0];
  const onsv = prio.find((r) => r.fold === "onsv");
  const gpu = String(card.config.device ?? "cpu").startsWith("cuda");
  const trainYears = (fam: string) => card.split.train?.[fam] ?? [];
  const span = (ys: number[]) => (ys.length ? `${ys[0]}–${ys[ys.length - 1]}` : "—");

  const sections: DocSection[] = [
    {
      id: "resumen",
      title: "Resumen",
      body: (
        <>
          <p>
            El modelo estima la intensidad esperada de atropellos de peatones en cada celda de 1 km de los 43 distritos
            de Lima Metropolitana, por año, tipo de día y franja de seis horas. Es un ensamble de {card.members} redes{" "}
            {VARIANT_LABEL[card.variant] ?? card.variant}: una parte convolucional lee el entorno de cada celda y una parte
            recurrente recorre los años en orden, usando solo información anterior al año que estima.
          </p>
          {onsv && (
            <p>
              En {onsv.test_year}, año que no intervino en el entrenamiento ni en la elección del modelo, el 20 % de las
              celdas con mayor riesgo estimado concentró el <strong>{pct(onsv.cell_year.model.capture_top20, 0)}</strong>{" "}
              de los {FAMILY_POPULATION.onsv} registrados, frente al {pct(onsv.cell_year.historical_average.capture_top20, 0)}{" "}
              del promedio histórico. El área bajo la curva ROC fue {dec(onsv.cell_year.model.auc)} (promedio histórico{" "}
              {dec(onsv.cell_year.historical_average.auc)}; azar 0,50).
            </p>
          )}
          {onsv && <SummaryTable row={onsv} m05={main?.relative_improvement_pct ?? null} />}
        </>
      ),
    },
    {
      id: "datos",
      title: "Datos y partición",
      body: (
        <>
          <p>
            La red aprende de dos registros que observan el mismo fenómeno con distinta cobertura. El Censo Nacional de
            Comisarías (CENACOM, {span(trainYears("cenacom"))}) registra atropellos de todas las severidades. El
            Observatorio Nacional de Seguridad Vial (ONSV, desde 2021) registra solo siniestros con al menos un fallecido.
            Ambas fuentes se vinculan a la misma intensidad mediante un factor de registro propio y la fracción del año que
            cubren.
          </p>
          <p>
            La partición es cronológica. Los años de prueba no se usan para entrenar, detener el entrenamiento ni elegir la
            configuración.
          </p>
          <Figure n={1} caption="Uso de cada año por fuente. Entre 2018 y 2020 no hay registro disponible.">
            <Partitions split={card.split} />
          </Figure>
        </>
      ),
    },
    {
      id: "arquitectura",
      title: "Arquitectura",
      body: (
        <>
          <p>
            La entrada es un tensor de {card.input_channels.length} variables por celda y año sobre una malla de{" "}
            {card.tensor_shapes.X?.[2]} × {card.tensor_shapes.X?.[3]} celdas.{" "}
            {card.variant === "convlstm"
              ? "En cada año, la ConvLSTM aplica una convolución 3 × 3 sobre la entrada y sobre su propio estado del año anterior; cada celda combina así su vecindario inmediato con una memoria que se extiende un kilómetro más por cada año previo."
              : "Dos convoluciones 3 × 3 por año dan a cada celda un vecindario de 5 × 5 km; una LSTM por celda recorre luego los años."}{" "}
            La salida λ es la intensidad latente en las 8 combinaciones de tipo de día y franja.
            El operador de observación convierte λ en los conteos esperados de cada fuente, a nivel de celda para los
            eventos ubicados y de distrito para los que solo tienen distrito.
          </p>
          <Figure n={2} caption={<>Flujo de los datos por la red. Las dimensiones se leen años × canales × filas × columnas.</>}>
            <Architecture card={card} />
          </Figure>
          <DocTable n={2} caption="Configuración del modelo publicado.">
            <tbody>
              <tr><th scope="row">Variante</th><td>{VARIANT_LABEL[card.variant] ?? card.variant}, {card.config.hidden} canales ocultos</td></tr>
              <tr><th scope="row">Parámetros entrenables</th><td>{int(card.parameters)} por red, ensamble de {card.members}</td></tr>
              <tr><th scope="row">Optimización</th><td>Adam, tasa {String(card.config.lr).replace(".", ",")}, decaimiento de pesos {String(card.config.weight_decay).replace(".", ",")}{card.variant === "convlstm" ? "" : `, dropout ${String(card.config.dropout).replace(".", ",")}`}</td></tr>
              <tr><th scope="row">Pérdida</th><td>Verosimilitud de Poisson de los conteos observados, por evento</td></tr>
              <tr><th scope="row">Detención</th><td>Hasta {card.config.max_epochs} épocas; se conserva la de menor pérdida de validación (paciencia {card.config.patience})</td></tr>
              <tr><th scope="row">Factor de registro</th><td>ONSV respecto a CENACOM: {dec(card.reporting_factor.onsv, 3)}</td></tr>
            </tbody>
          </DocTable>
        </>
      ),
    },
    {
      id: "entrenamiento",
      title: "Entrenamiento",
      body: (
        <>
          <p>
            Cada red del ensamble parte de una semilla distinta. El entrenamiento completo, con la búsqueda de
            configuración y el ensamble, tomó {Math.round(card.elapsed_seconds / 60)} minutos en{" "}
            {gpu ? "GPU" : `CPU (${card.config.threads} hilos)`} con PyTorch {card.torch}. Repetirlo produce pesos idénticos
            byte a byte.
          </p>
          <Figure n={3} caption="Pérdida de Poisson por época de la primera red del ensamble. La línea vertical marca la época conservada.">
            <TrainingCurves card={card} />
          </Figure>
        </>
      ),
    },
    {
      id: "priorizacion",
      title: "Priorización espacial",
      body: (
        <>
          <p>
            La pregunta operativa es dónde intervenir primero. Para responderla se ordenan las 2 899 celdas por su riesgo
            estimado en el año de prueba y se mide cuántos de los atropellos registrados caen en las primeras. Estas medidas
            no dependen del volumen total registrado, solo del orden.
          </p>
          {prio.length > 0 ? <PrioritisationTable rows={prio} /> : <p>La corrida publicada no incluye este reporte.</p>}
          <p>
            En la serie fatal de 2024 la red ordena mejor que el promedio histórico en todas las medidas. En la serie de
            todas las severidades de 2017 ambos ordenan casi igual de bien: allí el historial de cada celda ya explica la
            mayor parte de la distribución.
          </p>
        </>
      ),
    },
    {
      id: "conteo",
      title: "Error de conteo",
      body: (
        <>
          <p>
            El indicador M-05 del plan compara el error absoluto medio de atropellos por distrito y franja con el del
            promedio histórico de la misma fuente. Con conteos tan bajos (0,7 eventos por distrito y franja en ONSV), una
            parte del error es variación aleatoria que ningún modelo puede anticipar. La última columna estima la mejora
            máxima posible si la intensidad estimada fuera exacta.
          </p>
          {ceiling.length > 0 && <CeilingTable rows={ceiling} />}
          <p>
            En ONSV 2024 la red obtiene la mayor parte de la mejora alcanzable. En CENACOM 2017 ambos métodos subestiman el
            total: el registro policial de Lima pasó de unos 710 accidentes mensuales en 2016 a unos 1 230 en el primer
            semestre de 2017, y ningún dato anterior anticipa ese cambio. La red, que sigue la tendencia descendente de
            2012–2016, estima un total algo menor que el promedio histórico y por eso su error es mayor.
          </p>
        </>
      ),
    },
    ...(card.high_level
      ? [
          {
            id: "nivel-alto",
            title: "Nivel alto",
            body: (
              <>
                <p>
                  El mapa clasifica como alto todo índice de 70 o más, es decir, el 30 % superior de la escala de
                  referencia. Cuando la serie de prueba es rara, como los atropellos fatales, ese umbral marca muchas más
                  unidades que positivos hay, y la precisión queda acotada aunque el orden sea correcto.
                </p>
                <HighLevelTable card={card} />
              </>
            ),
          },
        ]
      : []),
    {
      id: "explicaciones",
      title: "Cómo se explica la red",
      body: (
        <>
          <p>
            Cada zona del mapa trae tres explicaciones, calculadas fuera de línea con el modelo publicado. Las tres describen
            en qué se apoya la red; ninguna identifica causas de los atropellos.
          </p>
          <dl className="doc-defs">
            <dt>Grad-CAM</dt>
            <dd>
              Para la zona elegida, se toma su riesgo estimado en 2024 y se recorre la red hacia atrás hasta sus estados
              internos. En cada celda se multiplica la activación por el gradiente, es decir, cuánto cambiaría la
              estimación si esa activación cambiara, y se suman los aportes positivos de todos los años que la memoria
              recorre. Se usa la variante HiResCAM (Draelos y Carin, 2020), que conserva el gradiente de cada celda en
              lugar de promediarlo sobre todo el mapa como el Grad-CAM original (Selvaraju et al., 2017). Así solo se
              resaltan celdas que la red realmente puede leer desde la zona. El resultado se promedia sobre las cinco redes
              y se escala para que la celda más influyente valga 100 %.
            </dd>
            <dt>Qué impulsa la estimación</dt>
            <dd>
              Se reemplaza un grupo de variables a la vez por un valor neutro, el promedio de Lima para el contexto o
              ningún evento previo para el historial, y se mide cuánto cambia la estimación de la zona en porcentaje. Un
              valor positivo indica que el valor real de ese grupo eleva el riesgo estimado frente al neutro.
            </dd>
            <dt>Simulación de contexto</dt>
            <dd>
              Se multiplica una variable en las celdas del distrito, manteniendo las demás, y se registra la respuesta de
              la red. Muestra la sensibilidad del modelo, no el efecto de una intervención real.
            </dd>
          </dl>
        </>
      ),
    },
    ...(card.search?.length
      ? [
          {
            id: "seleccion",
            title: "Selección de configuración",
            body: (
              <>
                <p>
                  Se probaron {card.search.length} configuraciones y se eligió la de menor error de validación por distrito
                  y franja. La elegida se entrena luego con {card.members} semillas.
                </p>
                <SearchTable card={card} />
              </>
            ),
          },
        ]
      : []),
    {
      id: "variables",
      title: "Variables de entrada",
      body: <ChannelsTable card={card} />,
    },
    {
      id: "reproducibilidad",
      title: "Reproducibilidad",
      body: (
        <>
          <dl className="doc-kv">
            <dt>Corrida</dt><dd><code>{card.run_id}</code></dd>
            <dt>Commit del código</dt><dd><code>{card.code_commit_sha.slice(0, 12)}</code></dd>
            <dt>SHA-256 de los pesos</dt><dd><code>{card.weights_sha256}</code></dd>
            <dt>Entorno</dt><dd>PyTorch {card.torch}, {gpu ? "GPU" : "CPU"}, semilla {card.config.seed}</dd>
          </dl>
          <details className="doc-details">
            <summary>Capas de la red ({card.layers.length})</summary>
            <div className="doc-mono">{card.layers.join("\n")}</div>
          </details>
        </>
      ),
    },
  ];

  return (
    <DocPage
      title="Modelo de riesgo"
      lead="Cómo se construye, entrena y evalúa la red que estima el riesgo de atropello peatonal en Lima Metropolitana."
      meta={<>Corrida publicada <code>{card.run_id}</code></>}
      sections={sections}
    />
  );
}

function SummaryTable({ row, m05 }: { row: PrioritisationRow; m05: number | null }) {
  const m = row.cell_year.model;
  const h = row.cell_year.historical_average;
  const r = row.cell_year.random_expected;
  const line = (label: string, a: string, b: string, c: string, best: boolean) => (
    <tr>
      <th scope="row">{label}</th>
      <td className={best ? "num best" : "num"}>{a}</td>
      <td className="num">{b}</td>
      <td className="num">{c}</td>
    </tr>
  );
  return (
    <DocTable
      n={1}
      caption={<>Resultados en {FAMILY_LABEL[row.fold]} {row.test_year}, {FAMILY_POPULATION[row.fold]}.</>}
      note="Captura: porcentaje de los eventos registrados que cae en el porcentaje indicado de celdas, ordenadas de mayor a menor riesgo estimado."
    >
      <thead>
        <tr><th scope="col">Medida</th><th scope="col" className="num">Red</th><th scope="col" className="num">Promedio histórico</th><th scope="col" className="num">Azar</th></tr>
      </thead>
      <tbody>
        {line("Captura en el 10 % de celdas", pct(m.capture_top10, 0), pct(h.capture_top10, 0), "10 %", m.capture_top10 > h.capture_top10)}
        {line("Captura en el 20 % de celdas", pct(m.capture_top20, 0), pct(h.capture_top20, 0), "20 %", (m.capture_top20 ?? 0) > (h.capture_top20 ?? 0))}
        {line("Área bajo la curva ROC", dec(m.auc), dec(h.auc), "0,50", m.auc > h.auc)}
        {line("Precisión promedio", dec(m.average_precision), dec(h.average_precision), dec(r.average_precision), m.average_precision > h.average_precision)}
        {m05 != null && line("Mejora del error por distrito (M-05)", signed(m05), "referencia", "—", m05 > 0)}
      </tbody>
    </DocTable>
  );
}

function PrioritisationTable({ rows }: { rows: PrioritisationRow[] }) {
  const measures: [string, (s: RankingScores) => string][] = [
    ["Captura en el 5 %", (s) => pct(s.capture_top5, 0)],
    ["Captura en el 10 %", (s) => pct(s.capture_top10, 0)],
    ["Captura en el 20 %", (s) => pct(s.capture_top20, 0)],
    ["Área bajo la curva ROC", (s) => dec(s.auc)],
    ["Precisión promedio", (s) => dec(s.average_precision)],
  ];
  return (
    <DocTable
      n={3}
      caption="Priorización de celdas de 1 km en los años de prueba."
      note="Celda positiva: al menos un evento ubicado en el año. Azar: valor esperado de un orden aleatorio."
    >
      <thead>
        <tr><th scope="col">Medida</th>{rows.map((r) => <th key={r.fold} scope="col" className="num" colSpan={3}>{FAMILY_LABEL[r.fold]} {r.test_year}</th>)}</tr>
        <tr>
          <th scope="col" />
          {rows.map((r) => [
            <th key={`${r.fold}m`} scope="col" className="num">Red</th>,
            <th key={`${r.fold}h`} scope="col" className="num">Histórico</th>,
            <th key={`${r.fold}r`} scope="col" className="num">Azar</th>,
          ])}
        </tr>
      </thead>
      <tbody>
        {measures.map(([label, f], i) => (
          <tr key={label}>
            <th scope="row">{label}</th>
            {rows.map((r) => {
              const random = r.cell_year.random_expected;
              const rand = i < 3 ? ["5 %", "10 %", "20 %"][i] : i === 3 ? "0,50" : dec(random.average_precision);
              return [
                <td key={`${r.fold}m`} className="num">{f(r.cell_year.model)}</td>,
                <td key={`${r.fold}h`} className="num">{f(r.cell_year.historical_average)}</td>,
                <td key={`${r.fold}r`} className="num">{rand}</td>,
              ];
            })}
          </tr>
        ))}
        <tr className="group-start">
          <th scope="row">Celdas con evento</th>
          {rows.map((r) => <td key={r.fold} className="num" colSpan={3}>{int(r.positive_cells)} de {int(r.cells)}</td>)}
        </tr>
      </tbody>
    </DocTable>
  );
}

function CeilingTable({ rows }: { rows: NoiseCeilingRow[] }) {
  return (
    <DocTable
      n={4}
      caption="Error absoluto medio por distrito y franja."
      note="Mejora máxima: la que tendría una intensidad exacta, dada la variación aleatoria de conteos tan bajos; en CENACOM 2017 incluye conocer de antemano el aumento del registro de ese año. Validación: año usado para elegir el modelo."
    >
      <thead>
        <tr>
          <th scope="col">Serie y año</th>
          <th scope="col" className="num">Promedio histórico</th>
          <th scope="col" className="num">Red</th>
          <th scope="col" className="num">Mejora</th>
          <th scope="col" className="num">Mejora máxima</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={`${r.fold}${r.year}`} className={i > 0 && rows[i - 1].fold !== r.fold ? "group-start" : undefined}>
            <th scope="row">
              {FAMILY_LABEL[r.fold]} {r.year}
              <span className="sub">{isValidation(r) ? "validación" : "prueba"}</span>
            </th>
            <td className="num">{dec(r.baseline_mean, 3)}</td>
            <td className="num">{dec(r.model_mean, 3)}</td>
            <td className="num">{signed(r.achieved_improvement_pct)}</td>
            <td className="num">{signed(r.max_improvement_pct)}</td>
          </tr>
        ))}
      </tbody>
    </DocTable>
  );
}

const isValidation = (r: NoiseCeilingRow) => (r.fold === "onsv" ? r.year === 2023 : r.year === 2016);

function HighLevelTable({ card }: { card: Card }) {
  const rows = (card.high_level ?? []).filter((r) => r.partition !== "validation");
  return (
    <DocTable n={5} caption="Unidades celda × franja del año de prueba clasificadas en nivel alto.">
      <thead>
        <tr>
          <th scope="col">Prueba</th>
          <th scope="col">Método</th>
          <th scope="col" className="num">Altas observadas</th>
          <th scope="col" className="num">Detectadas</th>
          <th scope="col" className="num">Marcadas sin serlo</th>
          <th scope="col" className="num">Sensibilidad</th>
          <th scope="col" className="num">Precisión</th>
        </tr>
      </thead>
      <tbody>
        {rows.flatMap((r) =>
          [
            { who: "Red", c: r.model },
            ...(r.baseline ? [{ who: "Promedio histórico", c: r.baseline }] : []),
          ].map(({ who, c }, i) => (
            <tr key={`${r.family}${r.year}${who}`} className={i === 0 ? "group-start" : undefined}>
              <th scope="row">{i === 0 ? `${FAMILY_LABEL[r.family]} ${r.year}` : ""}</th>
              <td>{who}</td>
              <td className="num">{int(r.reference_high)}</td>
              <td className="num">{int(c.tp)}</td>
              <td className="num">{int(c.fp)}</td>
              <td className="num">{pct(c.recall)}</td>
              <td className="num">{pct(c.precision)}</td>
            </tr>
          )),
        )}
      </tbody>
    </DocTable>
  );
}

function SearchTable({ card }: { card: Card }) {
  const rows = [...(card.search ?? [])].sort((a, b) => a.validation_E - b.validation_E);
  return (
    <DocTable n={6} caption={<>Configuraciones evaluadas, ordenadas por error de validación. En negrita, la elegida.{card.search?.some((s) => s.variant === "convlstm") ? " La ConvLSTM no aplica dropout, por eso algunas filas repiten el mismo error." : ""}</>}>
      <thead>
        <tr>
          <th scope="col">Variante</th>
          <th scope="col" className="num">Canales</th>
          <th scope="col" className="num">Dropout</th>
          <th scope="col" className="num">Tasa</th>
          <th scope="col" className="num">Error de validación</th>
          <th scope="col" className="num">Época</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((s, i) => (
          <tr key={i}>
            <th scope="row" className={i === 0 ? "best" : undefined}>{VARIANT_LABEL[s.variant] ?? s.variant}</th>
            <td className="num">{s.hidden}</td>
            <td className="num">{String(s.dropout).replace(".", ",")}</td>
            <td className="num">{String(s.lr).replace(".", ",")}</td>
            <td className={i === 0 ? "num best" : "num"}>{dec(s.validation_E, 4)}</td>
            <td className="num">{s.best_epoch}</td>
          </tr>
        ))}
      </tbody>
    </DocTable>
  );
}

function ChannelsTable({ card }: { card: Card }) {
  const history = card.input_channels.filter((c) => c.includes("_prev_"));
  const context = card.input_channels.filter((c) => !c.includes("_prev_"));
  const label = (c: string) => VARIABLE_LABEL[c] ?? CHANNEL_LABEL[c] ?? c;
  return (
    <>
      <p>
        Las variables de contexto son fijas, salvo la población, que cambia cada año. Las de historial resumen los eventos
        del año anterior; el año estimado nunca entra en su propia entrada.
      </p>
      <DocTable n={7} caption={`Canales de entrada (${card.input_channels.length}).`}>
        <thead>
          <tr><th scope="col">Grupo</th><th scope="col">Variable</th></tr>
        </thead>
        <tbody>
          {context.map((c, i) => (
            <tr key={c} className={i === 0 ? "group-start" : undefined}>
              <th scope="row">{i === 0 ? "Contexto" : ""}</th>
              <td>{label(c)}</td>
            </tr>
          ))}
          {history.map((c, i) => (
            <tr key={c} className={i === 0 ? "group-start" : undefined}>
              <th scope="row">{i === 0 ? "Historial" : ""}</th>
              <td>{label(c)}</td>
            </tr>
          ))}
        </tbody>
      </DocTable>
    </>
  );
}

function TrainingCurves({ card }: { card: Card }) {
  const curves = Object.entries(card.training_curves).filter(([, c]) => c && c.length);
  if (!curves.length) return <p>Historial no registrado en esta corrida.</p>;
  const hist = curves[0][1]!;
  const best = hist.reduce((b, h) => (h[2] < b[2] ? h : b), hist[0]);
  return (
    <LineChart
      series={[
        { name: "Entrenamiento", color: "var(--chart-1)", points: hist.map((h) => [h[0], h[1]]) },
        { name: "Validación", color: "var(--chart-2)", points: hist.map((h) => [h[0], h[2]]) },
      ]}
      xLabel="época"
      xFormat={(v) => String(Math.round(v))}
      yFormat={(v) => v.toFixed(2).replace(".", ",")}
      marker={{ x: best[0], label: `época ${best[0]}` }}
      width={760}
      height={250}
    />
  );
}

function Partitions({ split }: { split: Record<string, Record<string, number[]>> }) {
  const years = Array.from({ length: 14 }, (_, i) => 2011 + i);
  const role = (fam: string, y: number) => {
    for (const part of ["train", "validation", "test"]) if (split[part]?.[fam]?.includes(y)) return part;
    return null;
  };
  const fill: Record<string, string> = { train: "var(--ink-2)", validation: "var(--chart-3)", test: "var(--chart-1)" };
  const label: Record<string, string> = { train: "Entrenamiento", validation: "Validación", test: "Prueba" };
  const w = 760, left = 84, cw = (w - left) / years.length;
  return (
    <svg viewBox={`0 0 ${w} 112`} className="chart" role="img" aria-label="Partición de años por fuente">
      {["cenacom", "onsv"].map((fam, r) => (
        <g key={fam}>
          <text x={0} y={22 + r * 30} style={{ font: "500 12px var(--font)", fill: "var(--ink)" }}>{FAMILY_LABEL[fam]}</text>
          {years.map((y, i) => {
            const k = role(fam, y);
            return (
              <rect key={y} x={left + i * cw + 1} y={8 + r * 30} width={cw - 2} height={20}
                fill={k ? fill[k] : "none"} stroke={k ? "none" : "var(--line)"} strokeDasharray={k ? undefined : "3 3"}>
                <title>{`${FAMILY_LABEL[fam]} ${y}: ${k ? label[k] : "sin registro"}`}</title>
              </rect>
            );
          })}
        </g>
      ))}
      {years.map((y, i) => (
        <text key={y} x={left + i * cw + cw / 2} y={82} textAnchor="middle" style={{ font: "11px var(--font)", fill: "var(--muted)" }}>{y}</text>
      ))}
      {Object.keys(label).map((k, i) => (
        <g key={k} transform={`translate(${left + i * 130} 98)`}>
          <rect width={10} height={10} y={-1} fill={fill[k]} />
          <text x={16} y={8} style={{ font: "11.5px var(--font)", fill: "var(--ink-2)" }}>{label[k]}</text>
        </g>
      ))}
    </svg>
  );
}

function Architecture({ card }: { card: Card }) {
  const X = card.tensor_shapes.X ?? [];
  const [, C, H, W] = X;
  const hidden = card.config.hidden;
  const conv = card.variant === "convlstm";
  const stages = [
    { title: "Entrada", lines: [`${C} variables por celda`, "contexto e historial"] },
    { title: conv ? "ConvLSTM" : "CNN + LSTM", lines: conv ? ["convolución 3 × 3", "memoria año a año"] : ["2 convoluciones 3 × 3", "LSTM por celda"] },
    { title: "Cabeza 1 × 1", lines: ["intensidad λ", "8 franjas por año"] },
    { title: "Observación", lines: ["registro y cobertura", "conteos por fuente"] },
  ];
  const shapes = [`T × ${C} × ${H} × ${W}`, `T × ${hidden} × ${H} × ${W}`, `T × 8 × ${H} × ${W}`];
  const w = 760, bw = 160, gap = (w - bw * stages.length) / (stages.length - 1);
  return (
    <svg viewBox={`0 0 ${w} 132`} className="chart" role="img" aria-label="Diagrama de la arquitectura de la red">
      <defs>
        <marker id="doc-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--ink-2)" />
        </marker>
      </defs>
      {stages.map((s, i) => {
        const x = i * (bw + gap);
        const core = i === 1;
        return (
          <g key={s.title}>
            <rect x={x + 0.5} y={10.5} width={bw - 1} height={78} fill={core ? "var(--accent-bg)" : "var(--bg)"} stroke={core ? "var(--accent)" : "var(--ink-2)"} />
            <text x={x + 12} y={34} style={{ font: "600 13px var(--font)", fill: "var(--ink)" }}>{s.title}</text>
            {s.lines.map((l, j) => (
              <text key={l} x={x + 12} y={56 + j * 17} style={{ font: "12px var(--font)", fill: "var(--ink-2)" }}>{l}</text>
            ))}
            {i < stages.length - 1 && (
              <>
                <line x1={x + bw + 3} y1={49} x2={x + bw + gap - 4} y2={49} stroke="var(--ink-2)" strokeWidth={1.2} markerEnd="url(#doc-arrow)" />
                <text x={x + bw + gap / 2} y={118} textAnchor="middle" style={{ font: "11px var(--mono)", fill: "var(--muted)" }}>{shapes[i]}</text>
                <line x1={x + bw + gap / 2} y1={56} x2={x + bw + gap / 2} y2={104} stroke="var(--line)" strokeDasharray="2 3" />
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}
