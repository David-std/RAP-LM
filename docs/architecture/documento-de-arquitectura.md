# Documento de arquitectura de software

**Sistema:** RAP-LM, aplicación web basada en redes neuronales para el análisis espaciotemporal del riesgo de
atropello peatonal en Lima Metropolitana.
**Línea base:** plan integrado del proyecto v1.6, sección 3.11 (Figuras 5A a 5E) y Tabla 14A.
**Notación:** modelo C4; fuentes C4-PlantUML en [`c4/`](c4/).

## 1. Propósito y alcance

El sistema permite a especialistas en seguridad vial, análisis territorial y tránsito consultar, comparar,
analizar y exportar el riesgo relativo de atropello peatonal (todas las severidades) en los 43 distritos de la
provincia de Lima, por celda de 1 km, distrito, calle y periodo. Cada resultado se acompaña de su procedencia y de
la explicación de cómo lo estimó la red.

Una cadena *datos de historial y contexto → ConvLSTM (CNN + RNN) → estimación del riesgo → mapa de calor*
organiza el sistema, con mapas de densidad del registro histórico y mapas Grad-CAM para explicar el modelo.

Fuera del alcance:
- operación en tiempo real (RG-02);
- recomendaciones de intervención (RG-03);
- territorio fuera de los 43 distritos (RG-01).

## 2. Restricciones y decisiones de base

| Restricción | Origen | Efecto en la arquitectura |
|---|---|---|
| Procesamiento por lotes | RG-02 | Ninguna petición entrena ni ejecuta el modelo; la API solo lee resultados publicados |
| Equipo de tres personas, un dominio de consulta | Plan v1.6 | Monolito modular en lugar de microservicios |
| Reproducibilidad | RNF-02 | Versiones fijadas, semillas, hilos fijos, hash de cada artefacto y linaje del código |
| Ámbito de 43 distritos | RG-01 | Validación de UBIGEO 1501xx en datos y API; máscara de ámbito en los mapas |
| Herramientas gratuitas o de código abierto | Plan v1.6, sección 3.9 | Stack libre; GPU y despliegue de pago como recursos condicionales |

Las decisiones de detalle y las solicitudes de cambio están en [architecture/registro-de-decisiones.md](../architecture/registro-de-decisiones.md).

## 3. Estilo arquitectónico

**Monolito modular por capas con un pipeline analítico por lotes separado.**

- La aplicación de consulta es un único despliegue de API organizado en capas:
  - presentación: routers;
  - contratos: esquemas;
  - aplicación: servicios;
  - datos: repositorios.
- El pipeline produce artefactos versionados y publica cada corrida en la base de datos; la aplicación solo los
  consulta.
- La separación principal es temporal: el entrenamiento y la evaluación ocurren fuera de línea.
- Se descartan los microservicios porque, para un solo dominio y la carga acotada de la validación, añadirían
  despliegue, comunicación entre procesos y monitoreo sin una necesidad de escalado o autonomía.
- La modularidad interna permite separar el pipeline o el módulo de análisis si el alcance crece.

## 4. Vistas

### 4.1. Contexto (C4 nivel 1, Figura 5A)

| Elemento | Relación con el sistema |
|---|---|
| Usuario especializado | Consulta, compara, analiza y exporta desde el navegador |
| Backend Developer y QA | Ejecuta el pipeline y publica corridas |
| Fuentes públicas (CENACOM, ONSV, INEI, WorldPop, MINAM, OpenStreetMap) | Instantáneas registradas con URL, licencia, fecha y SHA-256 |
| Servicio de teselas (Esri World Light Gray, sin clave de API) | Fondo cartográfico; no aporta datos analíticos |

### 4.2. Contenedores (C4 nivel 2, Figura 5B; fuente [`c4/5B_contenedores.puml`](c4/5B_contenedores.puml))

| Contenedor | Tecnología | Responsabilidad |
|---|---|---|
| Aplicación web | React, TypeScript, Leaflet, servida por Nginx | Mapa en malla de 1 km, por distrito o como superficie de calor continua; vistas de corredores, comparación, análisis, modelo y metodología; proxy inverso `/api` |
| API de consulta | Python, FastAPI, Pydantic, SQLAlchemy | Recursos de solo lectura con contratos validados y errores definidos |
| Base de datos espacial | PostgreSQL + PostGIS | Geometrías, periodos, corridas, resultados, vías críticas, explicaciones, pronóstico y procedencia |
| Migración | Alembic | Contenedor de un solo uso que aplica el esquema versionado |
| Pipeline analítico | Python, PyTorch, Shapely, PyProj | Fusión de fuentes, malla, tensores, entrenamiento, evaluación, explicaciones y publicación |

### 4.3. Componentes de la aplicación web (C4 nivel 3, Figura 5C; [`c4/5C_componentes_web.puml`](c4/5C_componentes_web.puml))

- **Estado y acceso a datos:** estado de consulta único (periodo, vista, filtros y selección) sincronizado con la
  URL, y cliente de API tipado con cancelación de solicitudes.
- **Mapa:** capas de riesgo estimado, registro histórico e influencia de la red.
- **Panel de zona:** riesgo con tres componentes, la red año a año, perfil horario, desglose del registro,
  influencia, atribución, simulación de contexto, calles críticas y procedencia.
- **Vistas de apoyo:** Pronóstico, Vías críticas, Comparadores, Análisis, Modelo y Metodología.

### 4.4. Componentes de la API (C4 nivel 3, Figura 5D; [`c4/5D_componentes_api.puml`](c4/5D_componentes_api.puml))

| Capa | Componentes |
|---|---|
| Routers | Consulta: `/periods`, `/units`, `/risk`, `/comparisons`, `/provenance`, `/series`. Análisis: `/corridors`, `/explanations`, `/model` |
| Esquemas | Validación de parámetros y forma de las respuestas (Pydantic) |
| Servicios | Corrida activa fijada por petición, unidades sin resultado como estado explícito, reglas de comparabilidad |
| Repositorios | Consultas parametrizadas con SQLAlchemy Core y funciones PostGIS |
| Errores | Esquema único; 404, 409, 422 y 503 sin datos sustitutos |

El contrato completo está en [api/contract.md](../api/contract.md).

### 4.5. Pipeline analítico (C4 nivel 3, Figura 5E; [`c4/5E_pipeline.puml`](c4/5E_pipeline.puml))

1. Registro de fuentes con hash.
2. Malla de 1 km en EPSG:32718 recortada a los 43 distritos.
3. Fusión de todos los atropellos y ubicación por cruce, tramo de calle o distrito.
4. Variables de exposición y entorno.
5. Tensores años × variables × malla con entradas causales.
6. Entrenamiento y benchmark: variantes CNN-RNN (ConvLSTM y CNN-LSTM; la parte recurrente es una LSTM), GLM de
   Poisson, ablaciones y promedio histórico.
7. Evaluación en un año posterior al entrenamiento.
8. Exportación de frecuencia, severidad y exposición, y explicaciones.
9. Publicación atómica.

### 4.6. Despliegue

Docker Compose define los servicios:
- `db`: PostgreSQL + PostGIS con volumen persistente;
- `migrate`: de un solo uso;
- `api`: usuario sin privilegios y chequeo de salud;
- `web`: Nginx;
- `pipeline`: perfil por lotes, que se ejecuta bajo demanda.

La configuración se inyecta por variables de entorno (`.env.example`). La API no guarda estado y puede replicarse
detrás del proxy.

Para la demostración en clase y las sesiones con especialistas se activa el recurso condicional de despliegue web
(decisión D-13), descrito como infraestructura en código en `render.yaml`:

| Entorno | Base de datos | API | Web | Actualización |
|---|---|---|---|---|
| Local (Docker Compose) | Contenedor PostGIS | Contenedor detrás de Nginx, mismo origen | Nginx con proxy inverso `/api` | `docker compose up -d --build` |
| Demostración (Render) | PostgreSQL gestionado con PostGIS | Mismo contenedor de solo lectura | Sitio estático en CDN; llama a la API por su dominio (CORS limitado al origen de la web) | Automática con cada push a `main` |

En ambos entornos los datos solo cambian mediante una publicación atómica con el rol publicador
(`tools/deploy/remote_setup.py` en la nube); un despliegue de código nunca altera los resultados. El
entrenamiento puede ejecutarse en CPU o en GPU (`requirements-gpu.txt`); la corrida publicada se entrena en CPU.

## 5. Patrones de diseño

| Patrón | Aplicación |
|---|---|
| Arquitectura en capas | API: router, esquema, servicio y repositorio |
| Repository y Service Layer | Acceso a datos y casos de uso separados |
| Data Transfer Object | Esquemas Pydantic de cada respuesta |
| Separación de lectura y escritura | El pipeline escribe con el rol publicador; la API lee con un rol de solo lectura |
| Tuberías y filtros | Etapas del pipeline con artefactos versionados |
| Publicación atómica con puntero activo | Una corrida se carga y concilia completa antes de activarse; la anterior queda disponible |
| Proxy inverso | Nginx sirve la aplicación y enruta la API |
| Estado único en el cliente | Contexto de React compartido por todas las vistas |

## 6. Atributos de calidad

| Atributo | Táctica | Medida |
|---|---|---|
| Reproducibilidad | Versiones fijadas, semilla, hilos fijos, hash, linaje del código | M-04 |
| Rendimiento | Resultados precalculados, índices GiST, consultas acotadas | M-09, p95 ≤ 2 s |
| Seguridad | Rol de solo lectura, sin rutas de escritura, parámetros validados, CORS limitado | Pruebas de contrato |
| Disponibilidad ante fallos | Error explícito sin corrida publicada o sin base de datos | Pruebas de contrato |
| Exactitud de lo servido | Conciliación de la publicación y contraste API frente a resultados exportados | M-08, M-02 |
| Usabilidad e interpretabilidad | Leyenda con valores y nombres, explicaciones por zona, manual | M-10 a M-12 |
| Modificabilidad | Contratos tipados, capas desacopladas, migraciones versionadas | Revisión de PR |

## 7. Modelo de datos

- **Geografía y tiempo:** `district`, `spatial_representation`, `spatial_unit` (celdas y distritos),
  `unit_district_relation` y `analysis_period`.
- **Procedencia:** `source_snapshot`, `dataset_version`, `variable`, `limitation`, `target_definition` y
  `threshold_set`.
- **Corridas y resultados:** `model_run` con sus relaciones de fuentes, variables, limitaciones y periodos, y
  `risk_result` con frecuencia, severidad, exposición y desglose (subtipo, severidad, vehículo, servicio y
  factores registrados).
- **Capas de análisis:** `corridor` (vías críticas, con vehículos y factores), `unit_explanation` (serie,
  atribución, simulación, Grad-CAM y perfil del entorno), `model_card` y `forecast` (pronóstico un paso
  adelante).
- **Publicación:** `publication_pointer` y `publication_log`.

Las migraciones están en `database/migrations`.

## 8. Roles del equipo frente a la arquitectura

| Rol | Contenedores y componentes |
|---|---|
| Backend Developer y QA | Pipeline (fusión, modelo, evaluación, explicaciones, publicación), API, base de datos y pruebas |
| Frontend Developer | Aplicación web, mapa, comparadores, vistas de análisis y explicación, pruebas de recorrido y validación con usuarios |
| Project Manager y Product Owner | Priorización, aceptación y control de cambios sobre contratos y alcance |
