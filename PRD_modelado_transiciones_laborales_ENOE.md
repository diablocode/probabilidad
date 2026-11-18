# PRD: Explorador interactivo de probabilidades y dinámica laboral ENOE

**Estado:** Borrador inicial  
**Producto:** Aplicación analítica local en Python  
**Fuente inicial:** `enoe/ENOE_SDEMT226.csv` (`per = 226`); insumos longitudinales: `ENOE_SDEMT425.csv`, `ENOE_SDEMT126.csv` y `ENOE_SDEMT226.csv`

## 1. Resumen

Aplicación gráfica e interactiva para explorar la ocupación y las categorías laborales en los registros de la ENOE. El usuario podrá seleccionar filtros, consultar indicadores y gráficas, y ver en pantalla la tabla del CSV limitada a las observaciones que cumplen esos filtros.

El producto distinguirá explícitamente los resultados descriptivos observables en el archivo actual de las transiciones longitudinales que no pueden estimarse sin identificar a las mismas personas en entrevistas sucesivas. No presentará diferencias entre grupos `n_ent` como si fueran transiciones individuales.

## 2. Problema y oportunidad

La aplicación debe ser dinámica e interactiva: cuando el usuario cambie filtros —por ejemplo, sexo, grupo de edad, municipio o ronda—, las métricas, gráficas y filas del CSV visible se recalcularán y actualizarán en tiempo real, sin modificar ni volver a ejecutar manualmente un script. La experiencia reunirá filtros, resúmenes ponderados y no ponderados, visualizaciones y registros subyacentes en una sola interfaz.

Además, una simulación ilustrativa de Markov puede confundirse con una matriz de transición estimada si no se comunica claramente su naturaleza; por ello, los resultados observados y los hipotéticos deben identificarse por separado.

## 3. Objetivos

- Permitir explorar las variables laborales mediante controles seleccionables.
- Mostrar el CSV y actualizar su contenido según los filtros elegidos.
- Calcular probabilidades marginales, conjuntas y condicionales de ocupación.
- Comparar estimaciones simples con estimaciones ponderadas por `fac_tri`.
- Responder consultas tipo Bayes, por ejemplo, la composición por sexo y grupo de edad entre las personas clasificadas como empleadoras.
- Facilitar la exploración por ronda `n_ent` sin atribuir causalidad o seguimiento individual a diferencias entre rondas.
- Especificar cómo habilitar análisis Markov válidos cuando se disponga de microdatos longitudinales vinculables.

## 4. No objetivos y límites metodológicos

- El archivo base `per = 226` es transversal y no permite estimar transiciones empíricas a nivel persona.
- Aunque la aplicación carga los archivos `per = 425`, `126` y `226` en orden trimestral, tratará la confirmación de la clave de enlace como realizada por instrucción del usuario; seguirá aplicando las validaciones estructurales de datos y periodos.
- `n_ent` identifica la ronda de entrevista asignada a una observación; comparar sus grupos no equivale a observar a una persona antes y después.
- Una matriz hipotética o simulada no se etiquetará como estimación de la ENOE.
- Los resultados no sustituirán las recomendaciones metodológicas, documentación o factores de expansión oficiales de INEGI.

## 5. Usuarios y necesidades

**Usuario principal:** estudiante o analista que explora datos de empleo y necesita interpretar resultados descriptivos y probabilísticos.

Necesita:

1. Seleccionar subpoblaciones con controles sencillos.
2. Entender el denominador usado en cada indicador.
3. Comparar estimaciones ponderadas y simples.
4. Inspeccionar qué observaciones producen cada resultado.
5. Distinguir resultados observados, simulados y no estimables con el archivo disponible.

## 6. Datos

### 6.1 Archivo 

El archivo base es `enoe/ENOE_SDEMT226.csv`, un CSV SDEMT crudo con 25,214 filas leídas; la validación actual acepta 24,629 y descarta 585 con `fac_tri` no positivo. La aplicación deriva las variables analíticas desde `pos_ocu`, `sex` y `eda` y conserva el original sin modificaciones. Para el diagnóstico longitudinal carga además `enoe/ENOE_SDEMT425.csv` y `enoe/ENOE_SDEMT126.csv`; los códigos de periodo y `mes_cal` permiten ordenarlos como 2025-T4, 2026-T1 y 2026-T2.

### 6.2 Campos de análisis conocidos

| Campo | Uso previsto |
|---|---|
| `n_ent` | Ronda de entrevista (valores observados 1–5); filtro y agrupación descriptiva |
| `ocupado` | Indicador binario de ocupación (0/1) |
| `categoria_empleo` | Estado laboral categórico para personas ocupadas y etiqueta de no ocupado |
| `grupo_edad` | Segmentación demográfica por edad |
| `sexo_label` | Segmentación por sexo |
| `cve_mun` | Filtro o agrupación por municipio |
| `fac_tri` | Factor de expansión trimestral para resultados ponderados |
| `per` | Periodo de referencia, útil para mostrar contexto y validar comparabilidad |
| `pos_ocu`, `sex`, `eda` | Campos crudos SDEMT usados para derivar categoría laboral, sexo y grupo de edad |

Las categorías y valores disponibles se obtendrán del archivo al cargarlo, no se codificarán como universales. Categorías de empleo observadas en la inspección inicial: `Trabajador subordinado y remunerado`, `Trabajador por cuenta propia`, `Empleador`, `Trabajador sin pago` y `No aplica / no ocupado`.

### 6.3 Validación al cargar

- Comprobar presencia de campos necesarios para cada módulo y mostrar errores legibles si faltan.
- Validar tipos y valores de `ocupado`, `n_ent` y `fac_tri`; los registros inválidos no deben incorporarse silenciosamente.
- Informar número de filas cargadas, descartadas y motivo de descarte.
- Tratar explícitamente valores faltantes y categorías sin observaciones.
- Verificar que `fac_tri` sea positivo para estimaciones ponderadas y reportar las filas excluidas si no lo es.

## 7. Alcance funcional

### 7.1 Interfaz y filtros

- Interfaz web local implementada en Python; tecnología propuesta: **Streamlit**.
- Panel de filtros seleccionables para `n_ent`, `grupo_edad`, `sexo_label`, `cve_mun`, `ocupado` y `categoria_empleo`.
- Selección múltiple donde aplique, opción para incluir todos los valores y acción para restablecer filtros.
- Los indicadores, gráficas y tabla deben actualizarse con el mismo conjunto filtrado.
- Mostrar el tamaño de la muestra filtrada y, cuando corresponda, la suma de factores de expansión.

### 7.2 Tabla del CSV

- Mostrar una tabla interactiva con las columnas del CSV y únicamente las filas correspondientes a los filtros activos.
- Permitir ordenar y recorrer páginas de resultados; indicar filas totales filtradas y filas visibles.
- Permitir seleccionar las columnas visibles sin alterar los cálculos.
- Ofrecer descarga del subconjunto filtrado como CSV, conservando los valores originales.
- La tabla no debe sustituir los datos ni ocultar los filtros activos.

### 7.3 Probabilidades de ocupación

Calcular y presentar tasas según el subconjunto seleccionado:

- **Marginal:** \(P(ocupado=1)\).
- **Conjunta:** \(P(ocupado=1, X=x)\), con \(X\) seleccionable entre grupo de edad, sexo y municipio.
- **Condicional:** \(P(ocupado=1 \mid X=x)\).
- Permitir desglosar los resultados por más de una variable demográfica y por `n_ent`.

Para cada resultado, permitir alternar entre:

- **Simple:** conteo del numerador dividido entre el conteo del denominador.
- **Ponderado:** suma de `fac_tri` en el numerador dividida entre suma de `fac_tri` en el denominador.

La interfaz debe identificar el método, el numerador, el denominador, el tamaño muestral sin ponderar y, para el método ponderado, el peso agregado utilizado.

### 7.4 Consulta tipo Bayes

- Permitir seleccionar una categoría laboral como evidencia y una o más variables demográficas de interés.
- Mostrar la distribución condicional de la población seleccionada; ejemplo: entre personas con `categoria_empleo = Empleador`, distribución por `sexo_label` y `grupo_edad`.
- La interfaz debe expresar claramente la condición: por ejemplo, \(P(sexo, grupo\_edad \mid categoria\_empleo = Empleador)\).
- Mostrar resultados simples y ponderados, con denominador explícito.
- No fijar como dato garantizado el valor de `n=306`; el conteo se calculará dinámicamente con los filtros y los registros válidos.

### 7.5 Visualizaciones

Las visualizaciones serán interactivas y responderán a los filtros:

- Barras o tabla de ocupación por edad, sexo o municipio.
- Comparación por ronda `n_ent`, con conteos y porcentajes.
- Composición de categorías laborales entre personas ocupadas.
- Comparación lado a lado de estimadores simples y ponderados.
- Etiquetas, títulos y ejes en español; unidades y método visibles.
- Indicadores sin denominador válido se mostrarán como no disponibles, nunca como cero.

### 7.6 Módulo Markov: capacidad y modo de datos

La aplicación contemplará dos modos claramente separados:

**Modo A — archivo transversal actual**

- Mostrar composición de estados por ronda `n_ent` como comparación descriptiva.
- No estimar ni mostrar una matriz de transición empírica, distribución estacionaria o tiempos de primer paso a partir de esas proporciones.
- Si se incluye una simulación, identificarla como escenario hipotético, explicar sus supuestos y separar visualmente sus resultados de los observados.
- Mostrar una advertencia: el archivo base `per = 226` no demuestra seguimiento individual. En el conjunto de varios periodos, la clave se asume confirmada por instrucción del usuario y cada par aún debe superar las validaciones estructurales.

**Modo B — diagnóstico de los microdatos longitudinales disponibles**

La aplicación combina los archivos disponibles de varios trimestres y propone la clave `cve_ent`, `con`, `upm`, `n_pro_viv`, `v_sel`, `n_hog`, `h_mud`, `n_ren`. Por instrucción del usuario, la confirmación de que identifica a la misma persona en cada periodo se considera realizada automáticamente, sin solicitar un checkbox. La aplicación valida periodos consecutivos, rondas, duplicados, pérdida de seguimiento y estados faltantes antes de estimar. Los filtros transversales del archivo base no se aplican automáticamente a este análisis longitudinal.

Con datos aptos, el módulo:

- Usa cinco estados: subordinado, cuenta propia, empleador, sin pago y no ocupado.
- Estima probabilidades simples y ponderadas desde pares consecutivos. La ponderada usa `fac_tri_origen` y se identifica como estimador, no como factor longitudinal oficial.
- Muestra conteos y matriz \(P\), con filas como estado de origen y columnas como estado destino; filas sin salidas observadas se reportan como no disponibles.
- Calcula la distribución estacionaria única cuando la cadena y las observaciones permiten identificarla; informa cuando no hay una solución única.
- Calcula tiempos esperados de primer paso en pasos trimestrales, reportando \(\infty\) si la probabilidad de alcanzar el destino es menor que uno.
- Clasifica clases comunicantes, irreducibilidad, periodicidad y ergodicidad antes de interpretarlas.
- Muestra transiciones, cobertura potencial de seguimiento, periodos y advertencias; no hereda automáticamente los filtros transversales del panel principal.

## 8. Requisitos no funcionales

- **Reproducibilidad:** los mismos datos, filtros y método producen los mismos resultados.
- **Transparencia:** cada métrica expone filtros, denominador y ponderación.
- **Usabilidad:** lenguaje en español, estados vacíos y errores comprensibles.
- **Rendimiento:** filtros y visualizaciones deben responder fluidamente con unas 25 mil filas en el archivo base y aproximadamente 73 mil al combinar los tres periodos.
- **Privacidad:** procesamiento local; no enviar el CSV a servicios externos.
- **Integridad:** nunca sobrescribir el CSV original; exportaciones separadas.
- **Accesibilidad básica:** contraste legible, títulos claros y significado no dependiente solo del color.

## 9. Criterios de aceptación

1. Al abrir la aplicación con el CSV inicial, se visualiza una tabla con las filas del archivo y los filtros disponibles con base en los valores encontrados.
2. Al cambiar cualquier filtro, la tabla, el total de observaciones, las gráficas y las métricas reflejan el mismo subconjunto.
3. La tabla permite revisar el CSV filtrado y descargarlo sin alterar el archivo de entrada.
4. Para cualquier filtro válido, la probabilidad simple de ocupación coincide con conteos manuales del subconjunto.
5. La probabilidad ponderada coincide con la razón de sumas de `fac_tri` del numerador y denominador definidos.
6. La consulta tipo Bayes especifica correctamente la evidencia y calcula la composición condicionada por ella.
7. El usuario puede comparar estimadores ponderados y simples e identificar el método y denominador.
8. En el modo transversal, la aplicación no presenta `n_ent` como seguimiento individual ni afirma estimar transiciones empíricas.
9. Los valores ausentes, denominadores nulos y archivos con columnas requeridas faltantes generan mensajes explícitos.
10. Una matriz, distribución estacionaria o tiempo de primer paso se presenta como empírico únicamente si se habilitó y validó el modo longitudinal.

## 10. Métricas de éxito

- El usuario puede responder una consulta descriptiva y ver sus registros subyacentes sin editar código.
- La tabla y todos los resultados permanecen sincronizados con los filtros activos.
- No hay discrepancias entre resultados de prueba de probabilidades y cálculos de referencia sobre los mismos datos.
- No se comunica ninguna transición individual que no esté respaldada por registros enlazados.

## 11. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Interpretar rondas `n_ent` como seguimiento de personas | Advertencia permanente y separación entre comparación transversal y modo longitudinal |
| Confundir simulación con estimación | Etiquetado “hipotético”, supuestos visibles y estilos diferenciados |
| Usar incorrectamente `fac_tri` o denominadores | Mostrar fórmula, universo analítico, conteo y peso agregado |
| Cambios en etiquetas o estructura del CSV | Descubrimiento dinámico de categorías y validación de esquema |
| Clave o periodos con problemas estructurales | Excluir registros inválidos y no habilitar pares ambiguos aunque la confirmación de la clave se asuma realizada |

## 12. Propuesta de fases

1. **Aplicación y filtros:** carga y validación del CSV, tabla visible y filtros seleccionables.
2. **Probabilidades de ocupación:** indicadores simples y ponderados, tablas y gráficas.
3. **Consulta y exportación:** análisis tipo Bayes y descarga del subconjunto filtrado.
4. **Preparación longitudinal:** combinación de periodos, confirmación asumida por instrucción del usuario y validaciones estructurales.
5. **Análisis Markov:** matrices de transición, distribución estacionaria, tiempos de primer paso y clasificación de estados.

Las cinco fases están implementadas. La confirmación de la clave se asume por instrucción del usuario; la app informa la ponderación, cobertura y límites de cada resultado.
