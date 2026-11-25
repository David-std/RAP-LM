# V13 pilot: transfer learning from other Peruvian cities (fixed before training)

Development branch only. Product scope unchanged: 43 districts of Lima, all severities.

## Data

- Source provinces: Arequipa (0401), Callao (0701), Trujillo (1301), Cusco (0801),
  Chiclayo (1401), Santa (0218), Huancayo (1201), Piura (2001), Tacna (2301), Ica (1101).
- CENACOM pedestrian collisions of every edition with AT105 in 1, 2, 7 (the Lima
  harmonisation rule), event year 2011-2017, valid date and hour. District of
  occurrence from AT104D (2015 onwards) or the station district (earlier editions).
  District level only: no street geocoding exists outside Lima. Districts with at least
  15 events in 2011-2017; 1 km grids built with the same code as Lima
  (pipelines.spatial.grid, EPSG:32718) on the national district layer
  (juaneladio/peru-geojson, peru_distrital_simple.geojson, SHA-256 1eba0da3...).
  Result: 15,723 events, 104 districts, 34,890 cells.
- Population: WorldPop annual series built exactly as for Lima
  (pipelines.fusion.context.annual_population), standardised with Lima's statistics.

## Inputs shared by Lima and the sources

Population of the year (frozen after the last training year), cell mask, and for each
source the previous-year district density and its observed flag. Cell-level history
and the Lima-only context layers are excluded because the sources do not have them.

## Arms (ConvLSTM, hidden 32, lr .003, seeds 1-5, fixed 150 epochs in Lima as in A1)

- A: Lima only, reduced inputs.
- B: 150 epochs on the source cities (CENACOM years up to the fold's last Lima training
  year), then 150 epochs in Lima, reduced inputs.
- Reference: C0 with the full Lima inputs (v10).

Folds D2b (evaluate CENACOM 2016) and D3b (evaluate ONSV 2023). B is adopted for a full
version only if it improves A in both folds on cell AP (all located) and district MAE.
