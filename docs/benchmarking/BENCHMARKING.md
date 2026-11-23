# Benchmarking RAP-LM

Universidad Peruana de Ciencias Aplicadas, SI727 Gerencia de Proyectos en Computación, Grupo 06.
Elaboración propia a partir de las corridas registradas del proyecto (datos, métricas y reproducibilidad).

## 1. Introducción

Los productos oficiales disponibles (ONSV, estadísticas INEI y MTC) permiten saber dónde y cuántos siniestros ocurrieron, pero no comparan el **riesgo** de atropello entre zonas y periodos: no relacionan la ocurrencia con la severidad, la exposición y el entorno, y agregan a escalas que ocultan diferencias internas (causas C1 a C3 del plan v1.6, con base en Guo et al., 2024 y Hu et al., 2024). Este benchmark compara, con datos reales de Lima y bajo un protocolo preregistrado, las alternativas de tres componentes del producto.

## 2. Objetivo del benchmarking

Seleccionar con evidencia medida: (1) el modelo espaciotemporal que estima el riesgo, (2) la unidad espacial de análisis y (3) la estrategia para ubicar los eventos sin coordenadas. Tipo de benchmarking: **modelos y técnicas** (componente 1 y 3) y **representación de datos** (componente 2).

## 3. Benchmarking del modelo espaciotemporal

### 3.1. Propuestas

| Propuesta | Descripción | Fuente |
|---|---|---|
| Promedio histórico (B0) | Media de los años previos de la misma fuente, unidad y franja. Enfoque base del plan (OE4-I1). | Plan v1.6 |
| GLM de Poisson | Regresión log-lineal de conteos sobre las mismas variables; modelo clásico en seguridad vial. | Práctica estándar de modelos de frecuencia de siniestros |
| ConvLSTM | Celda recurrente con compuertas convolucionales; base de Hetero-ConvLSTM para riesgo de accidentes en malla. | Shi et al. (2015); Yuan, Zhou y Yang (2018) |
| CNN-LSTM | CNN por año (vecindario 5 × 5 km) y LSTM por celda sobre la secuencia de años. Arquitectura de referencia del plan. | Plan v1.6; Guo et al. (2024) |
| Ablaciones | Solo CNN (sin recurrencia) y solo LSTM (sin contexto espacial) para medir el aporte de cada parte. | Diseño experimental propio |

### 3.2. Criterios y parámetros de medición

| # | Criterio | Medida | Mejor |
|---|---|---|---|
| 1 | Error de frecuencia (M-05) | MAE de atropellos por distrito × franja en el año de prueba (E) | menor |
| 2 | Ajuste probabilístico | Devianza de Poisson por celda | menor |
| 3 | Detección de zonas críticas | Recall del nivel alto (falsos negativos) | mayor |
| 4 | Precisión de las alertas | Precisión del nivel alto (falsos positivos) | mayor |
| 5 | Concentración | % de eventos en el 10 % de celdas con mayor estimación | mayor |
| 6 | Reproducibilidad (M-04) | Valores idénticos al reentrenar con la misma semilla y código | 100 % |
| 7 | Cumplimiento de la arquitectura | Componente espacial (RM-02) y temporal (RM-03) | requerido |

Protocolo: partición cronológica; la selección usa solo el conjunto de validación y la prueba se evalúa una vez para todas las alternativas. La iteración v2 se registró antes de su entrenamiento.

### 3.3. Comparación de propuestas

**Iteración v1, corrida principal** (prueba ONSV 2024, 233 eventos)

| Alternativa | E prueba (MAE distrito × franja) | M-05 frente a B0 | Devianza por celda | Captura 10 % de celdas |
|---|---|---|---|---|
| Promedio histórico (B0) | 0.607 | (referencia) | 0.1156 | 62.1 % |
| CNN-LSTM | 0.597 | +1.65 % | 0.0671 | 58.9 % |
| ConvLSTM (seleccionada) | 0.583 | +3.85 % | 0.0655 | 60.3 % |
| Solo CNN (ablación) | 0.619 | -2.09 % | 0.0655 | 61.2 % |
| Solo LSTM (ablación) | 0.601 | +0.92 % | 0.0651 | 62.1 % |
| GLM de Poisson | 0.562 | +7.35 % | 0.0666 | 60.7 % |

Nivel alto (23192 celdas × franjas, 216 altas observadas):

| Enfoque | Detectadas | Falsos negativos | Falsos positivos | Recall | Precisión |
|---|---|---|---|---|---|
| Modelo | 175 | 41 | 4064 | 81.0 % | 4.1 % |
| Promedio histórico | 34 | 182 | 491 | 15.7 % | 6.5 % |

**Iteración v1, backtest de todas las severidades** (prueba CENACOM 2017, 1629 eventos)

| Alternativa | E prueba (MAE distrito × franja) | M-05 frente a B0 | Devianza por celda | Captura 10 % de celdas |
|---|---|---|---|---|
| Promedio histórico (B0) | 2.380 | (referencia) | 0.0981 | 79.9 % |
| CNN-LSTM (seleccionada) | 2.530 | -6.29 % | 0.0892 | 79.1 % |
| ConvLSTM | 2.449 | -2.90 % | 0.0900 | 78.8 % |
| Solo CNN (ablación) | 3.178 | -33.53 % | 0.1129 | 76.2 % |
| Solo LSTM (ablación) | 2.567 | -7.87 % | 0.0882 | 79.7 % |
| GLM de Poisson | 2.615 | -9.89 % | 0.0933 | 76.7 % |

Nivel alto (23192 celdas × franjas, 2306 altas observadas):

| Enfoque | Detectadas | Falsos negativos | Falsos positivos | Recall | Precisión |
|---|---|---|---|---|---|
| Modelo | 2219 | 87 | 4566 | 96.2 % | 32.7 % |
| Promedio histórico | 2081 | 225 | 3126 | 90.2 % | 40.0 % |

**Iteración v2 (dataset v1.1, búsqueda y ensamble), corrida principal** (prueba ONSV 2024, 233 eventos)

| Alternativa | E prueba (MAE distrito × franja) | M-05 frente a B0 | Devianza por celda | Captura 10 % de celdas |
|---|---|---|---|---|
| Promedio histórico (B0) | 0.607 | (referencia) | 0.1156 | 62.1 % |
| ConvLSTM, ensamble de 5 (h=32, dropout=0.1, lr=0.01) | 0.580 | +4.39 % | 0.0659 | 66.1 % |

Nivel alto (23192 celdas × franjas, 216 altas observadas):

| Enfoque | Detectadas | Falsos negativos | Falsos positivos | Recall | Precisión |
|---|---|---|---|---|---|
| Modelo | 186 | 30 | 4227 | 86.1 % | 4.2 % |
| Promedio histórico | 34 | 182 | 491 | 15.7 % | 6.5 % |

**Iteración v2, backtest de todas las severidades** (prueba CENACOM 2017, 1629 eventos)

| Alternativa | E prueba (MAE distrito × franja) | M-05 frente a B0 | Devianza por celda | Captura 10 % de celdas |
|---|---|---|---|---|
| Promedio histórico (B0) | 2.380 | (referencia) | 0.0981 | 79.9 % |
| CNN-LSTM, ensamble de 5 (h=16, dropout=0.3, lr=0.01) | 2.466 | -3.63 % | 0.0882 | 79.4 % |

Nivel alto (23192 celdas × franjas, 2299 altas observadas):

| Enfoque | Detectadas | Falsos negativos | Falsos positivos | Recall | Precisión |
|---|---|---|---|---|---|
| Modelo | 2210 | 89 | 4557 | 96.1 % | 32.7 % |
| Promedio histórico | 2051 | 248 | 3056 | 89.2 % | 40.2 % |

Reproducibilidad (M-04): 258896/258896 valores dentro de la tolerancia (100.0 %), coincidencia de unidad, periodo y nivel 100.0 %.

### 3.4. Análisis de alternativas

- En la medida principal E por distrito, el GLM de Poisson y el promedio histórico son competidores fuertes: con series cortas (pocos años por fuente) un modelo simple estima bien los totales agregados.
- Las redes CNN-RNN reducen la devianza por celda frente al promedio histórico y **detectan muchas más unidades de nivel alto realmente observadas** (menos falsos negativos), a costa de más falsos positivos. En seguridad vial, no marcar una zona crítica suele ser el error más costoso.
- Las ablaciones muestran el aporte de cada parte: sin recurrencia (solo CNN) el error empeora; la secuencia temporal aporta información.

### 3.5. Selección

Se publica el candidato CNN-RNN con menor error de validación, como exige el plan (la arquitectura comprometida es CNN-RNN). El GLM y el promedio histórico quedan como referencia permanente en la vista *Modelo* de la aplicación.

## 4. Benchmarking de la unidad espacial

### 4.1. Propuestas y criterios

Propuestas: distrito (43), malla de 2 km, malla de 1 km y corredor vial (calle dentro de un distrito; Hu et al., 2024 reportan mejor ajuste a nivel de segmento vial). Criterios: número de unidades, eventos asignables, proporción de unidad-periodo sin eventos (dispersión), eventos por unidad-periodo no vacía y capacidad de mostrar diferencias internas.

### 4.2. Comparación

Periodos: 88 (año × tipo de día × franja). Eventos fusionados: 14158.

| Unidad | Unidades | Eventos asignables | Unidad-periodo sin eventos | Eventos por unidad-periodo no vacía |
|---|---|---|---|---|
| Distrito (43) | 43 | 100.0 % | 37.1 % | 5.95 |
| Malla 2 km | 782 | 63.8 % | 86.1 % | 0.94 |
| Malla 1 km | 2899 | 63.8 % | 91.97 % | 0.44 |
| Corredor vial (calle × distrito) | 2365 | 63.6 % | n/a | n/a |

Concentración: 10 % de la longitud reúne 41.8 % de los eventos ubicados.

### 4.3. Análisis y selección

El distrito es denso pero oculta diferencias internas (causa C3). La malla de 1 km es muy dispersa, pero es la resolución mínima que conserva la estructura urbana para la CNN y coincide con el prototipo validado. Se selecciona una **combinación**: malla de 1 km para el modelo, corredor vial para la precisión de calle y distrito para la gestión (agregando intensidades, nunca etiquetas).

## 5. Benchmarking de la ubicación de eventos sin coordenadas

### 5.1. Propuestas y criterios

Propuestas: (a) usar solo eventos con coordenadas (ONSV), (b) asignar todo al distrito, (c) reglas de coincidencia con calles de OpenStreetMap dentro del distrito declarado (cruce = punto, calle = reparto por longitud, sin coincidencia = distrito), (d) geocodificador externo en línea. Criterios: cobertura de eventos ubicados, precisión espacial, reproducibilidad sin conexión, coordenadas inventadas (deben ser cero) y licencia de uso.

### 5.2. Comparación

| Propuesta | Eventos ubicados bajo distrito | Precisión | Reproducible sin conexión | Coordenadas inventadas |
|---|---|---|---|---|
| (a) Solo coordenadas ONSV | 817 de 14158 (5.8 %) | punto | sí | 0 |
| (b) Solo distrito | 0 (14158 a distrito) | distrito | sí | 0 |
| (c) Reglas con calles OSM (seleccionada) | 9028 de 14158 (63.8 %): 1024 cruces, 7187 tramos, 817 puntos | cruce o tramo | sí | 0 |
| (d) Geocodificador en línea | no ejecutado | variable | no (servicio externo, límites de uso) | posibles |

Registros leídos de las fuentes: 14362. Las exclusiones (cohorte no comparable, año incompleto, fecha u hora inválida) se registran con su motivo.

### 5.3. Selección

Se selecciona (c): multiplica por más de diez la cobertura ubicada frente a (a), es reproducible sin conexión y no inventa coordenadas. Su limitación (L03) queda declarada: los números de cuadra no se convierten y una calle se reparte por su longitud dentro del distrito.

## 6. Conclusiones

1. La red CNN-RNN aporta principalmente en **detectar zonas y franjas de riesgo alto** (recall) y en el ajuste por celda; en el total por distrito, los modelos simples siguen siendo competitivos, lo que se reporta sin ocultarlo.
2. La fusión de fuentes y la ubicación por calles permiten pasar de 817 eventos con coordenadas a más de nueve mil ubicados bajo el nivel de distrito, de todas las severidades.
3. La combinación malla + corredor + distrito responde a la causa C3 del plan sin perder comparabilidad.
4. El proceso es reproducible: al reentrenar con la misma configuración se obtienen los mismos valores (M-04).

## 7. Referencias

- Guo et al. (2024) y Hu et al. (2024): referencias completas en el informe del proyecto v1.6.
- Hochreiter, S., y Schmidhuber, J. (1997). Long short-term memory. *Neural Computation, 9*(8), 1735-1780.
- Shi, X., Chen, Z., Wang, H., Yeung, D.-Y., Wong, W.-K., y Woo, W.-C. (2015). Convolutional LSTM network: A machine learning approach for precipitation nowcasting. *Advances in Neural Information Processing Systems, 28*.
- Wexler, J., Pushkarna, M., Bolukbasi, T., Wattenberg, M., Viégas, F., y Wilson, J. (2019). The What-If Tool: Interactive probing of machine learning models. *IEEE Transactions on Visualization and Computer Graphics, 26*(1), 56-65.
- Yuan, Z., Zhou, X., y Yang, T. (2018). Hetero-ConvLSTM: A deep learning approach to traffic accident prediction on heterogeneous spatio-temporal data. *Proceedings of the 24th ACM SIGKDD*, 984-992.
