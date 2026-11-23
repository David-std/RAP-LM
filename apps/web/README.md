# RAP-LM web

React + TypeScript + Leaflet analytical workspace (Figure 5C). It only reads the published results of the
API (`/api/v1`); it never computes risk.

## Views

| View | Purpose | Stories |
|---|---|---|
| Mapa de riesgo | Map by 1 km cell or district, period and filters; zone panel with risk components, network expected vs observed, hour profile, record breakdown, drivers, what-if and critical streets | HU-01 to HU-16, HU-21 to HU-27 |
| Corredores | Street-level ranking of recorded collisions, concentration curve, export | D-09 |
| Comparar | Units in one period and one unit across periods | HU-17 to HU-21 |
| Análisis | Ranking, change, persistence, district profile, CSV and GeoJSON export | analyst tools |
| Modelo | Architecture, partitions, training curves, benchmark, high-level errors, weights card | RM-01 to RM-05 |
| Metodología y fuentes | Components, sources, variables by group, limitations | RF-08, RD-05 |

## Structure

```text
src/
  api/          typed client, DTO types, request hook with cancellation
  state/        shared query state (period, view, filters, selection) synced with the URL
  components/   map, legend, zone panel, controls, SVG charts
  lib/          base map, colour ramps, formatting, export
  pages/        one file per view
  __tests__/    Vitest unit tests
e2e/            Playwright critical journeys against the Compose stack
```

## Run

```bash
npm install
npm run dev          # http://localhost:5173, proxies /api to http://127.0.0.1:8000
npm test             # unit tests
npm run typecheck
npm run build
npm run e2e          # needs `docker compose up -d` and a published run (http://localhost:8088)
```

`VITE_API_BASE_URL` overrides the API origin when the SPA is not served behind the Nginx proxy.

## Design rules

Petrol accent for interaction, red ramp reserved for risk, chart colours validated for colour-vision
deficiency and contrast. The legend uses numbers and level names, not colour alone. Text uses commas and plain
words as separators. Areas outside the 43 districts are dimmed on every map.
