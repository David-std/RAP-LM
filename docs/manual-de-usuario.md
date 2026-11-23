# Manual de usuario de RAP-LM

**Historia:** HU-29 (RNF-01). **Versión de la aplicación:** la de la rama que contiene este archivo. La corrida
publicada que se consulta aparece en la barra superior y en la barra de estado.

RAP-LM permite consultar, comparar, analizar y exportar el **riesgo relativo de atropello peatonal** (todas las
severidades y subtipos) en los 43 distritos de la provincia de Lima, por celda de 1 km, por distrito y por calle,
para cada **periodo**: año, tipo de día (laborable o fin de semana) y franja horaria (0 a 6, 6 a 12, 12 a 18 o 18
a 24 h). Es una referencia analítica para especialistas: **no es una predicción en tiempo real ni recomienda
intervenciones**.

## 1. Conceptos

| Término | Significado |
|---|---|
| Ámbito | Provincia de Lima, 43 distritos (UBIGEO 1501xx). En el mapa, lo que queda fuera (Callao y las otras provincias del departamento de Lima) se ve atenuado. |
| Unidad espacial | Una celda de la malla de 1 km (código `F{fila}-C{columna}`), un distrito o un corredor (una calle dentro de un distrito). |
| Frecuencia | Indicador principal: atropellos esperados por km² y año en esa franja, estimados por la red CNN-RNN con los años anteriores y el contexto urbano. Es el índice que colorea el mapa. |
| Severidad esperada | Frecuencia × probabilidad de desenlace fatal de la zona. Señala dónde las consecuencias suelen ser más graves. |
| Riesgo por exposición | Razón entre la frecuencia estimada y la que explicaría solo la exposición (población, comercio, transporte, veredas, vías arteriales). 1× = lo esperado por la exposición; 2× = el doble. |
| Índice (0 a 100) | Posición del indicador frente a la distribución de referencia: 85 significa que supera al 85 % de las celdas y franjas de referencia. **No es una probabilidad.** |
| Nivel | Bajo (menos de 40), medio (40 a 69) y alto (70 o más). Umbrales fijados antes de evaluar el modelo. |
| Sin resultado (trama) | No hay estimación para esa unidad o periodo. **No equivale a riesgo bajo.** |
| Registro histórico | Atropellos registrados en las fuentes, con su desglose por subtipo (atropello, atropello y fuga, choque y atropello, otro) y por severidad (con fallecido, con lesionados, solo daños, sin dato). Es frecuencia observada, no el riesgo estimado. |
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
5. **Ir a una zona:** escriba un código de celda (por ejemplo `F54-C35`) o parte del nombre de un distrito.
6. **Navegar:** rueda o botones para acercar, arrastre para desplazarse, botón ⤢ para volver a toda Lima.
7. **Leyenda:** abajo a la izquierda, con rangos numéricos y nombres de nivel (no depende solo del color).

### Panel de zona

Al hacer clic en una celda o distrito, el panel derecho muestra tarjetas:

| Tarjeta | Qué responde |
|---|---|
| Riesgo estimado | Nivel, índice de frecuencia, severidad esperada y riesgo por exposición; posición en Lima y diferencia frente al promedio histórico. |
| La red año a año | Atropellos que la red esperaba registrar frente a los registrados, año por año. Muestra cómo la parte recurrente sigue la evolución; clic en un año para cambiar el periodo. |
| Perfil horario | Índice en las ocho combinaciones de tipo de día y franja del año activo; clic para cambiar de franja. |
| Registro histórico | Total del periodo con desglose por subtipo y por severidad, lesionados y fallecidos. |
| Qué impulsa la estimación | Cuánto cambia la estimación si se retira cada grupo de variables (población, transporte, comercio, infraestructura peatonal, vías arteriales, atropellos del año previo). Rojo eleva, petróleo reduce. Es asociación del modelo, no causalidad. |
| Simular contexto del distrito | Elija una variable y mueva el control (de 0 a 2 veces su valor actual): se muestra cómo cambia el riesgo estimado del distrito. Los escenarios se calcularon fuera de línea; no son recomendaciones. |
| Calles con más atropellos | Las cinco calles del distrito con más eventos registrados; *Ver corredores* abre la vista de calles. |
| Procedencia y limitaciones | Corrida, dataset, fuentes del periodo y limitaciones. |

## 3. Corredores

Vista a nivel de calle, en la línea de las redes de alto riesgo de los programas Visión Cero:

- el mapa dibuja cada calle con grosor y color según sus atropellos por km;
- el ranking ordena las calles por densidad; clic en una calle para ver sus atropellos por año, cuándo ocurren
  (tipo de día y franja), lesionados, fallecidos, fuentes y el riesgo modelado medio de las celdas que cruza;
- la curva de concentración muestra qué parte de los atropellos ubicados se acumula en una pequeña parte de la
  longitud de calles;
- *Exportar CSV* descarga el ranking.

Un cruce reparte medio evento a cada una de sus calles; las avenidas de doble calzada suman ambas vías en su
longitud. Es registro histórico, no predicción.

## 4. Comparar

- **Zonas en un periodo:** agregue de 2 a 4 zonas (clic en el mapa o *Añadir distrito*). Todas usan el periodo
  activo, la misma corrida y la misma escala. La tabla muestra índice, nivel, diferencia con la zona A, promedio
  histórico y registro.
- **Zona entre periodos:** elija una zona y dos periodos (A y B); los dos mapas muestran la misma geometría. Se ven
  la variación y la serie de años (sin unir 2017 con 2021, porque 2018 a 2020 no tienen fuente).
- Celdas y distritos no se comparan entre sí: usan escalas distintas.

## 5. Análisis

| Herramienta | Para qué sirve |
|---|---|
| Ranking | Ordenar todas las unidades del periodo por índice, indicador, promedio histórico o registro. Respeta los filtros del mapa. |
| Cambio | Qué unidades subieron o bajaron entre dos periodos y cuántas cambiaron de nivel. |
| Persistencia | Cuántos años estuvo cada unidad en nivel alto para un mismo tipo de día y franja. |
| Distritos | Índice distrital y cuántas de sus celdas están en cada nivel. |

*Exportar CSV* (Excel) y *Exportar GeoJSON* (QGIS o ArcGIS) descargan lo que se ve, con corrida, dataset, periodo
y aviso de alcance. Las celdas vacías significan sin resultado, no cero. La dirección del navegador guarda periodo,
vista, filtros y unidad seleccionada: copie el enlace para compartir la misma consulta.

## 6. Modelo

Muestra cómo está construida y cómo se evaluó la red publicada:

- arquitectura (entrada, parte espacial, parte temporal, salida y vínculo con cada fuente);
- particiones de entrenamiento, validación y prueba por año y fuente;
- curvas de entrenamiento por época;
- benchmark en la prueba independiente frente al promedio histórico y otras arquitecturas, con la mejora relativa
  (M-05);
- errores del nivel alto: zonas críticas detectadas, falsos negativos y falsos positivos del modelo y del promedio
  histórico;
- búsqueda de configuración, variables de entrada, ficha técnica y huella SHA-256 de los pesos.

## 7. Metodología y fuentes

Qué representa cada componente, cómo se obtiene, las fuentes (incluidas las no incorporadas y por qué), las
variables por grupo (ocurrencia, severidad, exposición y contexto) y las limitaciones.

## 8. Buenas prácticas de interpretación

- Compare zonas en el mismo periodo, o una zona consigo misma entre periodos.
- Un nivel alto indica dónde se concentra el riesgo relativo, no su causa ni la intervención que corresponde.
- Use los tres componentes juntos: una zona con frecuencia media pero severidad alta o riesgo por exposición alto
  merece atención distinta de una con muchos atropellos leves en una zona muy transitada.
- Revise la procedencia: 2021 a 2024 se observa solo con siniestros fatales (ONSV) y el modelo los vincula al
  conjunto de atropellos; 2011 a 2017 proviene del censo de comisarías, de todas las severidades.
- La exposición se representa con proxies (no hay aforos peatonales públicos para los 43 distritos).
- Una celda con trama no tiene resultado: no la interprete como zona segura.
