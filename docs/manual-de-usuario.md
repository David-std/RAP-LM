# Manual de usuario de RAP-LM

**Historia:** HU-29 (RNF-01). **Versión de la aplicación:** v1.1.1. La versión del modelo aparece en la barra
superior (con el enlace *Código* al repositorio) y el dataset y la corrida completa, en la barra de estado.

**Navegación.** Las vistas de trabajo (*Mapa de riesgo*, *Pronóstico*, *Vías críticas*, *Comparar*, *Análisis*)
van a la izquierda; la documentación (*Modelo*, *Metodología y fuentes*) queda separada a la derecha. El nombre
RAP-LM vuelve al mapa. Cada opción o medida que no se explica sola tiene un botón **?**: se abre al pasar el
cursor, con el teclado o con un clic, y se cierra con Escape. Los textos secundarios se abren con su título
(*Cómo se obtiene*, *Cómo se calcula la tasa*, *Cómo leerlo*, *Procedencia y limitaciones*).

RAP-LM permite consultar, comparar, analizar y exportar el **riesgo relativo de atropello peatonal** (todas las
severidades y subtipos) en los 43 distritos de la provincia de Lima, por celda de 1 km, por distrito y por calle,
para cada **periodo**: año, tipo de día (laborable o fin de semana) y franja horaria (0 a 6, 6 a 12, 12 a 18 o 18
a 24 h). Es una referencia analítica para especialistas: **no es una predicción en tiempo real ni recomienda
intervenciones**.

## 1. Conceptos

| Término | Significado |
|---|---|
| Ámbito | Provincia de Lima, 43 distritos (UBIGEO 1501xx). En el mapa, lo que queda fuera (Callao y las otras provincias del departamento de Lima) se ve atenuado. |
| Unidad espacial | Una celda de la malla de 1 km (código `F{fila}-C{columna}`), un distrito o un tramo de calle (una calle dentro de un distrito). |
| Frecuencia | Indicador principal: atropellos esperados por km² y año en esa franja, estimados por la red CNN-RNN con los años anteriores y el contexto urbano. Es el índice que colorea el mapa. |
| Severidad esperada | Frecuencia × probabilidad de desenlace fatal de la zona. Señala dónde las consecuencias suelen ser más graves. |
| Frente al contexto | Razón entre la frecuencia estimada y la que predice un modelo estadístico solo con variables de contexto (población, comercio, transporte, veredas, vías arteriales). 1× = lo que predice el contexto; 2× = el doble. **No es una tasa por peatón expuesto**: Lima no tiene conteos de peatones, y la razón no indica causa. |
| Índice (0 a 100) | Posición del indicador frente a la distribución de referencia: 85 significa que supera al 85 % de las celdas y franjas de referencia. **No es una probabilidad.** |
| Nivel | Bajo (menos de 40), medio (40 a 69) y alto (70 o más). Umbrales fijados antes de evaluar el modelo. |
| Sin resultado (trama) | No hay estimación para esa unidad o periodo. **No equivale a riesgo bajo.** |
| Registro histórico | Atropellos registrados en las fuentes, con su desglose por subtipo (atropello, atropello y fuga, choque y atropello, otro) por severidad (con fallecido, con lesionados, solo daños, sin dato), por vehículo involucrado, por servicio de transporte (público, particular, carga) y por los factores que registró la policía. Es frecuencia observada, no el riesgo estimado. |
| Factores registrados | Causas que la policía anota después de cada atropello: exceso de velocidad, ebriedad del conductor o del peatón, conducta del conductor o del peatón, señalización defectuosa, falta de iluminación, vía en mal estado, falla o carga del vehículo, clima. Un atropello puede tener varios. **Describen el registro; no entran a la estimación de la red**, porque solo existen después del hecho. |
| Entorno de la zona | Condiciones previas que lee la red (semáforos y cruces por km de vía, veredas, vías arteriales, comercio, centros educativos y de salud, paraderos, población) comparadas con el resto de Lima: bajo (cuarto inferior), medio o alto (cuarto superior). |
| Promedio histórico | Enfoque base de comparación: promedio de los años previos de la misma fuente, unidad y franja. |

## 2. Mapa de riesgo

1. **Vista:** *Malla 1 km* muestra las celdas con las que trabaja la red; *Distritos*, los valores agregados de
   los 43 distritos; *Calor*, una superficie continua. En la vista de calor basta pasar el cursor por cualquier
   punto para leer los valores de la celda de 1 km que lo contiene, y un clic abre su panel.
2. **Qué mostrar:** *Riesgo estimado* (índice de la red CNN-RNN), *Atropellos registrados* (densidad por km² en
   las fuentes, con su propia escala) o *Grad-CAM* (qué zonas pesan en la estimación de la zona seleccionada;
   disponible para los distritos y para las celdas de mayor riesgo de 2024).
3. **Periodo:** elija el año en la lista o avance con las flechas, el tipo de día y la franja. Solo aparecen años
   con alguna fuente (2011 a 2017 y 2021 a 2024). Todas las vistas usan el mismo periodo.
4. **Filtros:** active uno o más chips de nivel (alto, medio, bajo; cada uno indica cuántas zonas tiene) o escriba
   un distrito. Las unidades fuera del filtro se atenúan y un resumen indica lo que se muestra; *Quitar filtros*
   restablece el conjunto completo. Abrir o cerrar una zona no cambia los filtros.
5. **Ir a una zona:** arriba del panel izquierdo; escriba un código de celda (por ejemplo `F54-C35`) o parte del
   nombre de un distrito y pulse *Ir*.
6. **Pasar el cursor:** en *Riesgo estimado* muestra el índice y su nivel, el valor esperado, si la estimación
   sube o baja frente al año anterior y la diferencia con el promedio histórico; en *Atropellos registrados*, los
   registros con su severidad y los peatones afectados; en *Grad-CAM*, la influencia de la celda y su posición.
7. **Navegar:** rueda o botones para acercar, arrastre para desplazarse, botón ⤢ para volver a toda Lima.
8. **Leyenda:** abajo a la izquierda, con rangos numéricos y nombres de nivel (no depende solo del color).

### Panel de zona

Sin zona elegida, el panel derecho resume el periodo: cuántas zonas hay en cada nivel y las de mayor riesgo; un
clic en una de ellas la selecciona. Al hacer clic en una celda o distrito, el panel muestra sus secciones:

| Tarjeta | Qué responde |
|---|---|
| Riesgo estimado | Tabla con el índice y el valor de frecuencia, severidad y razón frente al contexto; barra de posición en la escala y diferencia frente al promedio histórico. |
| La red año a año | Atropellos que la red esperaba registrar frente a los registrados, año por año. Muestra cómo la parte recurrente sigue la evolución; clic en un año para cambiar el periodo. |
| Perfil horario | Índice en las ocho combinaciones de tipo de día y franja del año activo; clic para cambiar de franja. |
| Registro histórico | Total del periodo con desglose por subtipo, severidad, vehículo, servicio de transporte y factores registrados; lesionados y fallecidos. |
| Entorno de la zona | Cada indicador del entorno con su valor y su posición en Lima (bajo, medio, alto), por ejemplo pocos semáforos por km de vía. Describe el entorno; no recomienda intervenciones. |
| Qué impulsa la estimación | Cuánto cambia la estimación si cada grupo de variables (población, transporte, comercio, infraestructura peatonal, vías arteriales, atropellos del año previo) se reemplaza por el promedio de Lima. Rojo eleva, petróleo reduce. Es asociación del modelo, no causalidad. |
| Influencia (Grad-CAM) | Con la capa Grad-CAM del mapa, qué celdas pesan en la estimación de la zona elegida (la más influyente vale 100 %). Disponible para los 43 distritos y las 400 celdas de mayor riesgo de 2024. |
| Simular contexto del distrito | Elija una variable y mueva el control (de 0 a 2 veces su valor actual): se muestra cómo cambia el riesgo estimado del distrito. Los escenarios se calcularon fuera de línea; no son recomendaciones. |
| Calles con más atropellos | Las cinco calles del distrito con más eventos registrados; *Ver vías críticas* abre la vista de calles. |
| Procedencia y limitaciones | Corrida, dataset, fuentes del periodo y limitaciones. Cada sección indica también su fuente. |

## 3. Pronóstico

La vista *Pronóstico* permite elegir 2025, 2026 o 2027, por distrito o celda, tipo de día y franja.
El modelo v5 se entrenó con todos los años observados (hasta 2024) y el contexto queda fijo en 2024; 2026 y 2027
usan las proyecciones previas como entrada. La tabla compara cada horizonte con el año inmediatamente anterior.
El rango muestra el mínimo y máximo entre los cinco miembros del ensamble, no un intervalo de confianza.
Los atropellos esperados están en la escala de registro del censo de comisarías: no son el total real de Lima.

El bloque *Fiabilidad* resume la evaluación fuera de muestra: primero todas las severidades (CENACOM 2017) y
luego los siniestros fatales (ONSV 2024), además del ensayo a tres años con años conocidos (2021 a 2024), en el
que la red mantuvo su ventaja sobre el promedio histórico. No existe validación observada de 2026 y 2027.
Es un insumo de planificación, no una alerta en tiempo real.

## 4. Vías críticas

Vista a nivel de calle, en la línea de las redes de alto riesgo de los programas Visión Cero:

- el mapa dibuja cada calle con grosor y color según sus atropellos por km;
- el ranking ordena las calles por densidad; clic en una calle para ver sus atropellos por año, cuándo ocurren
  (tipo de día y franja), lesionados, fallecidos, fuentes y el riesgo modelado medio de las celdas que cruza;
- la curva de concentración muestra qué parte de los atropellos ubicados se acumula en una pequeña parte de la
  longitud de calles;
- el detalle de cada calle incluye los vehículos involucrados y los factores registrados más frecuentes;
- *Exportar CSV* descarga el ranking.

Un cruce reparte medio evento a cada una de sus calles; las avenidas de doble calzada suman ambas vías en su
longitud. Es registro histórico, no predicción.

## 5. Comparar

- **Zonas en un periodo:** agregue de 2 a 4 zonas (clic en el mapa o *Añadir distrito*). Todas usan el periodo
  activo, la misma corrida y la misma escala. La tabla muestra índice, nivel, diferencia con la zona A, promedio
  histórico y registro.
- **Zona entre periodos:** elija una zona y dos periodos (A y B); los dos mapas muestran la misma geometría. Se ven
  la variación y la serie de años (sin unir 2017 con 2021, porque 2018 a 2020 no tienen fuente).
- Celdas y distritos no se comparan entre sí: usan escalas distintas.

## 6. Análisis

| Herramienta | Para qué sirve |
|---|---|
| Ranking | Ordenar todas las unidades del periodo por índice, indicador, promedio histórico o registro. Respeta los filtros del mapa. |
| Cambio | Qué unidades subieron o bajaron entre dos periodos y cuántas cambiaron de nivel. |
| Persistencia | Cuántos años estuvo cada unidad en nivel alto para un mismo tipo de día y franja. |
| Distritos | Índice distrital y cuántas de sus celdas están en cada nivel. |

*Exportar CSV* (Excel) y *Exportar GeoJSON* (QGIS o ArcGIS) descargan lo que se ve, con corrida, dataset, periodo
y aviso de alcance. Las celdas vacías significan sin resultado, no cero. La dirección del navegador guarda periodo,
vista, filtros y unidad seleccionada: copie el enlace para compartir la misma consulta.

## 7. Modelo

Documento técnico con índice lateral y secciones numeradas. Cada tabla y figura indica el archivo del repositorio
del que proviene, y al final hay referencias académicas:

- resumen con la priorización de celdas en los años de prueba;
- datos y años con que entrena la versión publicada (v5 usa todos los años observados, por eso sus valores
  2011 a 2024 son reconstrucciones; la evaluación proviene de redes entrenadas sin el año evaluado);
- arquitectura (entrada, ConvLSTM, cabeza y operador de observación), configuración y curva de entrenamiento;
- evaluación fuera de muestra frente al promedio histórico: precisión promedio (medida principal de M-05 según
  D-17), AUC, captura en el 10 y 20 % de celdas, estrato de ubicación precisa, error por distrito y correlación
  de rangos, incluidas las medidas desfavorables;
- pronóstico a uno, dos y tres años con años conocidos, y ablación de cada componente;
- cómo se explica la red (Grad-CAM, atribución por grupos y simulación de contexto), variables de entrada y
  reproducibilidad (commit, huella SHA-256 de los pesos y M-04).

## 8. Metodología y fuentes

Documento técnico con lo que muestra el mapa, la lectura de los niveles, el proceso (cada paso enlaza al
código que lo implementa), las fuentes incorporadas y las evaluadas no incorporadas con su motivo, las variables
por grupo con su periodo de referencia y las limitaciones.

## 9. Buenas prácticas de interpretación

- Compare zonas en el mismo periodo, o una zona consigo misma entre periodos.
- Un nivel alto indica dónde se concentra el riesgo relativo, no su causa ni la intervención que corresponde.
- Use los tres componentes juntos: una zona con frecuencia media pero severidad alta o muy por encima de lo que predice su contexto
  merece atención distinta de una con muchos atropellos leves en una zona muy transitada.
- Revise la procedencia: 2021 a 2024 se observa solo con siniestros fatales (ONSV) y el modelo los vincula al
  conjunto de atropellos; 2011 a 2017 proviene del censo de comisarías, de todas las severidades.
- La exposición se representa con proxies (no hay aforos peatonales públicos para los 43 distritos).
- Una celda con trama no tiene resultado: no la interprete como zona segura.
