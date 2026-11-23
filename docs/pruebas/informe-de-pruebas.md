# Informe de pruebas

Resultados de la verificación del MVP sobre la corrida publicada `fused-cnnlstm-2026.11-v4`, según el [plan de pruebas](plan-de-pruebas.md). Las métricas se miden contra la aplicación desplegada con Docker Compose (API, base de datos y web).

## 1. Pruebas automatizadas

| Conjunto | Alcance | Casos | Fallidos |
|---|---|---|---|
| pytest | Pipeline, modelo (forma, causalidad, campo receptivo), contrato de la API contra PostGIS, roles de base de datos | 122 | 0 |
| Vitest | Leyenda, colores por umbral, cliente de API | 7 | 0 |
| Playwright | Recorridos críticos sobre la aplicación desplegada | 12 | 0 |

## 2. Escenarios críticos de extremo a extremo (M-07)

| ID | Recorrido | Resultado |
|---|---|---|
| E2E-01 | Mapa con todas las unidades del ámbito, leyenda y periodo activo (RF-01, RF-07) | Aprobado |
| E2E-02 | Cambio de periodo que actualiza mapa y barra de estado (RF-03) | Aprobado |
| E2E-03 | Panel de zona con riesgo, red año a año, registro histórico y procedencia (RF-02, RF-08, HU-23) | Aprobado |
| E2E-04 | Filtro por nivel y retiro de filtros en una acción (RF-04) | Aprobado |
| E2E-05 | Comparación de dos distritos en un mismo periodo (RF-05) | Aprobado |
| E2E-06 | Comparación de un distrito entre dos periodos (RF-06) | Aprobado |
| E2E-07 | Metodología con fuentes, variables y limitaciones (RF-08) | Aprobado |
| E2E-08 | Exportación CSV del ranking con corrida y alcance (Análisis) | Aprobado |
| E2E-09 | Vista Modelo con arquitectura, benchmark y errores del nivel alto (RM-01, RM-05) | Aprobado |
| E2E-10 | Vías críticas: ranking de calles y detalle de una calle (D-09) | Aprobado |
| E2E-11 | Densidad registrada, vista de calor continua y capa Grad-CAM (D-09) | Aprobado |
| E2E-12 | Pronóstico del año siguiente con ranking, rango del ensamble y validación 2024 (D-11) | Aprobado |

## 3. Métricas de calidad del producto

| Métrica | Descripción | Resultado | Meta |
|---|---|---|---|
| M-01 | Correspondencia espacial (eventos ONSV con coordenadas verificables) | 817/817 = 100,0 % | >= 95 % |
| M-02 | Completitud del contexto de cada resultado publicado (campos obligatorios) | 258.896/258.896 = 100,0 % | >= 95 % |
| M-03 | Trazabilidad de fuente y versión (muestra de 200 resultados, semilla fija) | 200/200 = 100,0 % | >= 95 % |
| M-04 | Reproducibilidad del pipeline | 258.896/258.896 = 100,0 % | >= 95 % dentro de tolerancia; 100 % unidad, periodo y nivel |
| M-05 | Mejora relativa frente al promedio histórico | prueba ONSV 2024 (fatales): +6,29 %; backtest CENACOM 2017 (todas las severidades): -3,28 % | > 0 % |
| M-07 | Escenarios críticos de extremo a extremo | 12/12 escenarios aprobados | 100 % y cero bloqueantes |
| M-08 | Exactitud de consultas, filtros y comparaciones | 188/188 = 100,0 % | >= 95 % global, 100 % críticos |
| M-09 | Tiempo de respuesta p95 de la API | p95 0,48 s secuencial y 1,95 s con 10 clientes simultáneos (200 peticiones cada una, 0 errores) | <= 2 s |

M-06 (requisitos funcionales aceptados) se determina en la revisión de sprint con el plan de pruebas por requisito. M-10 a M-12 se miden en las sesiones con especialistas (paquete 4.5) con los instrumentos de `docs/validacion/`. M-13 a M-15 corresponden a la gestión del proyecto.

## 4. Defectos

Los defectos encontrados por las pruebas y su corrección se registran en el [registro de incidencias](../registro-de-incidencias.md).
