// Model view: technical documentation of the published CNN-RNN (RM-01..RM-05, RNF-02).
// Every number comes from /model (model card of the published run).

import { api } from "../api/client";
import type { EvalScores, EvaluationBlock, ModelCardDto } from "../api/types";
import { useApi } from "../api/useApi";
import { LineChart } from "../components/charts";
import { Notice } from "../components/Controls";
import { DocPage, DocTable, Figure, Source, type DocSection } from "../components/Doc";
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
const CHANNEL_LABEL: Record<string, string> = {
  valid_cell: "Celda dentro de los 43 distritos",
  cenacom_prev_cell_rate: "CENACOM del año anterior, por celda",
  cenacom_prev_district_density: "CENACOM del año anterior, densidad del distrito",
  cenacom_prev_observed: "Año anterior observado por CENACOM",
  onsv_prev_cell_rate: "ONSV del año anterior, por celda",
  onsv_prev_district_density: "ONSV del año anterior, densidad del distrito",
  onsv_prev_observed: "Año anterior observado por ONSV",
};

const REFERENCES = [
  { key: "lstm", text: "Hochreiter, S. y Schmidhuber, J. (1997). Long short-term memory. Neural Computation, 9(8), 1735–1780.", url: "https://doi.org/10.1162/neco.1997.9.8.1735" },
  { key: "convlstm", text: "Shi, X., Chen, Z., Wang, H., Yeung, D.-Y., Wong, W. y Woo, W. (2015). Convolutional LSTM network: a machine learning approach for precipitation nowcasting. NeurIPS 28.", url: "https://arxiv.org/abs/1506.04214" },
  { key: "adam", text: "Kingma, D. P. y Ba, J. (2015). Adam: a method for stochastic optimization. ICLR.", url: "https://arxiv.org/abs/1412.6980" },
  { key: "gradcam", text: "Selvaraju, R. R. et al. (2017). Grad-CAM: visual explanations from deep networks via gradient-based localization. ICCV, 618–626.", url: "https://doi.org/10.1109/ICCV.2017.74" },
  { key: "hirescam", text: "Draelos, R. L. y Carin, L. (2020). Use HiResCAM instead of Grad-CAM for faithful explanations of convolutional neural networks.", url: "https://arxiv.org/abs/2011.08891" },
  { key: "whatif", text: "Wexler, J. et al. (2019). The What-If Tool: interactive probing of machine learning models. IEEE TVCG, 26(1), 56–65.", url: "https://doi.org/10.1109/TVCG.2019.2934619" },
  { key: "pr", text: "Davis, J. y Goadrich, M. (2006). The relationship between precision-recall and ROC curves. ICML, 233–240.", url: "https://doi.org/10.1145/1143844.1143874" },
  { key: "d17", text: "RAP-LM (2026). Registro de decisiones D-17 (metodología de evaluación) y D-18 (modelo v5).", url: "https://github.com/David-std2/RAP-LM/blob/main/docs/architecture/registro-de-decisiones.md" },
];

const dec = (v: number | null | undefined, d = 2) => (v == null ? "n/a" : v.toFixed(d).replace(".", ","));
const pct = (v: number | null | undefined, d = 1) => (v == null ? "n/a" : `${(v * 100).toFixed(d).replace(".", ",")} %`);
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
  const { card } = data;
  const ev = card.evaluation ?? null;
  const all = ev?.tests.find((x) => x.family === "cenacom");
  const fatal = ev?.tests.find((x) => x.family === "onsv");
  const gpu = String(card.config.device ?? "cpu").startsWith("cuda");
  const trainYears = (fam: string) => card.split.train?.[fam] ?? [];
  const span = (ys: number[]) => (ys.length ? `${ys[0]}–${ys[ys.length - 1]}` : "—");
  const finalRefit = Object.keys(card.split.test ?? {}).length === 0;
  const epochs = Object.values(card.training_curves).find((c) => c && c.length)?.length ?? 0;

  const sections: DocSection[] = [
    {
      id: "resumen",
      title: "Resumen",
      body: (
        <>
          <p>
            El modelo estima la intensidad esperada de atropellos de peatones de todas las severidades en cada celda de 1 km
            de los 43 distritos de Lima Metropolitana, por año, tipo de día y franja de seis horas. Es un ensamble de{" "}
            {card.members} redes {VARIANT_LABEL[card.variant] ?? card.variant}: una parte convolucional lee el entorno de cada
            celda y una parte recurrente recorre los años en orden, usando solo información anterior al año que estima.
          </p>
          {all && all.model.all_located && all.historical.all_located && (
            <p>
              Entrenado sin conocer {all.year}, el modelo ordenó las celdas por riesgo con una precisión promedio de{" "}
              <strong>{dec(all.model.all_located.average_precision)}</strong> frente a{" "}
              {dec(all.historical.all_located.average_precision)} del promedio histórico, en atropellos de todas las
              severidades. En los siniestros fatales de {fatal?.year}, el 20 % de celdas con mayor riesgo concentró el{" "}
              {pct(fatal?.model.all_located?.capture_top20, 0)} de los registrados, frente al{" "}
              {pct(fatal?.historical.all_located?.capture_top20, 0)} del histórico.
            </p>
          )}
          {ev && <SummaryTable ev={ev} />}
        </>
      ),
    },
    {
      id: "datos",
      title: "Datos y entrenamiento",
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
            {finalRefit
              ? "La versión publicada entrena con todos los años observados, para que el pronóstico parta de los datos más recientes. Por eso sus valores de 2011 a 2024 son reconstrucciones, no predicciones: la evaluación de la sección 5 proviene de modelos entrenados igual, pero sin el año evaluado."
              : "La partición es cronológica. Los años de prueba no se usan para entrenar, detener el entrenamiento ni elegir la configuración."}
          </p>
          <Figure n={1} source={<Source files={["ml/configs/v5-final.json"]} />} caption="Años con que entrena la versión publicada, por fuente. Entre 2018 y 2020 no hay registro disponible.">
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
            La salida λ es la intensidad latente en las 8 combinaciones de tipo de día y franja. El operador de observación
            convierte λ en los conteos esperados de cada fuente, a nivel de celda para los eventos ubicados y de distrito
            para los que solo tienen distrito.
          </p>
          <Figure n={2} source={<Source files={["ml/fused/model.py"]}>Shi et al. (2015) para la ConvLSTM</Source>} caption={<>Flujo de los datos por la red. Las dimensiones se leen años × canales × filas × columnas.</>}>
            <Architecture card={card} />
          </Figure>
          <DocTable n={2} source={<Source files={["ml/configs/v5-final.json", "docs/architecture/registro-de-decisiones.md"]}>decisión D-18</Source>} caption="Configuración del modelo publicado.">
            <tbody>
              <tr><th scope="row">Variante</th><td>{VARIANT_LABEL[card.variant] ?? card.variant}, {card.config.hidden} canales ocultos</td></tr>
              <tr><th scope="row">Parámetros entrenables</th><td>{int(card.parameters)} por red, ensamble de {card.members}</td></tr>
              <tr><th scope="row">Optimización</th><td>Adam, tasa {String(card.config.lr).replace(".", ",")}, decaimiento de pesos {String(card.config.weight_decay).replace(".", ",")}{card.variant === "convlstm" ? "" : `, dropout ${String(card.config.dropout).replace(".", ",")}`}</td></tr>
              <tr><th scope="row">Pérdida</th><td>Verosimilitud de Poisson de los conteos observados, por evento</td></tr>
              <tr><th scope="row">Duración</th><td>{finalRefit ? `${epochs} épocas fijas, definidas en los pliegues de desarrollo` : `Hasta ${card.config.max_epochs} épocas; se conserva la de menor pérdida de validación (paciencia ${card.config.patience})`}</td></tr>
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
            Cada red del ensamble parte de una semilla distinta. El entrenamiento tomó {Math.max(1, Math.round(card.elapsed_seconds / 60))}{" "}
            minutos en {gpu ? "GPU" : `CPU (${card.config.threads} hilos)`} con PyTorch {card.torch}. Repetirlo en el mismo
            equipo produce pesos idénticos.
          </p>
          <Figure n={3} source={<Source files={["ml/fused/train.py"]}>historial registrado en la ficha de la corrida</Source>} caption="Pérdida de Poisson por época de la primera red del ensamble.">
            <TrainingCurves card={card} />
          </Figure>
        </>
      ),
    },
    ...(ev
      ? [
          {
            id: "evaluacion",
            title: "Evaluación fuera de muestra",
            body: (
              <>
                <p>
                  Cada año se evalúa con una red entrenada de la misma forma pero sin ese año, y se compara con el promedio
                  histórico de la misma fuente. La evaluación principal es la de todas las severidades. Se muestran todas las
                  medidas, también las desfavorables.
                </p>
                <EvaluationTable ev={ev} />
                <p>
                  La red ordena mejor las celdas en ambos años, también en el estrato de ubicación precisa. En CENACOM 2017
                  pierde en error por distrito: el censo de ese año registra muchos más eventos por mes que los anteriores,
                  junto con un cambio en su factor de expansión muestral, y ese cambio de nivel no se puede anticipar con los
                  años previos. Los años 2017 y 2024 se consultaron en iteraciones anteriores del desarrollo, por lo que no
                  constituyen una validación independiente.
                </p>
              </>
            ),
          },
          {
            id: "horizontes",
            title: "Pronóstico a varios años",
            body: (
              <>
                <p>
                  Para estimar 2026 y 2027 el modelo usa su propia estimación del año previo como entrada. Este ensayo repite
                  ese encadenamiento con años conocidos: la red se entrena hasta un año y pronostica uno, dos y tres años
                  después sin ver los años intermedios.
                </p>
                <HorizonsTable ev={ev} />
              </>
            ),
          },
          {
            id: "ablacion",
            title: "Aporte de cada componente",
            body: (
              <>
                <p>
                  Se entrena la misma red quitando un componente a la vez. Las tres partes aportan; el contexto urbano es la
                  que más influye en la priorización.
                </p>
                <AblationTable ev={ev} />
              </>
            ),
          },
        ]
      : []),
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
          <Source files={["evidence/metrics/M-04.json", "evidence/benchmarking/gpu_determinism.json"]}>reentrenamiento independiente con resultados idénticos (M-04)</Source>
          <details className="doc-details">
            <summary>Capas de la red ({card.layers.length})</summary>
            <div className="doc-mono">{card.layers.join("\n")}</div>
          </details>
        </>
      ),
    },
  ];

  sections.push({
    id: "referencias",
    title: "Referencias",
    body: (
      <ul className="doc-refs">
        {REFERENCES.map((r) => (
          <li key={r.key}>
            {r.text} <a href={r.url} target="_blank" rel="noreferrer">{r.url.replace("https://", "")}</a>
          </li>
        ))}
      </ul>
    ),
  });

  return (
    <DocPage
      title="Modelo de riesgo"
      lead="Cómo se construye, entrena y evalúa la red que estima el riesgo de atropello peatonal en Lima Metropolitana."
      meta={<>Corrida publicada <code>{card.run_id}</code></>}
      sections={sections}
    />
  );
}

function SummaryTable({ ev }: { ev: EvaluationBlock }) {
  const tests = [...ev.tests].sort((a) => (a.family === "cenacom" ? -1 : 1));
  const rows: [string, (s: EvalScores) => number | undefined, (v: number | undefined) => string, boolean][] = [
    ["Precisión promedio", (s) => s.all_located?.average_precision, (v) => dec(v), true],
    ["Área bajo la curva ROC", (s) => s.all_located?.auc, (v) => dec(v), true],
    ["Captura en el 20 % de celdas", (s) => s.all_located?.capture_top20, (v) => pct(v, 0), true],
  ];
  return (
    <DocTable n={1} source={<Source files={["evidence/benchmarking/performance-v10/evaluation-T1f-T2f.json", "docs/ml/performance-v10.md"]} />} caption="Priorización de celdas en años no usados para entrenar." note="Captura: parte de los eventos registrados que cae en el 20 % de celdas con mayor riesgo estimado. Azar: 0,50 de AUC y 20 % de captura.">
      <thead>
        <tr>
          <th scope="col">Medida</th>
          {tests.map((x) => <th key={x.family} scope="col" className="num" colSpan={2}>{x.population.split(" ")[0]} {x.year}<span className="sub">{x.population}</span></th>)}
        </tr>
        <tr><th scope="col" />{tests.map((x) => [<th key={`${x.family}m`} scope="col" className="num">Red</th>, <th key={`${x.family}h`} scope="col" className="num">Histórico</th>])}</tr>
      </thead>
      <tbody>
        {rows.map(([label, get, fmt, higher]) => (
          <tr key={label}>
            <th scope="row">{label}</th>
            {tests.map((x) => {
              const m = get(x.model), h = get(x.historical);
              const best = m != null && h != null && (higher ? m > h : m < h);
              return [<td key={`${x.family}m`} className={best ? "num best" : "num"}>{fmt(m)}</td>, <td key={`${x.family}h`} className="num">{fmt(h)}</td>];
            })}
          </tr>
        ))}
      </tbody>
    </DocTable>
  );
}

function EvaluationTable({ ev }: { ev: EvaluationBlock }) {
  const tests = [...ev.tests].sort((a) => (a.family === "cenacom" ? -1 : 1));
  const rows: [string, (s: EvalScores) => number | undefined, (v: number | undefined) => string, boolean][] = [
    ["Precisión promedio, masa ubicada", (s) => s.all_located?.average_precision, (v) => dec(v), true],
    ["AUC, masa ubicada", (s) => s.all_located?.auc, (v) => dec(v), true],
    ["Captura en 10 % de celdas", (s) => s.all_located?.capture_top10, (v) => pct(v, 1), true],
    ["Captura en 20 % de celdas", (s) => s.all_located?.capture_top20, (v) => pct(v, 1), true],
    ["Precisión promedio, ubicación precisa", (s) => s.precise?.average_precision, (v) => dec(v), true],
    ["Captura en 10 %, ubicación precisa", (s) => s.precise?.capture_top10, (v) => pct(v, 1), true],
    ["Error absoluto medio, distrito y franja", (s) => s.district.mae, (v) => dec(v, 3), false],
    ["Correlación de rangos entre distritos", (s) => s.district.spearman, (v) => dec(v, 3), true],
    ["Captura en 20 % de distritos", (s) => s.district.capture_top20, (v) => pct(v, 1), true],
  ];
  return (
    <DocTable n={3} source={<Source files={["evidence/benchmarking/performance-v10/evaluation-T1f-T2f.json", "docs/ml/performance-v10.md", "ml/experiments/v10.py"]} />} caption="Evaluación completa por año. En negrita, el mejor valor de cada par." note="Masa ubicada: eventos asignados a la malla por cruce, calle o coordenada. Ubicación precisa: solo cruces (CENACOM) o coordenadas (ONSV).">
      <thead>
        <tr><th scope="col">Medida</th>{tests.map((x) => <th key={x.family} scope="col" className="num" colSpan={2}>{x.family === "cenacom" ? "CENACOM" : "ONSV"} {x.year}</th>)}</tr>
        <tr><th scope="col" />{tests.map((x) => [<th key={`${x.family}m`} scope="col" className="num">Red</th>, <th key={`${x.family}h`} scope="col" className="num">Histórico</th>])}</tr>
      </thead>
      <tbody>
        {rows.map(([label, get, fmt, higher]) => (
          <tr key={label}>
            <th scope="row">{label}</th>
            {tests.map((x) => {
              const m = get(x.model), h = get(x.historical);
              const mBest = m != null && h != null && (higher ? m > h : m < h);
              const hBest = m != null && h != null && (higher ? h > m : h < m);
              return [<td key={`${x.family}m`} className={mBest ? "num best" : "num"}>{fmt(m)}</td>, <td key={`${x.family}h`} className={hBest ? "num best" : "num"}>{fmt(h)}</td>];
            })}
          </tr>
        ))}
      </tbody>
    </DocTable>
  );
}

function HorizonsTable({ ev }: { ev: EvaluationBlock }) {
  const rows = [...ev.horizons].sort((a, b) => (a.family === b.family ? a.last_observed - b.last_observed || a.horizon - b.horizon : a.family === "cenacom" ? -1 : 1));
  return (
    <DocTable n={4} wide source={<Source files={["evidence/benchmarking/performance-v14/horizons.json", "evidence/benchmarking/performance-v14/README.md"]} />} caption="Pronóstico encadenado: red frente al promedio histórico de los años hasta el último con datos. Error: absoluto medio por distrito y franja." note="Desde 2014 el histórico no tiene años con eventos ubicados en la malla, por lo que su orden de celdas equivale al azar (AUC 0,50).">
      <thead>
        <tr>
          <th scope="col">Fuente</th>
          <th scope="col" className="num">Último año con datos</th>
          <th scope="col" className="num">Año estimado</th>
          <th scope="col" className="num">Años</th>
          <th scope="col" className="num">AUC red</th>
          <th scope="col" className="num">AUC hist.</th>
          <th scope="col" className="num">Error red</th>
          <th scope="col" className="num">Error hist.</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((h, i) => (
          <tr key={`${h.family}${h.last_observed}${h.target}`} className={i > 0 && rows[i - 1].family !== h.family ? "group-start" : undefined}>
            <th scope="row">{h.family === "cenacom" ? "CENACOM" : "ONSV"}</th>
            <td className="num">{h.last_observed}</td>
            <td className="num">{h.target}</td>
            <td className="num">{h.horizon}</td>
            <td className={(h.model.all_located?.auc ?? 0) > (h.historical.all_located?.auc ?? 0) ? "num best" : "num"}>{dec(h.model.all_located?.auc, 3)}</td>
            <td className="num">{dec(h.historical.all_located?.auc, 3)}</td>
            <td className={h.model.district.mae < h.historical.district.mae ? "num best" : "num"}>{dec(h.model.district.mae, 3)}</td>
            <td className={h.historical.district.mae < h.model.district.mae ? "num best" : "num"}>{dec(h.historical.district.mae, 3)}</td>
          </tr>
        ))}
      </tbody>
    </DocTable>
  );
}

function AblationTable({ ev }: { ev: EvaluationBlock }) {
  return (
    <DocTable n={5} source={<Source files={["evidence/benchmarking/performance-v10/evaluation-D2b-D3b.json", "evidence/benchmarking/performance-v10/README.md"]} />} caption="Ablación: misma red sin un componente. Desarrollo con CENACOM 2016 y ONSV 2023." note="Error: absoluto medio por distrito y franja (menor es mejor).">
      <thead>
        <tr>
          <th scope="col">Variante</th>
          <th scope="col" className="num">Precisión promedio 2016</th>
          <th scope="col" className="num">Error 2016</th>
          <th scope="col" className="num">Precisión promedio 2023</th>
          <th scope="col" className="num">Error 2023</th>
        </tr>
      </thead>
      <tbody>
        {ev.ablation.map((a) => (
          <tr key={a.arm} className={a.arm === "C0" ? "group-start" : undefined}>
            <th scope="row" className={a.arm === "C0" ? "best" : undefined}>{a.label}</th>
            <td className="num">{dec(a.cenacom_2016.average_precision, 3)}</td>
            <td className="num">{dec(a.cenacom_2016.mae, 3)}</td>
            <td className="num">{dec(a.onsv_2023.average_precision, 3)}</td>
            <td className="num">{dec(a.onsv_2023.mae, 3)}</td>
          </tr>
        ))}
      </tbody>
    </DocTable>
  );
}

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
      <DocTable n={7} source={<Source files={["pipelines/fusion/context.py", "docs/data/feature-target-contract.md"]} />} caption={`Canales de entrada (${card.input_channels.length}).`}>
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
  const hasVal = hist.some((h) => h[2] !== null && h[2] !== undefined);
  const best = hasVal ? hist.reduce((b, h) => (h[2] < b[2] ? h : b), hist[0]) : hist[hist.length - 1];
  return (
    <LineChart
      series={[
        { name: "Entrenamiento", color: "var(--chart-1)", points: hist.map((h) => [h[0], h[1]]) },
        ...(hasVal ? [{ name: "Validación", color: "var(--chart-2)", points: hist.map((h): [number, number] => [h[0], h[2]]) }] : []),
      ]}
      xLabel="época"
      xFormat={(v) => String(Math.round(v))}
      yFormat={(v) => fmtNumber(v, 2)}
      marker={{ x: best[0], label: hasVal ? `época ${best[0]}` : "última época" }}
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
