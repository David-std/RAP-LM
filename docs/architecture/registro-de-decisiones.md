# Registro de decisiones técnicas y solicitudes de cambio

Cada entrada indica si **aplica sin cambiar la línea base** (decisión de implementación) o si es una
**solicitud de cambio** que el equipo debe aprobar mediante el control integrado de cambios (comunicación
C-05 del plan, métrica M-15). El estado "Pendiente de aprobación" se mantiene hasta que el Project Manager
registra la aprobación del equipo.

| ID | Fecha | Tipo | Estado |
|---|---|---|---|
| D-01 | 2026-11-22 | Solicitud de cambio (datos, objetivo) | Aprobada por el PM (2026-11-23) |
| D-02 | 2026-11-22 | Decisión de implementación (nombres de API) | Aplicada, a revisar en PR |
| D-03 | 2026-11-22 | Decisión de implementación (malla) | Aplicada |
| D-04 | 2026-11-22 | Decisión de implementación (persistencia) | Aplicada |
| D-05 | 2026-11-22 | Decisión de implementación (benchmark) | Aplicada |
| D-06 | 2026-11-22 | Solicitud de cambio (contrato API: recurso `/series`) | Aprobada por el PM (2026-11-23) |
| D-07 | 2026-11-22 | Decisión de implementación (retiro del prototipo sintético) | Aplicada |
| D-08 | 2026-11-22 | Decisión de implementación (definición de periodos) | Aplicada |
| D-09 | 2026-11-22 | Solicitud de cambio (contrato API: corredores, explicaciones y ficha del modelo) | Aprobada por el PM (2026-11-23) |
| D-10 | 2026-11-22 | Solicitud de cambio (dataset v1.1: exposición, entorno, severidad; tres componentes de riesgo) | Aprobada por el PM (2026-11-23) |
| D-11 | 2026-11-23 | Solicitud de cambio (pronóstico anual un paso adelante y vista Pronóstico) | Aprobada por el PM (2026-11-23) |
| D-12 | 2026-11-23 | Solicitud de cambio (dataset v1.2: población anual, tipo de vehículo y servicio; iteración v3) | Aprobada por el PM (2026-11-23) |
| D-13 | 2026-11-23 | Activación de recursos condicionales (GPU y despliegue web de demostración) | Aprobada por el PM (2026-11-23) |
| D-14 | 2026-11-23 | Política espacial de eventos con solo distrito de comisaría (dataset v1.4, iteración v4) | Aprobada por el PM (2026-11-23) |
| D-15 | 2026-11-23 | Solicitud de cambio (meta de M-09: p95 ≤ 2,5 s bajo carga concurrente) | Aprobada por el PM (2026-11-23) |
| D-16 | 2026-11-23 | Pronóstico anual encadenado 2025–2027 | Aprobada por el PM (2026-11-23) |

---

## D-01. Objetivo "todos los atropellos" mediante fusión de fuentes

**Requisitos y EDT:** RD-01..RD-06, RM-01..RM-05, RG-01; paquetes 3.1.1, 3.2.1, 3.2.2, 3.2.3, 4.4.
**Contexto:** en la primera revisión el profesor observó que el riesgo no puede limitarse a atropellos fatales.
El dataset v0.2.0 tenía los gates G1, G3, G4, G5 y G6 bloqueados: no existe una sola fuente reciente, de todas las
severidades, con ubicación en los 43 distritos.
**Decisión:** el objetivo es la intensidad latente de **todos los atropellos** (cualquier severidad y subtipo),
estimada por una red CNN-RNN que trata cada fuente como una observación parcial del mismo fenómeno:

- CENACOM 2011–2017 (todas las severidades) con factor de registro 1 (escala de referencia);
- ONSV 2021–2024 (siniestros con fallecido) con factor de registro aprendido;
- coberturas temporales como *offset* (2017 solo cubre enero a junio; 2018–2020 sin fuente: no se publican).

CENACOM no tiene coordenadas. Se georreferencia con reglas explícitas contra calles de OpenStreetMap del
distrito declarado: un cruce da un punto, una sola calle reparte el evento a lo largo de su tramo y, sin
coincidencia, el evento queda a nivel distrito. No se inventan coordenadas
(`pipelines/fusion/geocode.py`). Esto levanta el gate G4 con reglas documentadas y G1 mediante la fusión.
G3 (factores de expansión) no se usa: se trabaja con conteos registrados. G6 (exposición) sigue sin medida
directa y se declara como limitación.
**Alternativas descartadas:**

- Publicar solo fatales: contradice la observación del profesor y el título del proyecto.
- Usar solo CENACOM por distrito: no sirve para la malla CNN y deja fuera 2021–2024.
- Extrapolar con factores de expansión: no son confiables (1.117 factores inválidos auditados).

**Impacto:**

- Alcance y título: no cambian.
- Calidad: el modelo se evalúa en 2024 solo contra la observación ONSV. Por eso se agrega un backtest de todas
  las severidades (CENACOM 2017).
- Riesgos: R-datos, porque el supuesto de un factor ONSV espacialmente constante queda como la limitación L02.
- Cronograma: absorbido en la recuperación de la semana del MVP.

**Pendiente:** aprobación del equipo, registro en la matriz de cambios y en la Matriz de Trazabilidad (RD-05).

## D-02. Nombres de recursos de la API en inglés

**Requisitos:** RT-02 (HT-03, HT-09). **Contexto:** el informe (Figura 5D) nombra `/periodos`, `/unidades`,
`/riesgo`, `/comparaciones`, `/procedencia`. El Product Owner solicitó nombres estándar en inglés.
**Decisión:** `/api/v1/periods`, `/units`, `/risk`, `/comparisons`, `/provenance`, con correspondencia uno a
uno documentada en `docs/api/contract.md`. El plan fija la función de cada recurso, no su ruta exacta; la
obligación funcional y las pruebas se mantienen. **Impacto:** ninguno en requisitos; el
frontend consume el contrato nuevo en el mismo PR.

## D-03. Malla de 1 km en EPSG:32718 recortada a los 43 distritos

**Requisitos:** RD-03, RD-04, RG-01 (HT-04, HT-05). **Contexto:** el prototipo de Design usa una malla en grados
(0,009° × 0,0092°) con 2.750 celdas y descarta celdas con menos del 35 % de superficie.
**Decisión:** la malla es de cuadrados reales de 1 km en UTM 18S (CRS métrico). Conserva toda celda que
intersecta el ámbito, recortada al límite, para no perder eventos de bordes: quedan 2.899 celdas.
La pertenencia se resuelve así:

- `district_fractions` guarda la participación por área;
- el distrito "dueño" es el de mayor área y solo sirve para filtrar y rotular;
- los conteos se asignan por punto en polígono.

Los IDs mantienen la convención `F{fila}-C{columna}` del diseño.

## D-04. Una tabla de resultados por representación y publicación atómica

**Requisitos:** RT-03, RM-04 (HT-10, HT-11). **Decisión:** `risk_result` guarda celdas y distritos con
`representation_id`, en lugar de una tabla `district_result` separada, porque es el mismo contrato y las mismas
reglas. El índice distrital agrega las intensidades de sus celdas por área (nunca promedia etiquetas) y tiene
su propia distribución de referencia. La publicación ocurre en una sola transacción con conciliación de filas
y sumas contra `results.csv`; el puntero activo solo puede apuntar a corridas `published` (trigger). Hay roles
separados: `raplm_reader` (API, solo lectura), `raplm_publisher` (lotes) y el dueño (migraciones).

## D-05. Benchmark ampliado con implementaciones de la literatura

**Requisitos:** RM-01 (HT-02), M-05. **Decisión:** además del promedio histórico (enfoque base comprometido) se
comparan ConvLSTM (Shi et al., 2015; base de Hetero-ConvLSTM, Yuan et al., 2018) y un GLM de Poisson,
junto con dos ablaciones (solo CNN y solo LSTM). El modelo publicado es el candidato CNN-RNN con menor
pérdida de validación; los demás se reportan aunque ganen. El protocolo se congeló antes de evaluar la
prueba (`docs/ml/benchmark-protocol.md`).

## D-06. Recurso adicional `GET /api/v1/series` para vistas de analista

**Requisitos:** RF-03, RF-06; mejora pedida por el Product Owner para que la herramienta sea útil a analistas
e instituciones (ranking, cambio, persistencia, perfil distrital y exportación). **Decisión:** se agrega un
sexto recurso de solo lectura que devuelve, por unidad, el índice de todos los años publicados para un tipo de
día y una franja. Calcular la persistencia con `/risk` exigiría 11 consultas de unas 2.900 filas.
**Impacto:** amplía el contrato de la Figura 5D, sin escrituras ni recomendaciones (RG-02, RG-03). Necesita
aprobación como cambio de contrato (C-05).

## D-07. Retiro del `RiskProvider` sintético de la ruta de producción

**Requisitos:** RT-02, RG-02. **Decisión:** se eliminan `GET /risk`, `GET /risk/map`, `POST /risk/compare` y
`/metadata/*` del prototipo, junto con sus pruebas. Calculaban un puntaje SHA-256 en cada petición, lo que
contradice la arquitectura por lotes. Si no hay corrida publicada, la API responde `503 NO_PUBLISHED_RUN` y no
devuelve datos simulados. Los datos de ejemplo solo existen como fixture `is_demo=true` en las pruebas de
contrato.

## D-08. Periodo = año × tipo de día × franja de 6 horas

**Requisitos:** RF-03. **Decisión:** se adopta la definición del prototipo validado (PR-01): laborable o fin de
semana × 0–6, 6–12, 12–18 y 18–24 h, por año. Los años publicados son 2011–2017 y 2021–2024, es decir, los años
con alguna fuente. El indicador se anualiza por número de días del tipo para que laborable y fin de semana sean
comparables. Los eventos sin hora se excluyen de las franjas y quedan contados en el reporte de fusión.

## D-09. Capas de analista: corredores, explicaciones y ficha del modelo

**Requisitos:** RF-02, RF-08, RNF-01, RM-02, RM-03; pedido del Product Owner tras revisar la interfaz: un analista
necesita precisión de calle, entender cómo estima la red y poder explorar escenarios.
**Decisión:** tres recursos de solo lectura más, calculados por lotes (RG-02 se mantiene):

- `/api/v1/corridors`: calles con atropellos registrados por distrito, en la línea de las redes de alto riesgo de
  los programas Visión Cero;
- `/api/v1/explanations`: estimado frente a observado por año, atribución por oclusión y dependencia parcial por
  distrito (simulación con controles deslizantes, precalculada);
- `/api/v1/model`: arquitectura, curvas de entrenamiento, benchmark, errores del nivel alto y SHA de los pesos.

Nada de esto recomienda intervenciones (RG-03). **Impacto:** amplía el contrato de la Figura 5D (C-05) y agrega
la migración `0002` y la vista *Corredores* y *Modelo* de la interfaz.

## D-10. Dataset v1.1 y tres componentes del riesgo (frecuencia, severidad, exposición)

**Requisitos:** RD-05, RM-05; plan v1.6 §1.2 (Guo et al., 2024; Hu et al., 2024): el riesgo se relaciona con la
frecuencia, la severidad, la exposición peatonal, el volumen de tránsito y el entorno vial, y la evaluación
técnica separa "conteos" de "riesgo ajustado por exposición". **Brecha detectada:** el MVP solo modelaba la
frecuencia y usaba siete proxies de contexto; no había índice ajustado por exposición ni componente de severidad, y
no se reportaban los falsos positivos y negativos del nivel alto que define el plan.
**Decisión:**

1. Dataset `fused-v1.1.0` con ocho proxies de OSM (comercio y servicios, centros educativos y de salud, cruces,
   semáforos, veredas y vías peatonales, vías arteriales como proxy del volumen de tránsito, vías colectoras) y con
   subtipo y severidad por evento.
2. Tres indicadores por zona y periodo:
   - frecuencia (λ de la red, índice principal);
   - severidad esperada (λ × probabilidad de desenlace fatal suavizada por Bayes empírico con los años de
     entrenamiento);
   - razón ajustada por exposición (λ / λ esperado por un modelo que solo ve exposición, lógica de razón
     observados/esperados).
3. Desglose del registro histórico por subtipo y severidad.
4. Falsos positivos y negativos, precisión y recall del nivel alto para el modelo y el promedio histórico.

La v2 del modelo se entrena sobre v1.1 con la enmienda A1, registrada antes de reiniciar la búsqueda.
**Limitación que persiste:** no existe exposición peatonal medida (aforos) para los 43 distritos; los proxies se
declaran como tales (L06). **Impacto:** migración `0003`, campos `severity`, `exposure` y `breakdown` en la API.

## D-11. Pronóstico anual un paso adelante

**Requisitos:** RM-04, RF-01; propuesta del curso (datos de tránsito e historial → ConvLSTM → predicción de riesgo
→ mapa de calor); restricción RG-02. **Contexto:** el producto presentaba la estimación de los años observados; la
capacidad de la red de proyectar el año siguiente solo se evidenciaba en la evaluación de 2024.
**Decisión:** la red es causal (las entradas del año t solo usan observaciones de t-1), por lo que añadir el año
siguiente al eje temporal produce un pronóstico genuino con los pesos publicados, sin reentrenar.
`ml.fused.forecast` verifica que los años observados reproduzcan exactamente las estimaciones publicadas, y luego
escribe por unidad y subperiodo del año siguiente el índice, el nivel, el rango del ensamble (mínimo y máximo de los
cinco modelos), el índice del último año observado y, por distrito, los atropellos esperados en la escala de
referencia. Se publica en la tabla `forecast` (migración 0005), se sirve en `GET /api/v1/forecast` y se muestra en la
vista Pronóstico con la validación del mismo procedimiento en 2024.
**Alcance:** pronóstico anual para planificación y priorización; no es alerta en tiempo real ni se ejecuta a demanda
(RG-02). **Impacto:** una tabla, un recurso de lectura y una vista; sin cambios en los requisitos existentes.

## D-12. Dataset v1.2: población anual, tipo de vehículo y servicio de transporte

**Requisitos:** RD-05, RM-05, RF-02 (detalle de zona); limitaciones declaradas de la v2. **Contexto:** la población
era una superficie fija de 2020 aplicada a todos los años, y el registro histórico no indicaba qué vehículo
participó en cada atropello ni si era transporte público o particular, aunque ambas fuentes lo registran.
**Decisión:**

1. Población residente del año de cada periodo: WorldPop R2025A 2015–2025 (serie anual), encadenada hacia
   2011–2014 con la variación relativa de cada celda en la serie anual 2000–2020.
2. Tipo de vehículo (auto, camioneta, combi o minibús, bus, carga, moto, mototaxi, bicicleta o triciclo, no
   identificado) y servicio (público, particular, carga, no identificado) de cada evento. Se leen de los
   microdatos del capítulo 100 de CENACOM, cuya lista de códigos cambia entre ediciones (17, 18 y 19 tipos), y del
   registro de vehículos del ONSV. Un evento con varios vehículos reparte su peso por igual.
3. El vehículo y el servicio alimentan el desglose del registro histórico y las vías críticas, no la entrada de
   la red. La población anual sí entra a la red (iteración v3, enmienda A2 del protocolo).

4. Dataset v1.3 = v1.2 más los factores que la policía registra en cada atropello (exceso de velocidad, ebriedad
   del conductor o del peatón, conducta del conductor o del peatón, señalización defectuosa, falta de iluminación,
   vía en mal estado, vehículo, clima). La lista de CENACOM cambia entre ediciones (12, 15, 18 y 19 códigos); en
   ONSV se usa la causa específica. Son causas anotadas después del hecho: describen el registro y nunca entran a
   la red, porque usarlas como predictor filtraría el resultado. El tensor de entrada de v1.3 es idéntico byte a
   byte al de v1.2; la exportación lo verifica antes de usar v1.3 con un modelo entrenado en v1.2.
5. Perfil del entorno de cada celda y distrito: semáforos y cruces por km de vía, veredas por km de vía, vías
   arteriales, comercio, centros educativos y de salud, paraderos y población por km², con el percentil de la zona
   en Lima. Son las mismas condiciones previas que lee la red, expresadas para el analista.

**Alcance:** la v3 reemplaza a la v2 solo si mejora el error de validación. Los factores y el perfil describen;
no generan recomendaciones de intervención (RG-03). **Impacto:** datasets nuevos, migraciones 0006 (vehículos y
factores por calle) y 0007 (perfil del entorno), y campos opcionales en el desglose y la explicación de la API.

## D-13. Activación de recursos condicionales: GPU y despliegue web de demostración

**Requisitos:** plan v1.6, recursos condicionales (cómputo con GPU y despliegue web, presupuestados con
precios de referencia y registrados sin asignación mientras no se activen); RNF-02; validación con
especialistas (paquete 4.5). **Necesidad técnica:**

1. GPU: cada iteración del protocolo (búsqueda de 16 configuraciones y ensamble de 5) tomaba unos 33 minutos
   en CPU y las explicaciones varias horas. En GPU la misma búsqueda toma unos 4 minutos y las explicaciones
   minutos, lo que permitió las corridas de ablación y de backtest dentro del plazo. La corrida publicada y su
   reproducibilidad (M-04) se mantienen en CPU.
2. Despliegue web: la demostración en clase y las sesiones con especialistas requieren abrir la aplicación sin
   instalar Docker. `render.yaml` crea la base gestionada con PostGIS, la API de solo lectura y la web estática;
   `tools/deploy/remote_setup.py` carga los datos con roles separados y publicación atómica.

**Alcance:** demostración y validación, no operación productiva (exclusión del plan). **Impacto en costos:** GPU
local sin costo adicional; despliegue en el plan gratuito de Render, o el plan inicial de la API durante el mes
de la demostración si se requiere evitar la suspensión por inactividad. El Project Manager registra el monto
que se active contra la reserva correspondiente.

## D-14. Política espacial de los eventos ubicados solo por la comisaría

**Origen:** auditoría previa a la fusión (hallazgo P0-01). **Contexto:** unos 8.000 registros de CENACOM no traen
distrito de ocurrencia; la fusión usaba el distrito de la comisaría y luego buscaba la dirección en ese distrito,
llevando el evento a una calle o celda. **Evidencia:** en 2016 y 2017, donde existen ambos datos, el distrito de la
comisaría coincide con el de ocurrencia en el 93,2 % de 5.378 eventos. **Decisión:** el distrito de la comisaría se
acepta como ubicación a nivel distrito, declarada; esos eventos ya no se geocodifican a calle ni celda, y la fusión
rechaza cualquier evento de comisaría con geometría. Un brazo de sensibilidad los excluye por completo. **Impacto:**
dataset v1.4, iteración v4 (enmienda A3), mapas de celda y vías críticas sin esos eventos.

## D-15. Meta de M-09 bajo carga concurrente

**Contexto:** el plan fija p95 ≤ 2 s sin precisar la carga. Con 200 consultas secuenciales el p95 es 0,4 a 0,5 s; con
10 clientes simultáneos que piden el mapa completo de 2.899 celdas (4,4 MB por respuesta) queda entre 1,7 y 2,1 s,
aun con 4 procesos de API y caché de respuestas. **Decisión propuesta:** meta de p95 ≤ 2,5 s medida en ambas
condiciones (secuencial y 10 clientes). **Impacto:** cambia el umbral de una métrica de calidad de la línea base;
requiere aprobación en el control de cambios (M-15). Mientras no se apruebe, los informes muestran ambos umbrales.


## D-16. Pronóstico anual encadenado 2025–2027

**Decisión:** extender D-11 a tres horizontes con los pesos publicados de la v4 y covariables congeladas en 2024.
La media del ensamble, en la escala de observación ONSV, alimenta los canales de historial del paso siguiente.
Los datos observados y la escala de referencia permanecen intactos. Se conserva el pronóstico original de 2025.
La tabla existente admite varios horizontes; la API selecciona uno y la vista permite cambiar de año.
**Limitación:** la validación de 2024 corresponde a un paso y a siniestros fatales. No demuestra exactitud a
dos o tres años; el desacuerdo entre miembros no es un intervalo de predicción calibrado ni representa toda
la incertidumbre acumulada. No se introducen datos futuros observados ni inferencia en tiempo real.
