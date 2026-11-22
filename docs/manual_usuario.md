# Manual de usuario de RAP-LM

**Historia:** HU-29 (RNF-01). **Versión de la aplicación:** la de la rama que contiene este archivo. La corrida
publicada que se consulta aparece siempre en la barra de estado inferior.

RAP-LM permite consultar, comparar y exportar un **índice relativo de riesgo de atropello peatonal** (todas
las severidades) por celda de 1 km o por distrito, en los 43 distritos de la provincia de Lima, para cada
**periodo**: año, tipo de día (laborable o fin de semana) y franja horaria (0–6, 6–12, 12–18 o 18–24 h).
Es una referencia analítica: **no es una predicción en tiempo real ni recomienda intervenciones**.

## 1. Conceptos

| Término | Significado |
|---|---|
| Unidad espacial | Una celda de la malla de 1 km (código `F{fila}-C{columna}`) o un distrito (UBIGEO). Cada celda pertenece al distrito con mayor parte de su superficie. |
| Indicador estimado | Atropellos esperados por km² y año en esa franja, estimados por el modelo CNN-LSTM a partir de los años anteriores y el contexto urbano. |
| Índice (0 a 100) | Posición del indicador frente a la distribución de referencia: un índice de 85 significa que supera al 85 % de las celdas y periodos de referencia. **No es una probabilidad.** |
| Nivel | Bajo (menos de 40), medio (40 a 69) y alto (70 o más). Los umbrales se fijaron antes de evaluar el modelo y se ven en la leyenda. |
| Sin resultado (trama) | No hay estimación para esa unidad o periodo. **No equivale a riesgo bajo.** |
| Registro histórico | Atropellos, lesionados y fallecidos observados en las fuentes. Es una referencia de frecuencia, no el riesgo estimado. |
| Promedio histórico | Enfoque base de comparación: promedio de los años previos de la misma fuente, unidad y franja. |

## 2. Pantalla de mapa

1. **Periodo:** en el panel *Consulta* elija el año, el tipo de día y la franja. Solo aparecen los años con al menos
   una fuente (2011–2017 y 2021–2024). El mapa, el detalle y las comparaciones abiertas se actualizan juntos.
2. **Unidad de análisis:** alterne entre *Celda de 1 km* y *Distrito*. Los contornos negros son los límites
   distritales.
3. **Leyenda:** abajo a la izquierda. Seis tonos agrupados en tres niveles, con sus rangos numéricos. Se puede
   plegar.
4. **Navegación:** rueda o botones para acercar y alejar, arrastre para desplazarse y el botón ⤢ para volver a
   la vista completa de Lima. Con el mapa enfocado también funcionan las flechas del teclado y las teclas `+` y `-`.
5. **Información rápida:** al pasar el cursor por una unidad se ven su nombre, índice, nivel y periodo.
6. **Buscar:** escriba un código de celda (por ejemplo `F54-C35`) o parte del nombre de un distrito y pulse
   Enter.

## 3. Filtros

- **Nivel de riesgo:** marque uno o varios niveles. Las unidades que no cumplen el filtro se ven atenuadas. Los
  números indican cuántas unidades hay en cada nivel en el periodo activo.
- **Distrito:** limita la consulta a una jurisdicción.
- Los filtros activos se resumen en el panel; **Quitar filtros** restablece el conjunto completo.
- Abrir o cerrar el detalle no cambia el periodo ni los filtros.

## 4. Detalle de una unidad

Haga clic en una unidad. El panel derecho muestra:

- índice, nivel, periodo, tipo de unidad, indicador estimado, promedio histórico y posición en Lima;
- **perfil horario** del año: los ocho periodos (dos tipos de día por cuatro franjas). Un clic cambia el
  periodo activo;
- **registro histórico** del periodo: atropellos registrados y peatones lesionados y fallecidos;
- **procedencia**: fuentes que observan ese periodo, partición del modelo (entrenamiento, validación o
  prueba), corrida, dataset, variables por grupo (ocurrencia, severidad, exposición y contexto) y limitaciones.

La barra inferior **Evolución temporal** muestra el índice de la unidad en todos los años para el mismo tipo
de día y franja.

## 5. Comparar

- **Zonas en un periodo:** agregue de 2 a 4 zonas haciendo clic en el mapa (o con *Añadir distrito*). Todas usan
  el periodo activo, la misma corrida y la misma escala. La tabla muestra índice, nivel, diferencia con la zona
  A, promedio histórico y atropellos registrados. Use × para quitar una zona.
- **Zona entre periodos:** elija una zona y dos periodos (A y B). Los dos mapas muestran la misma geometría. Se
  muestran la variación y la serie de años, que no une 2017 con 2021 porque no hay fuente entre 2018 y 2020.
- No se pueden comparar celdas con distritos: usan escalas distintas.

## 6. Análisis

| Herramienta | Para qué sirve |
|---|---|
| Ranking | Ordenar todas las unidades del periodo por índice, indicador, promedio histórico o atropellos registrados. Respeta los filtros del mapa. |
| Cambio | Ver qué unidades subieron o bajaron entre dos periodos (rojo sube, azul baja) y cuántas cambiaron de nivel. |
| Persistencia | Cuántos años estuvo cada unidad en nivel alto para un mismo tipo de día y franja. |
| Distritos | Índice distrital y cuántas de sus celdas están en cada nivel. |

**Exportar:** *Exportar CSV* (abre en Excel) y *Exportar GeoJSON* (abre en QGIS o ArcGIS) descargan lo que se ve.
Cada archivo incluye la corrida, el dataset, el periodo y el aviso de alcance. Las celdas vacías significan sin
resultado, no cero.

**Compartir:** la dirección del navegador guarda el periodo, la vista, los filtros y la unidad seleccionada.
Copie el enlace para que otra persona vea la misma consulta.

## 7. Metodología y fuentes

Explica qué representa el índice, cómo se obtiene, la evaluación frente al promedio histórico y a modelos de la
literatura, las fuentes (incluidas las no incorporadas y por qué), las variables y las limitaciones.

## 8. Buenas prácticas de interpretación

- Compare zonas siempre en el mismo periodo, o una zona consigo misma entre periodos.
- Un nivel alto indica dónde se concentra el riesgo relativo, no una causa ni la intervención que corresponde.
- Revise la procedencia antes de usar un resultado: 2021–2024 se observa solo con siniestros fatales (ONSV) y
  el modelo los vincula al conjunto de atropellos; 2011–2017 proviene del censo de comisarías.
- Una celda con trama no tiene resultado: no la interprete como zona segura.
