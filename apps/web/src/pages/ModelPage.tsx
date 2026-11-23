// Model view: how the CNN-RNN is built, trained, compared and reproduced
// (RM-01..RM-05, RNF-02). Every number comes from /model (published run).

import { api } from "../api/client";
import type { EvaluationRow, ModelCardDto } from "../api/types";
import { useApi } from "../api/useApi";
import { CompareBars, LineChart } from "../components/charts";
import { Notice } from "../components/Controls";
import { VARIABLE_LABEL } from "../components/ZonePanel";

const VARIANT_LABEL: Record<string, string> = {
  cnn_lstm: "CNN-RNN: CNN seguida de LSTM (referencia del plan)",
  convlstm: "CNN-RNN: ConvLSTM, LSTM con compuertas convolucionales (Shi et al., 2015)",
  cnn_only: "Solo CNN (ablación)",
  lstm_only: "Solo LSTM (ablación)",
  poisson_glm: "GLM de Poisson (clásico)",
};
const FAMILY_LABEL: Record<string, string> = { cenacom: "CENACOM", onsv: "ONSV" };
const num = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : v.toFixed(2).replace(".", ","));
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : `${(v * 100).toFixed(1).replace(".", ",")} %`);

export function ModelPage() {
  const model = useApi((s) => api.model(s), []);
  if (model.loading) return <div className="page"><div className="page-inner"><Notice>Cargando…</Notice></div></div>;
  if (model.error || !model.data) {
    return <div className="page"><div className="page-inner"><Notice tone="warn">La corrida publicada aún no tiene ficha del modelo ({model.error?.message}).</Notice></div></div>;
  }
  const { card, benchmark } = model.data;
  const testRow = card.high_level?.find((r) => r.partition !== "validation");
  const test = benchmark.test ?? [];
  const main = test[0];
  return (
    <div className="page">
      <div className="page-inner">
        <header className="page-header">
          <div>
            <p className="eyebrow">Modelo</p>
            <h1>Cómo funciona la red y qué tan bien estima</h1>
            <p>
              Corrida <code>{card.run_id}</code>: {VARIANT_LABEL[card.variant] ?? card.variant}
              {card.members > 1 && `, ensamble de ${card.members} semillas`}. Entrenada fuera de línea; la aplicación solo
              consulta sus resultados publicados.
            </p>
          </div>
        </header>

        <div className="grid cols-4">
          <Kpi label="Parámetros entrenables" value={card.parameters.toLocaleString("es-PE")} foot={`${card.members} modelo(s)`} />
          <Kpi label="Mejora frente al promedio histórico (M-05)" value={main?.relative_improvement_pct == null ? "n/a" : `${main.relative_improvement_pct > 0 ? "+" : ""}${main.relative_improvement_pct.toFixed(1)} %`} foot={main ? `prueba ${FAMILY_LABEL[main.family]} ${main.year}` : ""} />
          <Kpi
            label="Priorización de celdas, precisión promedio"
            value={num(testRow?.annual_cell?.model.average_precision)}
            foot={`histórico ${num(testRow?.annual_cell?.baseline?.average_precision)}; azar ${num(testRow?.annual_cell ? testRow.annual_cell.positives / testRow.annual_cell.cells : null)}`}
          />
          <Kpi label="Tiempo de entrenamiento" value={`${Math.round(card.elapsed_seconds / 60)} min`} foot={`CPU, ${card.config.threads} hilos, PyTorch ${card.torch}`} />
        </div>

        <section className="card">
          <header>
            <div>
              <h2>Arquitectura</h2>
              <p className="card-sub">Tensor de entrada [{card.tensor_shapes.X?.join(" × ")}] = años × variables × filas × columnas de la malla</p>
            </div>
          </header>
          <Architecture variant={card.variant} channels={card.input_channels.length} />
          <p className="card-note">
            La parte convolucional mira, en cada año, un vecindario de 5 × 5 km alrededor de cada celda; la parte recurrente
            recorre los años en orden y solo usa información anterior al año estimado. La salida es la intensidad esperada
            de atropellos por celda, año, tipo de día y franja; cada fuente se vincula a ella con su factor de registro
            (ONSV/CENACOM = {card.reporting_factor.onsv?.toFixed(3)}) y su cobertura.
          </p>
        </section>

        <div className="grid cols-2">
          <section className="card">
            <header><h2>Datos de entrenamiento, validación y prueba</h2></header>
            <Partitions split={card.split} />
            <p className="card-note">Partición cronológica: ningún dato del año de prueba se usa para entrenar, detener el entrenamiento ni elegir el modelo.</p>
          </section>
          <section className="card">
            <header><h2>Curvas de entrenamiento</h2><span className="card-sub">pérdida de Poisson por época</span></header>
            <TrainingCurves card={card} />
          </section>
        </div>

        <section className="card">
          <header>
            <div>
              <h2>Benchmark en la prueba independiente</h2>
              <p className="card-sub">Error E: error absoluto medio de atropellos por distrito y franja (menor es mejor). Línea discontinua: promedio histórico.</p>
            </div>
          </header>
          {test.map((row) => (
            <BenchmarkBlock key={`${row.family}-${row.year}`} row={row} model={model.data!} />
          ))}
          <p className="card-note">Selección: {benchmark.selection_rule}. La prueba se evalúa una sola vez para todas las alternativas.</p>
        </section>

        {card.high_level && (
          <section className="card">
            <header>
              <div>
                <h2>Errores del nivel alto</h2>
                <p className="card-sub">Unidades = celdas × franjas del año de prueba. Falso positivo: marcada alta sin serlo en lo observado; falso negativo: alta observada no marcada.</p>
              </div>
            </header>
            <table className="data-table">
              <thead>
                <tr><th scope="col">Prueba</th><th scope="col">Enfoque</th><th scope="col" className="num">Altas observadas</th><th scope="col" className="num">Detectadas</th><th scope="col" className="num">Falsos negativos</th><th scope="col" className="num">Falsos positivos</th><th scope="col" className="num">Recall</th><th scope="col" className="num">Precisión</th><th scope="col" className="num">F1</th></tr>
              </thead>
              <tbody>
                {card.high_level.filter((r) => r.partition !== "validation").flatMap((r) => [
                  { who: "Modelo", c: r.model, r },
                  ...(r.baseline ? [{ who: "Promedio histórico", c: r.baseline, r }] : []),
                ]).map(({ who, c, r }) => (
                  <tr key={`${r.family}${r.year}${who}`}>
                    <th scope="row">{FAMILY_LABEL[r.family]} {r.year}</th>
                    <td>{who}</td>
                    <td className="num">{r.reference_high.toLocaleString("es-PE")}</td>
                    <td className="num">{c.tp.toLocaleString("es-PE")}</td>
                    <td className="num">{c.fn.toLocaleString("es-PE")}</td>
                    <td className="num">{c.fp.toLocaleString("es-PE")}</td>
                    <td className="num">{pct(c.recall)}</td>
                    <td className="num">{pct(c.precision)}</td>
                    <td className="num">{num(c.f1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="card-note">
              El nivel alto es un percentil de una escala continua (índice 70 o más), así que marca muchas unidades; si la
              referencia es rara, como los atropellos fatales de ONSV, la precisión queda acotada por positivos sobre
              marcadas aunque el orden fuera perfecto. Por eso se reportan también medidas de priorización con el mismo
              presupuesto para la red y el promedio histórico.
            </p>
            <table className="data-table">
              <thead>
                <tr><th scope="col">Prueba</th><th scope="col">Medida</th><th scope="col" className="num">Modelo</th><th scope="col" className="num">Promedio histórico</th><th scope="col" className="num">Azar</th></tr>
              </thead>
              <tbody>
                {card.high_level.filter((r) => r.partition !== "validation" && r.model_ranking).flatMap((r) => {
                  const name = `${FAMILY_LABEL[r.family]} ${r.year}`;
                  const rows = [
                    { m: `Precisión con presupuesto igual a los positivos (${r.model_ranking!.k}), celda × franja`, a: pct(r.model_ranking!.precision_at_k), b: pct(r.baseline_ranking?.precision_at_k), c: pct(r.base_rate) },
                    { m: "Precisión promedio, celda × franja", a: num(r.model_ranking!.average_precision), b: num(r.baseline_ranking?.average_precision), c: num(r.base_rate) },
                  ];
                  const at = r.model_ranking!.at_validation_threshold;
                  if (at) rows.push({ m: `Umbral elegido en validación (índice ${r.validation_thresholds?.model}): precisión, recall, F1`, a: `${pct(at.precision)}, ${pct(at.recall)}, ${num(at.f1)}`, b: r.baseline_ranking?.at_validation_threshold ? `${pct(r.baseline_ranking.at_validation_threshold.precision)}, ${pct(r.baseline_ranking.at_validation_threshold.recall)}, ${num(r.baseline_ranking.at_validation_threshold.f1)}` : "n/a", c: "" });
                  const an = r.annual_cell;
                  if (an) {
                    rows.push({ m: `Celdas de 1 km en el año: precisión con presupuesto (${an.positives} celdas con atropello)`, a: pct(an.model.precision_at_k), b: pct(an.baseline?.precision_at_k), c: pct(an.positives / an.cells) });
                    rows.push({ m: "Celdas de 1 km en el año: precisión promedio", a: num(an.model.average_precision), b: num(an.baseline?.average_precision), c: num(an.positives / an.cells) });
                    rows.push({ m: "Celdas de 1 km en el año: celdas con atropello dentro del 10 % priorizado", a: pct(an.model.capture_top10), b: pct(an.baseline?.capture_top10), c: "10 %" });
                  }
                  return rows.map((x, i) => (
                    <tr key={`${name}${i}`}>
                      <th scope="row">{i === 0 ? name : ""}</th>
                      <td>{x.m}</td>
                      <td className="num">{x.a}</td>
                      <td className="num">{x.b}</td>
                      <td className="num">{x.c}</td>
                    </tr>
                  ));
                })}
              </tbody>
            </table>
          </section>
        )}

        {card.search && card.search.length > 0 && (
          <section className="card">
            <header><h2>Búsqueda de configuración (solo validación)</h2><span className="card-sub">{card.search.length} configuraciones</span></header>
            <div className="table-scroll" style={{ maxHeight: 320 }}>
              <table className="data-table">
                <thead><tr><th scope="col">Arquitectura</th><th scope="col" className="num">Ocultas</th><th scope="col" className="num">Dropout</th><th scope="col" className="num">Tasa de aprendizaje</th><th scope="col" className="num">E validación</th><th scope="col" className="num">Mejor época</th></tr></thead>
                <tbody>
                  {[...card.search].sort((a, b) => a.validation_E - b.validation_E).map((s, i) => (
                    <tr key={i} className={i === 0 ? "selected" : ""}>
                      <th scope="row">{VARIANT_LABEL[s.variant] ?? s.variant}</th>
                      <td className="num">{s.hidden}</td><td className="num">{s.dropout}</td><td className="num">{s.lr}</td>
                      <td className="num">{s.validation_E.toFixed(4)}</td><td className="num">{s.best_epoch}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        <div className="grid cols-2">
          <section className="card">
            <header><h2>Variables de entrada</h2><span className="card-sub">{card.input_channels.length} canales</span></header>
            <ul className="steps">
              {card.input_channels.map((c) => (
                <li key={c}>{VARIABLE_LABEL[c] ?? CHANNEL_LABEL[c] ?? c}</li>
              ))}
            </ul>
          </section>
          <section className="card">
            <header><h2>Ficha técnica y pesos</h2></header>
            <dl className="kv">
              <dt>Familia</dt><dd>{card.model_family}</dd>
              <dt>Configuración</dt><dd className="mono">{Object.entries(card.config).map(([k, v]) => `${k}=${v}`).join(", ")}</dd>
              <dt>SHA-256 de pesos</dt><dd className="mono" style={{ wordBreak: "break-all" }}>{card.weights_sha256}</dd>
              <dt>Commit</dt><dd className="mono">{card.code_commit_sha.slice(0, 12)}</dd>
            </dl>
            <details style={{ marginTop: 10 }}>
              <summary>Capas ({card.layers.length})</summary>
              <div className="mono-block">{card.layers.join("\n")}</div>
            </details>
          </section>
        </div>
      </div>
    </div>
  );
}

const CHANNEL_LABEL: Record<string, string> = {
  valid_cell: "Máscara de celda válida",
  cenacom_prev_cell_rate: "Atropellos CENACOM del año previo (celda)",
  cenacom_prev_district_density: "Atropellos CENACOM del año previo (distrito)",
  cenacom_prev_observed: "Año previo observado por CENACOM",
  onsv_prev_cell_rate: "Siniestros ONSV del año previo (celda)",
  onsv_prev_district_density: "Siniestros ONSV del año previo (distrito)",
  onsv_prev_observed: "Año previo observado por ONSV",
};

function Kpi({ label, value, foot }: { label: string; value: string; foot: string }) {
  return (
    <div className="card kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      <span className="kpi-foot">{foot}</span>
    </div>
  );
}

function BenchmarkBlock({ row, model }: { row: EvaluationRow; model: ModelCardDto }) {
  const candidates = model.benchmark.candidates ?? {};
  const bars = Object.entries(candidates)
    .map(([v, c]) => ({ v, e: c.test?.find((t) => t.family === row.family && t.year === row.year)?.model.district_mae }))
    .filter((b): b is { v: string; e: number } => b.e !== undefined)
    .map((b) => ({ label: VARIANT_LABEL[b.v] ?? b.v, value: b.e, color: b.v === model.benchmark.selected_variant ? "var(--chart-1)" : "#b9b6ae" }));
  if (!bars.length) bars.push({ label: "Modelo publicado", value: row.model.district_mae, color: "var(--chart-1)" });
  return (
    <div style={{ marginBottom: 14 }}>
      <p className="field-label">
        {FAMILY_LABEL[row.family]} {row.year}: {row.observed_events.toFixed(0)} eventos, M-05 ={" "}
        {row.relative_improvement_pct === null ? "no calculable" : `${row.relative_improvement_pct.toFixed(2)} %`}
      </p>
      <CompareBars bars={bars} reference={row.baseline?.district_mae} referenceLabel="Promedio histórico" format={(v) => v.toFixed(3)} />
    </div>
  );
}

function TrainingCurves({ card }: { card: ModelCardDto["card"] }) {
  const curves = Object.entries(card.training_curves).filter(([, c]) => c && c.length);
  if (!curves.length) return <p className="muted small">Historial no registrado en esta corrida (se registra desde la versión 2).</p>;
  const [name, hist] = curves[0];
  return (
    <>
      <LineChart
        series={[
          { name: "Entrenamiento", color: "var(--chart-1)", points: hist!.map((h) => [h[0], h[1]]) },
          { name: "Validación", color: "var(--chart-2)", points: hist!.map((h) => [h[0], h[2]]) },
        ]}
        xLabel="época"
        xFormat={(v) => String(Math.round(v))}
        yFormat={(v) => v.toFixed(2)}
      />
      <p className="card-note">{name.replace("ensemble_seed_", "Semilla ")}. Se conserva el modelo de la época con menor pérdida de validación (detención temprana).</p>
    </>
  );
}

function Partitions({ split }: { split: Record<string, Record<string, number[]>> }) {
  const years = Array.from({ length: 14 }, (_, i) => 2011 + i);
  const role = (fam: string, y: number) => {
    for (const part of ["train", "validation", "test"]) if (split[part]?.[fam]?.includes(y)) return part;
    return null;
  };
  const color: Record<string, string> = { train: "#b9b6ae", validation: "var(--chart-3)", test: "var(--chart-1)" };
  const label: Record<string, string> = { train: "Entrenamiento", validation: "Validación", test: "Prueba" };
  return (
    <div>
      {["cenacom", "onsv"].map((fam) => (
        <div key={fam} className="bar-row" style={{ gridTemplateColumns: "80px 1fr" }}>
          <span className="small">{FAMILY_LABEL[fam]}</span>
          <span style={{ display: "grid", gridTemplateColumns: `repeat(${years.length}, 1fr)`, gap: 2 }}>
            {years.map((y) => {
              const r = role(fam, y);
              return <span key={y} title={`${y}: ${r ? label[r] : "sin datos"}`} style={{ height: 16, borderRadius: 3, background: r ? color[r] : "var(--seg)" }} />;
            })}
          </span>
        </div>
      ))}
      <div className="bar-row" style={{ gridTemplateColumns: "80px 1fr" }}>
        <span />
        <span style={{ display: "grid", gridTemplateColumns: `repeat(${years.length}, 1fr)`, gap: 2 }}>
          {years.map((y) => <span key={y} className="small muted" style={{ textAlign: "center" }}>{String(y).slice(2)}</span>)}
        </span>
      </div>
      <div className="chart-legend">
        {Object.keys(label).map((k) => <span key={k}><i className="box" style={{ background: color[k] }} /> {label[k]}</span>)}
        <span><i className="box" style={{ background: "var(--seg)" }} /> Sin fuente</span>
      </div>
    </div>
  );
}

function Architecture({ variant, channels }: { variant: string; channels: number }) {
  const conv = variant === "convlstm" ? "Compuertas convolucionales 3×3 (ConvLSTM)" : "2 convoluciones 3×3 por año (CNN)";
  const rnn = variant === "convlstm" ? "Memoria LSTM por celda, año a año" : "LSTM por celda sobre los años";
  const boxes = [
    { t: "Entrada", s: `${channels} variables por celda y año` },
    { t: "Espacial", s: conv },
    { t: "Temporal", s: rnn },
    { t: "Salida λ", s: "8 franjas por celda y año" },
    { t: "Observación", s: "factor de registro y cobertura por fuente" },
  ];
  const w = 1000;
  const bw = 170;
  const gap = (w - bw * boxes.length) / (boxes.length - 1);
  return (
    <svg viewBox={`0 0 ${w} 130`} className="chart" role="img" aria-label="Diagrama de la arquitectura de la red">
      {boxes.map((b, i) => {
        const x = i * (bw + gap);
        return (
          <g key={b.t}>
            <rect x={x} y={14} width={bw} height={100} rx={10} fill={i === 1 || i === 2 ? "var(--accent-bg)" : "var(--bg-2)"} stroke="var(--line)" />
            <text x={x + 12} y={42} style={{ font: "600 13px var(--font)", fill: "var(--ink)" }}>{b.t}</text>
            <foreignObject x={x + 10} y={54} width={bw - 20} height={56}>
              <div style={{ font: "12px var(--font)", color: "var(--muted)", lineHeight: 1.3, overflowWrap: "anywhere" }}>{b.s}</div>
            </foreignObject>
            {i < boxes.length - 1 && <path d={`M${x + bw + 4} 64 L${x + bw + gap - 6} 64`} stroke="var(--ink-2)" strokeWidth={1.5} markerEnd="url(#arrow)" />}
          </g>
        );
      })}
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--ink-2)" />
        </marker>
      </defs>
    </svg>
  );
}
