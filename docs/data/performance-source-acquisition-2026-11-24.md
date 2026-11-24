# Source acquisition audit ? 2026-11-24

Development branch only. No change to RAP-LM target (all pedestrian collision
severities), published v4 model, dataset, or deployment.

## SIDPOL: alternative official download verified

- Landing: https://www.gob.pe/institucion/mininter/informes-publicaciones/7620286-base-de-datos-del-sidpol-a-diciembre-del-2025
- ZIP: https://cdn.www.gob.pe/uploads/document/file/9290152/7620286-base-de-datos-del-sidpol-a-diciembre-2025.zip?v=1768424662
- HTTP 200; 14,131,027 bytes; SHA256 d947fd5b0b14728d2bca7e06d834aa0c603122c5f1aa89bd6282d2f80a19492e.
- Seven worksheets, monthly aggregated counts, 2018?2025. Temp5/5.2 include
  occurrence district and UBIGEO, but no collision date/time or coordinates.
- Full scans of Temp4, Temp5, Temp5.2, Temp6 and Temp7 found no explicit
  atropello labels. Temp6/7 contain criminal modalities of fleeing the scene
  of a road accident, not an exhaustive pedestrian collision register.
- Do not use as pedestrian outcome labels. Do not infer zero collisions.
- Original open-data CSV route and dictionary returned HTTP 418 in prior checks.
  Alternative official publication was used without circumventing access controls.

## REATPOL/ONSV: primary acquisition target

- https://www.gob.pe/institucion/mtc/noticias/1348009-mtc-y-pnp-articulan-registro-de-accidentes-de-transito-para-fortalecer-la-seguridad-vial-a-nivel-nacional
- https://www.gob.pe/institucion/mtc/noticias/1030194-mtc-y-policia-nacional-impulsan-la-modernizacion-de-la-gestion-de-la-informacion-en-seguridad-vial
- https://www.onsv.gob.pe/datosabiertos
- Official integration of police accident registry with ONSV; explicitly includes
  fatal and nonfatal records in the broader system. Rollout is progressive.
- No verified public bulk export of the necessary all-severity records found.
  Public map (https://sratma.mtc.gob.pe/SRATMA/mapa/) has filters but no
  verified documented bulk interface. Request existing anonymised extracts.
- Official channels: https://www.onsv.gob.pe/contacto/ ;
  https://portal.mtc.gob.pe/servicios_tramite/plataforma/solicitud_informacion_publica.html ;
  https://www.gob.pe/849-ministerio-del-interior-acceso-a-la-informacion-publica-del-ministerio-del-interior

## CDC-MINSA: complementary outcome

- https://app7.dge.gob.pe/maps2/sala-Lesiones.html
- https://www.dge.gob.pe/portalnuevo/vigilancia-epidemiologica/vigilancia-de-enfermedades-no-transmisibles-utvent/
- https://www.dge.gob.pe/portalnuevo/direccion-general/unidad-asesoria-juridica/
- Surveillance counts injuries by location, time and other attributes. No verified
  public joint district-by-band pedestrian-event export. Request anonymised
  injury counts or records by occurrence district, date/band and pedestrian role;
  model as separate patient/notification population, not crash counts.

## Existing national archives: feasible transfer-learning research

Local national CENACOM archives contain DBF tables (not new contemporary data):
- 547-Modulo1092-DBF.zip: 40,418 raw accident records.
- 595-Modulo1233-DBF.zip: 68,811 raw accident records, date, hour, occurrence
  geography, crash class; 595-Modulo1234-DBF.zip: 161,110 raw person records.
- Counts are DBF header record counts, not pedestrian-specific cleaned events.
  Verify edition-specific dictionaries, codes and join keys before filtering.
- Original official source: https://www.datosabiertos.gob.pe/dataset/censo-nacional-de-comisarias-cenacom-2017-instituto-nacional-de-estad%C3%ADstica-e-inform%C3%A1tica
- ONSV national source: join by crash ID to persons with TIPO PERSONA=PEATON
  and count distinct crash IDs. Outside province of Lima: 543 (2021), 571
  (2022), 457 (2023), 297 (2024), 165 (2025 preliminary). Inside province:
  179, 198, 232, 233, 55 respectively, matching prior fusion inputs.
  These are fatal crashes involving pedestrians, not necessarily pedestrian
  fatalities, and pre-quality-filter counts. Coverage by region/year still
  requires qualification; no assumption of complete annual observation.
- Transfer pretraining may increase sample size; exclude Lima from source
  pretraining and respect target fold chronology (no later outcomes for
  earlier validation). Reconstruct comparable context at source geography.
  Do not merge source populations or claim new Lima observations.
- ArcGIS public layers 7f7155e230364d169b537c1258aa6870 (104 features,
  station-level aggregate fields) and f9ce827f2f4c41f3b660f29935130e89
  (educational layer citing INEI 2014) rejected as new outcome sources.

## Request text (not submitted)

Solicito copia digital, en formato CSV/XLSX o formato estructurado disponible,
de los registros anonimizados de siniestros de tr?nsito que involucren peatones
en los 43 distritos de la provincia de Lima, correspondientes a 2018?2025 y,
si existe, el periodo disponible de 2026. Incluir eventos fatales y no fatales
(atropello, atropello y fuga, choque con atropello y otros con participaci?n
peatonal). Solicito las variables existentes: identificador an?nimo del
siniestro, fecha y hora o franja horaria, UBIGEO del lugar de ocurrencia,
coordenadas o referencia vial cuando est?n disponibles, clase de siniestro,
participaci?n peatonal, n?mero de lesionados y fallecidos y fuente de registro.
Solicito asimismo el diccionario de variables y documentaci?n existente sobre
cobertura, periodos incompletos, comisar?as incorporadas y actualizaci?n.

No solicito nombres, documentos de identidad, tel?fonos, placas, domicilios
personales ni historias cl?nicas. Si no es viable entregar registros
individuales anonimizados, solicito las tablas agregadas existentes con el
mayor detalle conjunto disponible de distrito de ocurrencia, mes, tipo de d?a,
franja horaria, modalidad y severidad, con sus respectivos conteos. Si solo se
dispone de un subconjunto, agradecer? se precise la cobertura. La informaci?n
ser? utilizada para investigaci?n universitaria de seguridad vial.

For CDC-MINSA specify surveillance notifications of pedestrian injuries by
accident occurrence geography, dates/time bands and severity; ask whether
notifications count people or events and for duplicate/coverage documentation.
No request submitted by this audit; applicant must submit through official channel.
