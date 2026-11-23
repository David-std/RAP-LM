# ruff: noqa: E501  (Markdown table rows are kept on one line)
"""Generate docs/pruebas/informe-de-pruebas.md from test and metric evidence.

Usage: python -m tools.reports.test_report

Inputs (produced by the test commands in README.md):
- evidence/tests/pytest.xml   (pytest --junitxml)
- evidence/tests/vitest.xml   (vitest --reporter=junit)
- evidence/e2e/results.json   (Playwright JSON reporter)
- evidence/metrics/M-*.json   (tools.metrics.measure)
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "evidence"
OUT = ROOT / "docs" / "pruebas" / "informe-de-pruebas.md"

TARGETS = {
    "M-01": ("Correspondencia espacial", ">= 95 %"),
    "M-02": ("Completitud del contexto de cada resultado", ">= 95 %"),
    "M-03": ("Trazabilidad de fuente y versión", ">= 95 %"),
    "M-04": (
        "Reproducibilidad del pipeline",
        ">= 95 % dentro de tolerancia; 100 % unidad, periodo y nivel",
    ),
    "M-05": ("Mejora relativa frente al promedio histórico", "> 0 %"),
    "M-07": ("Escenarios críticos de extremo a extremo", "100 % y cero bloqueantes"),
    "M-08": ("Exactitud de consultas, filtros y comparaciones", ">= 95 % global, 100 % críticos"),
    "M-09": ("Tiempo de respuesta p95 de la API", "<= 2 s"),
}


def junit(path: Path) -> tuple[int, int, int] | None:
    if not path.exists():
        return None
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    tests = sum(int(s.get("tests", 0)) for s in suites)
    failures = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    return tests, failures, skipped


def e2e() -> tuple[int, int, list[str]] | None:
    path = EV / "e2e" / "results.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    titles, passed, total = [], 0, 0

    def walk(suite):
        nonlocal passed, total
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                total += 1
                ok = all(r.get("status") == "passed" for r in test.get("results", []))
                passed += ok
                titles.append(("Aprobado" if ok else "Fallido") + ": " + spec["title"])
        for child in suite.get("suites", []):
            walk(child)

    for s in data.get("suites", []):
        walk(s)
    return passed, total, titles


def metric(mid: str) -> dict | None:
    path = EV / "metrics" / f"{mid}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def fmt_metric(mid: str, m: dict) -> str:
    if mid == "M-05":
        rows = m.get("evaluations", [])
        return "; ".join(
            f"{r['run'].replace('fused-cnnlstm-', '')}: {r['improvement_pct']:+.2f} %"
            for r in rows
            if r.get("improvement_pct") is not None
        )
    if mid == "M-09":
        return f"p95 {m['value']:.2f} s ({m['requests']} peticiones, {m['errors']} errores)"
    if m.get("numerator") is not None:
        return f"{m['numerator']:,}/{m['denominator']:,} = {m['value']} %".replace(",", ".")
    return str(m.get("value"))


def main() -> None:
    py = junit(EV / "tests" / "pytest.xml")
    vt = junit(EV / "tests" / "vitest.xml")
    pw = e2e()
    run_id = next((m["run_id"] for mid in TARGETS if (m := metric(mid))), "n/a")
    L = [
        "# Informe de pruebas",
        "",
        f"Resultados de la verificación del MVP sobre la corrida publicada `{run_id}`, según el "
        "[plan de pruebas](plan-de-pruebas.md). Las métricas se miden contra la aplicación desplegada con Docker "
        "Compose (API, base de datos y web).",
        "",
        "## 1. Pruebas automatizadas",
        "",
        "| Conjunto | Alcance | Casos | Fallidos |",
        "|---|---|---|---|",
    ]
    if py:
        L.append(
            f"| pytest | Pipeline, modelo (forma, causalidad, campo receptivo), contrato de la API contra PostGIS, roles de base de datos | {py[0]} | {py[1]} |"
        )
    if vt:
        L.append(f"| Vitest | Leyenda, colores por umbral, cliente de API | {vt[0]} | {vt[1]} |")
    if pw:
        L.append(
            f"| Playwright | Recorridos críticos sobre la aplicación desplegada | {pw[1]} | {pw[1] - pw[0]} |"
        )
    L += ["", "## 2. Escenarios críticos de extremo a extremo (M-07)", ""]
    if pw:
        L += [f"- {t}" for t in pw[2]]
    L += [
        "",
        "## 3. Métricas de calidad del producto",
        "",
        "| Métrica | Descripción | Resultado | Meta |",
        "|---|---|---|---|",
    ]
    for mid, (desc, target) in TARGETS.items():
        if mid == "M-07" and pw:
            L.append(f"| M-07 | {desc} | {pw[0]}/{pw[1]} escenarios aprobados | {target} |")
            continue
        m = metric(mid)
        if m:
            L.append(f"| {mid} | {desc} | {fmt_metric(mid, m)} | {target} |")
    L += [
        "",
        "M-06 (requisitos funcionales aceptados) se determina en la revisión de sprint con el plan de pruebas por "
        "requisito. M-10 a M-12 se miden en las sesiones con especialistas (paquete 4.5) con los instrumentos de "
        "`docs/validacion/`. M-13 a M-15 corresponden a la gestión del proyecto.",
        "",
        "## 4. Defectos",
        "",
        "Los defectos encontrados por las pruebas y su corrección se registran en el "
        "[registro de incidencias](../registro-de-incidencias.md).",
        "",
    ]
    OUT.write_text("\n".join(L), encoding="utf-8")
    print("written", OUT)


if __name__ == "__main__":
    main()
