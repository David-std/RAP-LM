# V6 validation-only performance investigation

18 fits; no test evaluations or production export. See protocol docs/ml/performance-v6.md.

| Arm | ONSV 2023 MAE | Improvement | CENACOM 2016 MAE | Improvement |
|---|---:|---:|---:|---:|
| H0 | 0.57312 | +4.99% | 1.78461 | +4.23% |
| H1 | 0.57130 | +5.29% | 1.78102 | +4.42% |
| H2 | 0.58983 | +2.22% | 1.78461 | +4.23% |
| H3 | 0.60311 | +0.01% | 1.78102 | +4.42% |
| H4 | 0.59394 | +1.53% | 1.78102 | +4.42% |
| Q1 | 0.61073 | -1.25% | 1.80758 | +2.99% |
| Q2 | 0.58529 | +2.97% | 2.11367 | -13.43% |
| Q3 | 0.59002 | +2.19% | 1.84412 | +1.03% |
| Q4 | 0.57935 | +3.95% | 1.80374 | +3.20% |

## Decision

No arm meets the fixed research gate. H1 gives modest improvements over H0 but not a substantial joint gain. H2-H4 do not improve the main fold. H2/H0 and H3/H4/H1 coincide in the CENACOM-only fold because there are no ONSV observations. H0 differs slightly from the earlier E0 due to objective reduction order. Q1-Q4 do not justify replacing the published model. Q2 removes district-level proxy supervision and materially worsens CENACOM MAE. Q3 improves CENACOM top-10% capture but not MAE. These development folds were repeatedly inspected; no generalisation claim or independent test result is made.

## Diagnostic: published v4, validation only

ONSV 2023: 232 observed events, 183.94 estimated, historical baseline 188.50. Among 344 district-band combinations, 197 have zero events. Absolute errors on zero/one/2+ groups: baseline 54.0/72.5/81.0 vs model 62.972/57.549/77.315. CENACOM 2016: 1875 observed, 1877.21 estimated, historical baseline 1962.40. Absolute errors on zero/one/2+ groups: baseline 66.4/67.8/506.8 vs model 62.167/57.717/461.722. These are retrospective observation-scale diagnostics, not all-severity estimates for ONSV.

## Source review (2026-11-24)

- CENACOM: 8,005 station-proxy records in 2011-2014; occurrence-district records in 2015-2017. The INEI public census catalogue lists the 2017 edition: https://www.inei.gob.pe/estadisticas/censos/. No newer equivalent microdata verified.
- SIDPOL: https://www.datosabiertos.gob.pe/dataset/denuncias-policiales-registradas-nivel-nacional-mininter. Resource metadata accessible from local PC; official download route and dictionary returned HTTP 418. No schema, pedestrian coverage, temporal granularity, or spatial resolution verified. Not incorporated.
- MINSA surveillance: https://app7.dge.gob.pe/maps2/sala-Lesiones.html. Search metadata indicates injury counts by district and other summaries; no joint pedestrian district-band event table verified, and patient counts are not crash counts. Not incorporated.
- MTC/INEI published aggregate reports: useful as magnitude checks, not district-band pedestrian collision records. https://www.gob.pe/institucion/mtc/informes-publicaciones/6966856-estad-sticas-transportes-terrestre-por-carretera-accidentes-de-tr-nsito.
- SOAT/CAT local workbook is reimbursement/person-level, not a verified pedestrian collision event register; no hour or explicit pedestrian role in inspected primary sheet. No personal rows retained or published.
- ONSV 2025 remains as qualified in v5; do not treat partial Lima fatal observations as all-severity data.

## Verification

40 targeted model/experiment tests passed, including four additional tests for bounded observation factors, conservation, quality-weight loss and causal history. Ruff passed. The target remains relative all-severity intensity; overlapping severity-resolved observations are still needed to identify observation factors and verify contemporary all-severity estimates.
