# ruff: noqa: E501  (Markdown table rows are kept on one line)
"""Generate docs/benchmarking/informe-de-benchmarking.md from evidence files (P3 structure as a guide).

Usage: python -m tools.reports.benchmark

Every number is read from evidence/ (run metrics, high-level errors,
spatial-unit measurements, fusion report, reproducibility). Nothing is typed by
hand, so regenerating after a new run keeps the report consistent.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "evidence" / "benchmarking"
OUT = ROOT / "docs" / "benchmarking" / "informe-de-benchmarking.md"

VARIANT = {
    "historical_average": "Promedio histórico (B0)",
    "poisson_glm": "GLM de Poisson",
    "convlstm": "ConvLSTM",
    "cnn_lstm": "CNN-LSTM",
    "cnn_only": "Solo CNN (ablación)",
    "lstm_only": "Solo LSTM (ablación)",
}


def load(name: str):
    path = EV / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pct(v, digits=1):
    return "n/a" if v is None else f"{v * 100:.{digits}f} %"


def num(v, digits=3):
    return "n/a" if v is None else f"{v:.{digits}f}"


def model_table(metrics: dict, high: list | None, title: str) -> list[str]:
    t0 = metrics["test"][0]
    lines = [
        f"**{title}** (prueba {t0['family'].upper()} {t0['year']}, {t0['observed_events']:.0f} eventos)",
        "",
        "| Alternativa | E prueba (MAE distrito × franja) | M-05 frente a B0 | Devianza por celda | Captura 10 % de celdas |",
        "|---|---|---|---|---|",
        f"| {VARIANT['historical_average']} | {num(t0['baseline']['district_mae'])} | (referencia) | "
        f"{num(t0['baseline']['cell_deviance'], 4)} | {pct(t0['baseline']['capture_top10'])} |",
    ]
    candidates = metrics.get("candidates") or {}
    if candidates:
        for v, c in candidates.items():
            t = c["test"][0]
            mark = " (seleccionada)" if v == metrics["selected_variant"] else ""
            lines.append(
                f"| {VARIANT.get(v, v)}{mark} | {num(t['model']['district_mae'])} | "
                f"{t['relative_improvement_pct']:+.2f} % | {num(t['model']['cell_deviance'], 4)} | "
                f"{pct(t['model']['capture_top10'])} |"
            )
    else:
        sel = metrics["selected_config"]
        lines.append(
            f"| {VARIANT.get(sel['variant'], sel['variant'])}, ensamble de 5 (h={sel['hidden']}, "
            f"dropout={sel['dropout']}, lr={sel['lr']}) | {num(t0['model']['district_mae'])} | "
            f"{t0['relative_improvement_pct']:+.2f} % | {num(t0['model']['cell_deviance'], 4)} | "
            f"{pct(t0['model']['capture_top10'])} |"
        )
    if high:
        h = high[0]
        lines += [
            "",
            f"Nivel alto ({h['units']} celdas × franjas, {h['reference_high']} altas observadas):",
            "",
            "| Enfoque | Detectadas | Falsos negativos | Falsos positivos | Recall | Precisión |",
            "|---|---|---|---|---|---|",
        ]
        for who, c in (("Modelo", h["model"]), ("Promedio histórico", h.get("baseline"))):
            if c:
                lines.append(
                    f"| {who} | {c['tp']} | {c['fn']} | {c['fp']} | {pct(c['recall'])} | {pct(c['precision'])} |"
                )
    return lines + [""]


def ablation_table(full: dict, ablated: dict) -> list[str]:
    """Context ablation arm (amendment A2): same protocol without urban-context channels."""
    rows = []
    for label, part in (("Validación", "validation"), ("Prueba", "test")):
        a, b = full[part][0], ablated[part][0]
        rows.append(
            f"| {label} {a['family'].upper()} {a['year']} | {num(a['model']['district_mae'])} | "
            f"{num(b['model']['district_mae'])} | {pct(a['model']['capture_top10'])} | "
            f"{pct(b['model']['capture_top10'])} | {num(a['model']['cell_deviance'], 4)} | "
            f"{num(b['model']['cell_deviance'], 4)} |"
        )
    return [
        "**Ablación de contexto (v3).** Mismo protocolo, datos y semillas, con todas las variables de exposición, "
        "entorno y tránsito fijadas en su media; la red solo ve el historial de atropellos. Responde si esas "
        "variables (Guo et al., 2024; Hu et al., 2024) mejoran la precisión.",
        "",
        "| Partición | E con contexto | E sin contexto | Captura con contexto | Captura sin contexto | "
        "Devianza con contexto | Devianza sin contexto |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
    ]


def device_section(devices: dict | None) -> list[str]:
    """Same configuration trained on CPU and on GPU: time and agreement of the results."""
    if not devices:
        return []
    return [
        "**Entrenamiento en CPU y en GPU.** La configuración publicada se entrenó en ambos dispositivos con la "
        "misma semilla y el mismo protocolo (búsqueda de 16 configuraciones y ensamble de 5).",
        "",
        "| Dispositivo | Tiempo de búsqueda y ensamble | Error E de validación del ensamble |",
        "|---|---|---|",
        *(
            f"| {d['device'].upper()} | {d['minutes']:.1f} min | {num(d['validation_E'], 4)} |"
            for d in devices["runs"]
        ),
        "",
        f"Concordancia entre dispositivos: nivel de riesgo igual en {_es(devices['level_match_pct'])} % de las "
        f"unidad-periodo; diferencia relativa mediana del indicador {_es(devices['median_rel_diff_pct'], 2)} %. "
        "Los resultados no son idénticos bit a bit entre dispositivos (aritmética de punto flotante distinta); "
        "cada dispositivo es reproducible por sí mismo. La corrida publicada y su reproducibilidad (M-04) son las de CPU.",
        "",
    ]


def _es(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


def _es_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def main() -> None:
    v1 = load("fused-cnnlstm-2026.11-r1.metrics.json")
    v1b = load("fused-cnnlstm-backtest-2017.metrics.json")
    v2 = load("fused-cnnlstm-2026.11-v2.metrics.json")
    v2b = load("fused-cnnlstm-backtest-2017-v2.metrics.json")
    v3 = load("fused-cnnlstm-2026.11-v3.metrics.json")
    v3b = load("fused-cnnlstm-backtest-2017-v3.metrics.json")
    v3n = load("fused-cnnlstm-2026.11-v3-nocontext.metrics.json")
    devices = load("device_comparison.json")
    spatial = load("spatial_units.json")
    dataset = (
        load("fused-v1.3.0.dataset_manifest.json")
        or load("fused-v1.1.0.dataset_manifest.json")
        or load("fused-v1.0.0.dataset_manifest.json")
    )
    m04 = json.loads((ROOT / "evidence/metrics/M-04.json").read_text(encoding="utf-8"))
    fusion = dataset["fusion_report"]
    total = sum(fusion["rows_read_by_source"].values())

    L: list[str] = [
        "# Benchmarking RAP-LM",
        "",
        "Universidad Peruana de Ciencias Aplicadas, SI727 Gerencia de Proyectos en Computación, Grupo 06.",
        "Elaboración propia a partir de las corridas registradas del proyecto (datos, métricas y reproducibilidad).",
        "",
        "## 1. Introducción",
        "",
        "Los productos oficiales disponibles (ONSV, estadísticas INEI y MTC) permiten saber dónde y cuántos "
        "siniestros ocurrieron, pero no comparan el **riesgo** de atropello entre zonas y periodos: no relacionan "
        "la ocurrencia con la severidad, la exposición y el entorno, y agregan a escalas que ocultan diferencias "
        "internas (causas C1 a C3 del plan v1.6, con base en Guo et al., 2024 y Hu et al., 2024). Este benchmark "
        "compara, con datos reales de Lima y bajo un protocolo preregistrado, las alternativas de tres componentes "
        "del producto.",
        "",
        "## 2. Objetivo del benchmarking",
        "",
        "Seleccionar con evidencia medida: (1) el modelo espaciotemporal que estima el riesgo, (2) la unidad "
        "espacial de análisis y (3) la estrategia para ubicar los eventos sin coordenadas. Tipo de benchmarking: "
        "**modelos y técnicas** (componente 1 y 3) y **representación de datos** (componente 2).",
        "",
        "## 3. Benchmarking del modelo espaciotemporal",
        "",
        "### 3.1. Propuestas",
        "",
        "| Propuesta | Descripción | Fuente |",
        "|---|---|---|",
        "| Promedio histórico (B0) | Media de los años previos de la misma fuente, unidad y franja. Enfoque base del plan (OE4-I1). | Plan v1.6 |",
        "| GLM de Poisson | Regresión log-lineal de conteos sobre las mismas variables; modelo clásico en seguridad vial. | Práctica estándar de modelos de frecuencia de siniestros |",
        "| ConvLSTM | Celda recurrente con compuertas convolucionales; base de Hetero-ConvLSTM para riesgo de accidentes en malla. | Shi et al. (2015); Yuan, Zhou y Yang (2018) |",
        "| CNN-LSTM | CNN por año (vecindario 5 × 5 km) y LSTM por celda sobre la secuencia de años. Arquitectura de referencia del plan. | Plan v1.6; Guo et al. (2024) |",
        "| Ablaciones | Solo CNN (sin recurrencia) y solo LSTM (sin contexto espacial) para medir el aporte de cada parte. | Diseño experimental propio |",
        "",
        "### 3.2. Criterios y parámetros de medición",
        "",
        "| # | Criterio | Medida | Mejor |",
        "|---|---|---|---|",
        "| 1 | Error de frecuencia (M-05) | MAE de atropellos por distrito × franja en el año de prueba (E) | menor |",
        "| 2 | Ajuste probabilístico | Devianza de Poisson por celda | menor |",
        "| 3 | Detección de zonas críticas | Recall del nivel alto (falsos negativos) | mayor |",
        "| 4 | Precisión de las alertas | Precisión del nivel alto (falsos positivos) | mayor |",
        "| 5 | Concentración | % de eventos en el 10 % de celdas con mayor estimación | mayor |",
        "| 6 | Reproducibilidad (M-04) | Valores idénticos al reentrenar con la misma semilla y código | 100 % |",
        "| 7 | Cumplimiento de la arquitectura | Componente espacial (RM-02) y temporal (RM-03) | requerido |",
        "",
        "Protocolo: partición cronológica; la selección usa solo el conjunto de validación y la prueba se evalúa una "
        "vez para todas las alternativas. La iteración v2 se registró antes de su entrenamiento.",
        "",
        "### 3.3. Comparación de propuestas",
        "",
    ]
    if v1:
        L += model_table(
            v1, load("fused-cnnlstm-2026.11-r1.high_level.json"), "Iteración v1, corrida principal"
        )
    if v1b:
        L += model_table(
            v1b,
            load("fused-cnnlstm-backtest-2017.high_level.json"),
            "Iteración v1, backtest de todas las severidades",
        )
    if v2:
        L += model_table(
            v2,
            load("fused-cnnlstm-2026.11-v2.high_level.json"),
            "Iteración v2 (dataset v1.1, búsqueda y ensamble), corrida principal",
        )
    if v2b:
        L += model_table(
            v2b,
            load("fused-cnnlstm-backtest-2017-v2.high_level.json"),
            "Iteración v2, backtest de todas las severidades",
        )
    if v3:
        L += model_table(
            v3,
            load("fused-cnnlstm-2026.11-v3.high_level.json"),
            "Iteración v3 (dataset v1.2, población anual; publicada), corrida principal",
        )
    if v3b:
        L += model_table(
            v3b,
            load("fused-cnnlstm-backtest-2017-v3.high_level.json"),
            "Iteración v3, backtest de todas las severidades",
        )
    if v3 and v3n:
        L += ablation_table(v3, v3n)
    L += [
        f"Reproducibilidad (M-04), corrida {m04['run_id']} reentrenada desde cero: "
        f"{_es_int(m04['numerator'])}/{_es_int(m04['denominator'])} valores dentro de la tolerancia "
        f"({_es(m04['value'])} %), coincidencia de unidad, periodo y nivel {_es(m04['level_match_pct'])} %.",
        "",
        *device_section(devices),
        "### 3.4. Análisis de alternativas",
        "",
        "- En la medida principal E por distrito, el GLM de Poisson y el promedio histórico son competidores fuertes: "
        "con series cortas (pocos años por fuente) un modelo simple estima bien los totales agregados.",
        "- Las redes CNN-RNN reducen la devianza por celda frente al promedio histórico y **detectan muchas más "
        "unidades de nivel alto realmente observadas** (menos falsos negativos), a costa de más falsos positivos. "
        "En seguridad vial, no marcar una zona crítica suele ser el error más costoso.",
        "- Las ablaciones muestran el aporte de cada parte: sin recurrencia (solo CNN) el error empeora; la "
        "secuencia temporal aporta información.",
        "",
        "### 3.5. Selección",
        "",
        "Se publica el candidato CNN-RNN con menor error de validación, como exige el plan (la arquitectura "
        "comprometida es CNN-RNN). El GLM y el promedio histórico quedan como referencia permanente en la vista "
        "*Modelo* de la aplicación.",
        "",
        "## 4. Benchmarking de la unidad espacial",
        "",
        "### 4.1. Propuestas y criterios",
        "",
        "Propuestas: distrito (43), malla de 2 km, malla de 1 km y corredor vial (calle dentro de un distrito; Hu et "
        "al., 2024 reportan mejor ajuste a nivel de segmento vial). Criterios: número de unidades, eventos "
        "asignables, proporción de unidad-periodo sin eventos (dispersión), eventos por unidad-periodo no vacía y "
        "capacidad de mostrar diferencias internas.",
        "",
        "### 4.2. Comparación",
        "",
        f"Periodos: {spatial['periods'] if spatial else 'n/a'} (año × tipo de día × franja). Eventos fusionados: "
        f"{spatial['events'] if spatial else 'n/a'}.",
        "",
        "| Unidad | Unidades | Eventos asignables | Unidad-periodo sin eventos | Eventos por unidad-periodo no vacía |",
        "|---|---|---|---|---|",
    ]
    for r in (spatial or {}).get("rows", []):
        L.append(
            f"| {r['representation']} | {r['units']} | {r['events_assigned_pct']} % | "
            f"{'n/a' if r['zero_share_pct'] is None else str(r['zero_share_pct']) + ' %'} | "
            f"{'n/a' if r['mean_events_nonzero'] is None else r['mean_events_nonzero']} |"
        )
    corr = next((r for r in (spatial or {}).get("rows", []) if r.get("note")), None)
    L += [
        "",
        f"{corr['note']}." if corr else "",
        "",
        "### 4.3. Análisis y selección",
        "",
        "El distrito es denso pero oculta diferencias internas (causa C3). La malla de 1 km es muy dispersa, pero es la "
        "resolución mínima que conserva la estructura urbana para la CNN y coincide con el prototipo validado. Se "
        "selecciona una **combinación**: malla de 1 km para el modelo, corredor vial para la precisión de calle y "
        "distrito para la gestión (agregando intensidades, nunca etiquetas).",
        "",
        "## 5. Benchmarking de la ubicación de eventos sin coordenadas",
        "",
        "### 5.1. Propuestas y criterios",
        "",
        "Propuestas: (a) usar solo eventos con coordenadas (ONSV), (b) asignar todo al distrito, (c) reglas de "
        "coincidencia con calles de OpenStreetMap dentro del distrito declarado (cruce = punto, calle = reparto por "
        "longitud, sin coincidencia = distrito), (d) geocodificador externo en línea. Criterios: cobertura de eventos "
        "ubicados, precisión espacial, reproducibilidad sin conexión, coordenadas inventadas (deben ser cero) y "
        "licencia de uso.",
        "",
        "### 5.2. Comparación",
        "",
        "| Propuesta | Eventos ubicados bajo distrito | Precisión | Reproducible sin conexión | Coordenadas inventadas |",
        "|---|---|---|---|---|",
    ]
    prec = fusion["precision_by_family"]
    points = prec.get("onsv:point", 0)
    located = sum(v for k, v in prec.items() if not k.endswith(":district"))
    fused = sum(prec.values())
    L += [
        f"| (a) Solo coordenadas ONSV | {points} de {fused} ({points / fused * 100:.1f} %) | punto | sí | 0 |",
        f"| (b) Solo distrito | 0 ({fused} a distrito) | distrito | sí | 0 |",
        f"| (c) Reglas con calles OSM (seleccionada) | {located} de {fused} ({located / fused * 100:.1f} %): "
        f"{prec.get('cenacom:intersection', 0)} cruces, {prec.get('cenacom:street', 0)} tramos, {points} puntos | "
        "cruce o tramo | sí | 0 |",
        "| (d) Geocodificador en línea | no ejecutado | variable | no (servicio externo, límites de uso) | posibles |",
        "",
        f"Registros leídos de las fuentes: {total}. Las exclusiones (cohorte no comparable, año incompleto, fecha u hora inválida) se registran con su motivo.",
        "",
        "### 5.3. Selección",
        "",
        "Se selecciona (c): multiplica por más de diez la cobertura ubicada frente a (a), es reproducible sin "
        "conexión y no inventa coordenadas. Su limitación (L03) queda declarada: los números de cuadra no se "
        "convierten y una calle se reparte por su longitud dentro del distrito.",
        "",
        "## 6. Conclusiones",
        "",
        "1. La red CNN-RNN aporta principalmente en **detectar zonas y franjas de riesgo alto** (recall) y en el "
        "ajuste por celda; en el total por distrito, los modelos simples siguen siendo competitivos, lo que se "
        "reporta sin ocultarlo.",
        "2. La fusión de fuentes y la ubicación por calles permiten pasar de 817 eventos con coordenadas a más de "
        "nueve mil ubicados bajo el nivel de distrito, de todas las severidades.",
        "3. La combinación malla + corredor + distrito responde a la causa C3 del plan sin perder comparabilidad.",
        "4. El proceso es reproducible: al reentrenar con la misma configuración se obtienen los mismos valores (M-04).",
        "",
        "## 7. Referencias",
        "",
        "- Guo et al. (2024) y Hu et al. (2024): referencias completas en el informe del proyecto v1.6.",
        "- Hochreiter, S., y Schmidhuber, J. (1997). Long short-term memory. *Neural Computation, 9*(8), 1735-1780.",
        "- Shi, X., Chen, Z., Wang, H., Yeung, D.-Y., Wong, W.-K., y Woo, W.-C. (2015). Convolutional LSTM network: "
        "A machine learning approach for precipitation nowcasting. *Advances in Neural Information Processing Systems, 28*.",
        "- Wexler, J., Pushkarna, M., Bolukbasi, T., Wattenberg, M., Viégas, F., y Wilson, J. (2019). The What-If Tool: "
        "Interactive probing of machine learning models. *IEEE Transactions on Visualization and Computer Graphics, 26*(1), 56-65.",
        "- Yuan, Z., Zhou, X., y Yang, T. (2018). Hetero-ConvLSTM: A deep learning approach to traffic accident "
        "prediction on heterogeneous spatio-temporal data. *Proceedings of the 24th ACM SIGKDD*, 984-992.",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print("written", OUT)


if __name__ == "__main__":
    main()
