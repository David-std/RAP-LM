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
    "M-01": ("Correspondencia espacial (eventos ONSV con coordenadas verificables)", ">= 95 %"),
    "M-02": (
        "Completitud del contexto de cada resultado publicado (campos obligatorios)",
        ">= 95 %",
    ),
    "M-03": (
        "Trazabilidad de fuente y versión (muestra de 200 resultados, semilla fija)",
        ">= 95 %",
    ),
    "M-04": (
        "Reproducibilidad del pipeline",
        ">= 95 % dentro de tolerancia; 100 % unidad, periodo y nivel",
    ),
    "M-05": ("Mejora relativa frente al promedio histórico", "> 0 %"),
    "M-07": ("Escenarios críticos de extremo a extremo", "100 % y cero bloqueantes"),
    "M-08": ("Exactitud de consultas, filtros y comparaciones", ">= 95 % global, 100 % críticos"),
    "M-09": ("Tiempo de respuesta p95 de la API (secuencial y 10 clientes simultáneos)", "<= 2,5 s (D-15; plan: 2 s)"),
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
    raw = path.read_text(encoding="utf-8")
    # Versioned evidence keeps repository-relative paths only (no local user folders).
    for prefix in (str(ROOT).replace("\\", "/") + "/", json.dumps(str(ROOT) + "\\")[1:-1]):
        raw = raw.replace(prefix, "")
    path.write_text(raw, encoding="utf-8")
    data = json.loads(raw)
    titles, passed, total = [], 0, 0

    def walk(suite):
        nonlocal passed, total
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                total += 1
                ok = all(r.get("status") == "passed" for r in test.get("results", []))
                passed += ok
                titles.append((spec["title"].split(" ")[0], "Aprobado" if ok else "Fallido"))
        for child in suite.get("suites", []):
            walk(child)

    for s in data.get("suites", []):
        walk(s)
    return passed, total, titles


def es(x: float, digits: int = 1) -> str:
    """Spanish decimal comma."""
    return f"{x:.{digits}f}".replace(".", ",")


def plan_journeys() -> dict[str, str]:
    """E2E id -> description and requirements, from the test plan table."""
    plan = ROOT / "docs" / "pruebas" / "plan-de-pruebas.md"
    rows = {}
    for line in plan.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == 3 and cells[0].startswith("E2E-"):
            rows[cells[0]] = f"{cells[1]} ({cells[2]})"
    return rows


def metric(mid: str) -> dict | None:
    path = EV / "metrics" / f"{mid}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def fmt_metric(mid: str, m: dict) -> str:
    if mid == "M-05":
        return _m05(m)
    if mid == "M-09":
        return _m09(m)
    if m.get("numerator") is not None:
        n, d = (f"{v:,}".replace(",", ".") for v in (m["numerator"], m["denominator"]))
        return f"{n}/{d} = {es(m['value'])} %"
    return str(m.get("value"))


def _m05(m: dict) -> str:
    """Fatal-only test of the run plus, when present, the all-severity backtest of the iteration."""
    text = "; ".join(
        f"prueba {r['family'].upper()} {r['year']} (fatales): {'+' if r['improvement_pct'] > 0 else ''}"
        f"{es(r['improvement_pct'], 2)} %"
        for r in m.get("evaluations", [])
        if r.get("improvement_pct") is not None
    )
    version = m.get("run_id", "").rsplit("-", 1)[-1]
    backtest = EV / "benchmarking" / f"fused-cnnlstm-backtest-2017-{version}.metrics.json"
    if backtest.exists():
        t = json.loads(backtest.read_text(encoding="utf-8"))["test"][0]
        sign = "+" if t["relative_improvement_pct"] > 0 else ""
        text += (
            f"; backtest {t['family'].upper()} {t['year']} (todas las severidades): "
            f"{sign}{es(t['relative_improvement_pct'], 2)} %"
        )
    return text


def _m09(m: dict) -> str:
    if "concurrent" not in m:
        return f"p95 {es(m['value'], 2)} s ({m['requests']} peticiones, {m['errors']} errores)"
    seq, con = m["sequential"], m["concurrent"]
    return (
        f"p95 {es(seq['p95'], 2)} s secuencial y {es(con['p95'], 2)} s con {con['clients']} clientes "
        f"simultáneos ({m['requests']} peticiones cada una, {m['errors']} errores)"
    )


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
        desc = plan_journeys()
        L += ["| ID | Recorrido | Resultado |", "|---|---|---|"]
        L += [f"| {i} | {desc.get(i, '')} | {r} |" for i, r in sorted(pw[2])]
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
