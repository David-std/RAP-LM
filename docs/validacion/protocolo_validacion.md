# Protocolo de validación con usuarios especializados (paquete EDT 4.5)

**Requisitos y métricas:** RV-03, RNF-01, RF-07; M-10 (éxito de tareas), M-11 (reducción de tiempo frente a la
plataforma del ONSV), M-12 (interpretación correcta y utilidad).
**Responsables:** las sesiones las conduce el equipo (Product Owner y Backend Developer & QA como observador).
Este documento, las plantillas de `docs/validacion/` y el script `tools/validation/consolidate.py` son los
instrumentos; **no contienen resultados**.

## 1. Participantes

- Al menos cinco usuarios especializados: analistas de seguridad vial, analistas GIS, ingenieros de tránsito y
  coordinadores municipales de seguridad vial.
- Se registran el perfil (rol, años de experiencia, familiaridad con SIG) y el consentimiento verbal o escrito.
  No se registran nombres en los archivos del repositorio: cada participante recibe un código `P01`, `P02`…

## 2. Condiciones

- La misma computadora, el mismo navegador y la misma corrida publicada para todos. Se anota el `run_id` que
  aparece en la barra de estado.
- Procedimiento de referencia (M-11): las mismas tareas o tareas equivalentes en las plataformas públicas del
  ONSV (tablero de siniestralidad), con el mismo ámbito y periodo. Se alterna el orden (MVP primero o ONSV
  primero) entre participantes para controlar el aprendizaje: los participantes impares empiezan por el MVP.
- Se cronometra desde que se lee la tarea hasta que el participante declara la respuesta. Abandonos y bloqueos
  se registran: **no se eliminan intentos fallidos**.

## 3. Tareas críticas

| ID | Tarea | Resultado correcto (se completa antes de la sesión con la corrida usada) | Criterio de finalización |
|---|---|---|---|
| T1 | Identifique el distrito con mayor nivel de riesgo en días laborables de 18 a 24 h de 2024. | Primer distrito del ranking distrital de ese periodo. | Nombra el distrito. |
| T2 | Indique tres celdas de nivel alto en San Juan de Lurigancho en ese mismo periodo. | Cualquier celda con nivel alto y distrito 150132 en ese periodo. | Señala tres celdas válidas. |
| T3 | Compare Cercado de Lima y Miraflores en fines de semana de 0 a 6 h de 2023: ¿cuál tiene mayor índice y por cuántos puntos? | Diferencia de índice entre ambos distritos en ese periodo. | Responde el distrito y la diferencia (±2 puntos). |
| T4 | Para Ate, diga si el nivel cambió entre 2016 y 2024 en laborables de 6 a 12 h. | Niveles de ambos periodos. | Responde "subió", "bajó" o "igual", con los niveles. |
| T5 | Indique de qué fuentes proviene el resultado de una celda seleccionada y una limitación. | Fuentes y limitaciones del panel de procedencia. | Nombra al menos una fuente y una limitación válidas. |

En el procedimiento ONSV las tareas T1 a T4 se resuelven con los conteos del tablero. Si una tarea no puede
resolverse allí, se registra como "no realizable en la referencia" y no se cuenta en M-11.

## 4. Preguntas de interpretación (M-12, clave fijada antes de la sesión)

| ID | Pregunta | Respuesta correcta |
|---|---|---|
| Q1 | ¿El índice 85 significa 85 % de probabilidad de atropello? | No. Es una posición relativa (percentil) frente a la distribución de referencia. |
| Q2 | Una celda rayada (trama), ¿tiene riesgo bajo? | No. No tiene resultado; no equivale a bajo. |
| Q3 | ¿Qué diferencia hay entre "atropellos registrados" y el índice? | Los registrados son conteos observados; el índice es un valor estimado por el modelo. |
| Q4 | ¿A qué periodo corresponde lo que ve en el mapa? | El periodo activo: año, tipo de día y franja que muestra la barra de estado. |
| Q5 | ¿Puede comparar el índice de una celda con el de un distrito? | No. Son representaciones con escalas distintas. |
| Q6 | ¿La aplicación recomienda una intervención vial? | No. Es una referencia analítica; no recomienda intervenciones. |

## 5. Utilidad (M-12, escala 1 a 5)

Cinco afirmaciones de `formulario_utilidad.md`, cada una valorada de 1 (muy en desacuerdo) a 5 (muy de acuerdo).
Consolidación: promedio de todas las respuestas válidas; la meta es al menos 4.

## 6. Cálculo

- **M-10** = tareas completadas correctamente / tareas iniciadas (meta: 80 % o más y no inferior a la
  referencia). Las ausencias se registran aparte.
- **M-11** = (tiempo medio ONSV − tiempo medio MVP) / tiempo medio ONSV × 100, solo con tareas correctas en
  ambos procedimientos (meta: más de 0 % sin que baje M-10).
- **M-12a** = respuestas correctas / preguntas realizadas (meta: 80 % o más). **M-12b** = utilidad media (meta: 4 o
  más).

`python -m tools.validation.consolidate docs/validacion/registro_sesiones.csv docs/validacion/respuestas.csv`
escribe `evidence/validation/M-10_M-12.json`. Con cinco participantes la muestra es pequeña: los resultados
se presentan con sus denominadores y no se extrapolan a toda Lima.
