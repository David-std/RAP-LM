# Informe de pruebas

Resultados de la verificación del MVP sobre la corrida publicada `fused-cnnlstm-2026.11-r1`, según el [plan de pruebas](plan-de-pruebas.md). Las métricas se miden contra la aplicación desplegada con Docker Compose (API, base de datos y web).

## 1. Pruebas automatizadas

| Conjunto | Alcance | Casos | Fallidos |
|---|---|---|---|
| pytest | Pipeline, modelo (forma, causalidad, campo receptivo), contrato de la API contra PostGIS, roles de base de datos | 112 | 0 |
| Vitest | Leyenda, colores por umbral, cliente de API | 7 | 0 |
| Playwright | Recorridos críticos sobre la aplicación desplegada | 8 | 0 |

## 2. Escenarios críticos de extremo a extremo (M-07)

- Aprobado: E2E-01 RF-01 RF-07: map shows every unit of the scope with legend and active period
- Aprobado: E2E-02 RF-03 HU-11: changing the period updates map and status together
- Aprobado: E2E-03 RF-02 RF-08 HU-06 HU-07: unit detail with index, level, record and provenance
- Aprobado: E2E-04 RF-04 HU-13 HU-16: level filter applies and clears in one action
- Aprobado: E2E-05 RF-05 HU-17: compare two districts in the same period
- Aprobado: E2E-06 RF-06 HU-20: compare one district between two periods
- Aprobado: E2E-07 RF-08 HU-24..HU-26: methodology lists sources, variables, limitations and evaluation
- Aprobado: E2E-08 analyst ranking exports CSV with run and scope

## 3. Métricas de calidad del producto

| Métrica | Descripción | Resultado | Meta |
|---|---|---|---|
| M-01 | Correspondencia espacial | 817/817 = 100.0 % | >= 95 % |
| M-02 | Completitud del contexto de cada resultado | 258.896/258.896 = 100.0 % | >= 95 % |
| M-03 | Trazabilidad de fuente y versión | 200/200 = 100.0 % | >= 95 % |
| M-04 | Reproducibilidad del pipeline | 258.896/258.896 = 100.0 % | >= 95 % dentro de tolerancia; 100 % unidad, periodo y nivel |
| M-05 | Mejora relativa frente al promedio histórico | 2026.11-r1: +3.85 %; backtest-2017: -6.29 % | > 0 % |
| M-07 | Escenarios críticos de extremo a extremo | 8/8 escenarios aprobados | 100 % y cero bloqueantes |
| M-08 | Exactitud de consultas, filtros y comparaciones | 188/188 = 100.0 % | >= 95 % global, 100 % críticos |
| M-09 | Tiempo de respuesta p95 de la API | p95 0.19 s (200 peticiones, 0 errores) | <= 2 s |

M-06 (requisitos funcionales aceptados) se determina en la revisión de sprint con el plan de pruebas por requisito. M-10 a M-12 se miden en las sesiones con especialistas (paquete 4.5) con los instrumentos de `docs/validacion/`. M-13 a M-15 corresponden a la gestión del proyecto.

## 4. Defectos

Los defectos encontrados por las pruebas y su corrección se registran en el [registro de incidencias](../registro-de-incidencias.md).
