# Implementation Plan: Explorador interactivo ENOE

**Documento base:** [PRD_modelado_transiciones_laborales_ENOE.md](./PRD_modelado_transiciones_laborales_ENOE.md)  
**Tecnología propuesta:** Python + Streamlit  
**Estrategia:** entregar incrementos pequeños y ejecutables; cada fase termina con pruebas automatizadas y una forma documentada de validar la aplicación.
**Estado:** fases 1, 2, 3, 4 y 5 implementadas y verificadas.

## Principios de implementación

1. La aplicación debe poder ejecutarse localmente desde la fase 1.
2. Los cálculos se implementarán en funciones independientes de la interfaz para poder probarlos con datos pequeños y deterministas.
3. Las pruebas no dependerán exclusivamente del CSV real: usarán fixtures controlados para verificar resultados exactos y casos límite.
4. Después de cada fase se ejecutarán las pruebas de esa fase y las pruebas previas.
5. El CSV original será de solo lectura. Los archivos exportados se escribirán en una ubicación elegida por el usuario.
6. La UI reflejará una sola selección de filtros en indicadores, gráficas y tabla.
7. El archivo base no se tratará por sí solo como panel enlazado. Para el conjunto longitudinal, la confirmación de la clave se asume por instrucción del usuario y se mantienen las validaciones estructurales persona-periodo.

## Estructura inicial propuesta

La estructura puede ajustarse a las convenciones que se adopten al iniciar la implementación, pero debe mantener separadas la interfaz, las transformaciones y las pruebas:

```text
proyecto final/
├── app.py
├── enoe_app/
│   ├── data.py
│   ├── filters.py
│   ├── metrics.py
│   └── markov.py
├── tests/
│   ├── conftest.py
│   ├── test_data.py
│   ├── test_filters.py
│   ├── test_metrics.py
│   └── test_app.py
├── enoe/
│   ├── ENOE_SDEMT425.csv
│   ├── ENOE_SDEMT126.csv
│   └── ENOE_SDEMT226.csv
├── pyproject.toml
└── analisis_transiciones_enoe.py
```

La estructura no implica que todos los módulos deban implementarse desde la fase 1. Se agregarán conforme sean necesarios. Las dependencias y comandos se declararán en `pyproject.toml` para que la instalación y las pruebas sean reproducibles.

## Fase 1 — Aplicación ejecutable, carga, filtros y tabla (implementada)

### Objetivo

Crear el primer incremento funcional: abrir la aplicación, cargar el CSV, seleccionar filtros y ver en pantalla la tabla filtrada. La fase también establece desde el inicio el entorno de pruebas.

### Trabajo

1. Crear la estructura mínima del proyecto y declarar dependencias de ejecución y desarrollo.
2. Implementar la carga del CSV local sin modificar el original.
3. Validar las columnas requeridas para filtros y vistas; mostrar errores explícitos si el archivo no existe o su estructura no permite continuar.
4. Implementar filtros seleccionables para `n_ent`, `grupo_edad`, `sexo_label`, `cve_mun`, `ocupado` y `categoria_empleo`, con opción de todos los valores y restablecimiento.
5. Mostrar las filas coincidentes en una tabla; incluir total filtrado y permitir revisar las páginas disponibles.
6. Mostrar información básica del archivo: nombre, filas cargadas, filtros activos y cantidad de filas descartadas, si las hubiera.
7. Crear fixtures pequeños para pruebas; no usar el CSV completo como único mecanismo de prueba.

### Pruebas desde esta fase

- **Unitarias de carga:** lectura correcta, columnas faltantes, archivo vacío, valores numéricos inválidos y manejo explícito de valores faltantes.
- **Unitarias de filtros:** cada filtro conserva solo los valores seleccionados; varios filtros se combinan correctamente; la selección “todos” no altera el conjunto.
- **Interfaz:** probar la aplicación con `streamlit.testing.v1.AppTest` (o mecanismo equivalente de Streamlit) para confirmar que inicia, muestra controles y presenta las filas filtradas tras cambiar una selección.
- **Smoke test del archivo real:** cargar el CSV incluido, confirmar que la app no falla y que el total cargado es consistente con el archivo. No fijar cifras estadísticas como verdad permanente si el archivo puede actualizarse.

### Criterios de salida

- La aplicación inicia con el comando documentado y no requiere editar el código para seleccionar filtros.
- Cambiar un filtro actualiza la tabla y el conteo sin reiniciar manualmente el proceso.
- La tabla muestra solo registros que cumplen todos los filtros activos.
- Los errores de archivo o esquema se comunican en pantalla, sin continuar con datos inválidos.
- La suite automatizada de la fase pasa desde un entorno limpio con las dependencias declaradas.

### Validación manual

Ejecutar la aplicación, filtrar por una ronda y un grupo de edad, comprobar algunas filas visibles contra el CSV y restaurar todos los filtros.

### Verificación de entrega

- `python -m pytest -q`: 11 pruebas aprobadas, incluidas las pruebas de carga, filtros y actualización de la interfaz.
- CSV base `enoe/ENOE_SDEMT226.csv`: 25,214 filas leídas, 24,629 aceptadas y 585 descartadas por `fac_tri` no positivo. Las etiquetas analíticas se derivan de los campos crudos SDEMT.
- Servidor Streamlit local: comprobación de salud HTTP respondida con `ok`.

## Fase 2 — Indicadores y probabilidades de ocupación (implementada)

### Objetivo

Agregar indicadores simples y ponderados que reaccionen a los filtros de la fase 1.

### Trabajo

1. Implementar funciones puras para conteos y probabilidades marginales, conjuntas y condicionales de `ocupado`.
2. Implementar estimadores simples y ponderados por `fac_tri`, con numerador, denominador y tamaño muestral explícitos.
3. Agregar desglose por `grupo_edad`, `sexo_label`, `cve_mun` y `n_ent`.
4. Incorporar visualizaciones que respondan a filtros y distingan claramente método simple de ponderado.
5. Manejar grupos vacíos y denominadores nulos como “no disponible”, no como cero.

### Pruebas

- Comparar cada función con resultados calculados manualmente sobre fixtures deterministas.
- Verificar que la probabilidad simple usa conteos y la ponderada usa la razón de sumas de `fac_tri`.
- Cubrir filtros que dejan cero filas, factor de expansión inválido y categorías con una sola observación.
- Probar en la interfaz que al cambiar un filtro cambian conjuntamente tabla, indicadores y visualizaciones.
- Ejecutar la suite completa de las fases 1 y 2.

### Criterios de salida

- Los resultados presentan método, universo, numerador, denominador, conteo sin ponderar y peso agregado cuando aplique.
- Los cálculos coinciden con las pruebas de referencia.
- Las gráficas no representan una tasa indefinida como 0%.

### Verificación de entrega

- `python -m pytest -q`: 18 pruebas aprobadas para las fases 1 y 2.
- Las pruebas verifican probabilidades marginales, conjuntas y condicionales con datos deterministas, con y sin ponderación.
- La prueba de interfaz confirma que los indicadores y la visualización reaccionan al cambiar el filtro de sexo.

## Fase 3 — Consulta tipo Bayes, comparación y exportación (implementada)

### Objetivo

Permitir consultas condicionales configurables y facilitar la inspección y reutilización del subconjunto filtrado.

### Trabajo

1. Permitir seleccionar una categoría laboral como evidencia y variables demográficas para describir.
2. Calcular la composición condicional, por ejemplo \(P(sexo, grupo\_edad \mid categoria\_empleo = Empleador)\), en versiones simple y ponderada.
3. Mostrar explícitamente la evidencia, filtros adicionales y denominador de cada resultado.
4. Habilitar selección de columnas visibles y descarga CSV del conjunto filtrado, preservando los valores originales.
5. Informar el tamaño de la muestra y el peso agregado en la consulta.

### Pruebas

- Verificar distribuciones condicionales sobre fixtures con proporciones conocidas, incluyendo combinaciones demográficas ausentes.
- Confirmar que el denominador corresponde al conjunto que satisface la evidencia y los demás filtros.
- Verificar que los resultados ponderados y simples coinciden con cálculos de referencia distintos cuando los pesos no son uniformes.
- Comprobar que el CSV descargado incluye las filas filtradas, no modifica el original y conserva las columnas elegidas.
- Probar la interacción de filtros, consulta, tabla y descarga.

### Criterios de salida

- La interfaz expresa la condición de probabilidad en lenguaje claro y en notación cuando corresponda.
- El tamaño muestral no se fija en el código; se recalcula con los datos y filtros activos.
- La descarga reproduce el subconjunto mostrado.

### Verificación de entrega

- `python -m pytest -q`: 30 pruebas aprobadas para las fases 1 a 3.
- El CSV base devuelve 723 registros válidos para `categoria_empleo = Empleador`; la composición por sexo y edad suma 100% en las versiones simple y ponderada.
- La exportación probada conserva filas y columnas seleccionadas, no modifica el DataFrame fuente y genera un CSV UTF-8 con BOM.

## Fase 4 — Preparación y validación de datos longitudinales (implementada)

### Objetivo

Preparar los datos para enlazar personas entre entrevistas consecutivas. La clave se considera confirmada por instrucción del usuario; la fase sigue validando secuencias temporales, duplicados y estados antes de producir pares.

### Formato esperado

- CSV UTF-8 con una fila por persona y periodo.
- Campos identificadores seleccionados explícitamente; la confirmación de que identifican a la misma persona se asume realizada por instrucción del usuario.
- `period_index`: entero que represente periodos consecutivos. En los archivos SDEMT se deriva de `per` y se valida contra `mes_cal`; `n_ent` no es índice temporal, sino ronda de entrevista.
- Campo de estado con las etiquetas laborales ENOE conocidas o estados canónicos: `Subordinado`, `Cuenta propia`, `Empleador`, `Sin pago` y `No ocupado`.
- `fac_tri` positivo y finito para cada fila que se pretenda utilizar posteriormente.

### Trabajo

1. Documentar el formato esperado de los archivos longitudinales y los campos de periodo, ronda, estado y enlace.
2. Usar la clave seleccionada como confirmada sin requerir un checkbox; informar que esta confirmación proviene de la instrucción del usuario.
3. Implementar validaciones para duplicados, secuencias no consecutivas, estados faltantes y pérdida de seguimiento.
4. Construir pares de observaciones consecutivas cuando el emparejamiento sea inequívoco y no haya duplicados persona-periodo.
5. Mostrar diagnóstico de registros recibidos, personas enlazadas, transiciones utilizables y exclusiones.
6. Mantener el modo Markov empírico deshabilitado ante datos insuficientes o inconsistentes.
7. Combinar `enoe/ENOE_SDEMT425.csv`, `ENOE_SDEMT126.csv` y `ENOE_SDEMT226.csv` en orden trimestral, además de permitir cargar un CSV externo; mostrar controles para seleccionar campos identificadores y un diagnóstico.

### Pruebas

- Usar datos sintéticos con identificadores y periodos conocidos para probar enlaces correctos.
- Probar identificadores duplicados, saltos de periodo, entrevistas faltantes, persona sin pareja y estados desconocidos.
- Verificar que datos inválidos bloquean el cálculo y producen un diagnóstico visible.
- Confirmar que el archivo base transversal no se interpreta por sí solo como seguimiento persona a persona.

### Criterios de salida

- La clave se trata como confirmada por instrucción del usuario y la cobertura temporal queda documentada.
- Los pares de transición pueden rastrearse a las observaciones fuente.
- El modo empírico permanece bloqueado si no se satisfacen los requisitos longitudinales.

### Verificación de entrega

- `python -m pytest -q`: 41 pruebas aprobadas para las fases 1 a 4, incluidas normalización SDEMT, carga de fuentes múltiples, periodos con saltos, estados desconocidos y el flujo de carga de la interfaz.
- Los tres CSV contienen 74,498 filas originales en total; se aceptan 72,832 y se descartan 1,666 por `fac_tri` no positivo. Los periodos son 2025-T4 (`per=425`), 2026-T1 (`per=126`) y 2026-T2 (`per=226`); `n_ent` se valida por separado y no se usa como periodo.
- La combinación `cve_ent`, `con`, `upm`, `n_pro_viv`, `v_sel`, `n_hog`, `h_mud`, `n_ren` no presenta duplicados persona-periodo y produce 34,715 pares, todos con incremento de `n_ent` igual a uno. La app considera confirmada la clave por instrucción del usuario y presenta los pares para la siguiente fase; aún no estima matrices de transición.

## Fase 5 — Matriz de transición y análisis Markov (implementada)

### Objetivo

Calcular y presentar métricas Markov únicamente a partir de pares longitudinales validados.

### Trabajo

1. Normalizar las categorías observadas al espacio de estados acordado, documentando cómo se mapea “No aplica / no ocupado” a “No ocupado”.
2. Estimar la matriz de transición con estados de origen en filas y destino en columnas; registrar el método de ponderación.
3. Mostrar conteos y probabilidades por celda, incluyendo estados sin transiciones salientes.
4. Diagnosticar clases comunicantes, irreducibilidad y periodicidad antes de informar ergodicidad.
5. Calcular distribución estacionaria y tiempos medios de primer paso solo cuando las condiciones matemáticas y los datos los permitan.
6. Mostrar cobertura de seguimiento, periodo, tamaño de muestra y advertencias en la interfaz.
7. Si se conserva una simulación hipotética, ofrecerla como herramienta separada y nunca mezclarla con la estimación empírica.

La matriz ponderada utiliza `fac_tri_origen` para ponderar cada par. Los tiempos de primer paso se expresan en pasos entre periodos consecutivos; la diagonal representa tiempo cero y \(\infty\) indica que la probabilidad de alcanzar el estado destino es menor que uno.

### Pruebas

- Usar matrices sintéticas cuya estructura y resultados conocidos permitan verificar las funciones.
- Probar matriz con filas normalizadas, estado absorbente, estados no observados y cadenas reducibles o periódicas.
- Verificar que la distribución estacionaria satisface \(\pi P = \pi\) dentro de una tolerancia numérica documentada cuando exista.
- Validar los tiempos de primer paso con casos pequeños calculables manualmente y bloquear casos no definidos.
- Confirmar que la interfaz nunca rotula una matriz hipotética como estimada de la ENOE.

### Criterios de salida

- Cada resultado Markov puede trazarse a datos longitudinales validados y reglas de cálculo documentadas.
- Las condiciones de existencia y las limitaciones se muestran junto con los resultados.
- Los diagnósticos y pruebas cubren cadenas reducibles, estados no observados y casos sin solución única.

### Verificación de entrega

- `python -m pytest -q`: 50 pruebas aprobadas para las fases 1 a 5.
- Las pruebas cubren estimación simple y ponderada, cadenas completas e incompletas, clases comunicantes, periodicidad, distribución estacionaria única/no única y tiempos de primer paso finitos o infinitos.
- Con los tres CSV actuales se estiman 34,715 pares en los cinco estados; el 78.8% de las filas válidas tiene al menos una pareja candidata. Las matrices simple y ponderada son estocásticas, irreducibles, aperiódicas y ergódicas. La residual de la distribución estacionaria queda por debajo de \(10^{-8}\).

## Ciclo de validación por incremento

Al terminar cada fase:

1. Ejecutar todas las pruebas automatizadas, no solo las nuevas.
2. Iniciar la aplicación localmente y realizar la validación manual definida para la fase.
3. Revisar que la tabla, métricas y visualizaciones representen los mismos filtros.
4. Actualizar instrucciones de ejecución, dependencias y criterios de aceptación si cambió el comportamiento acordado.
5. No iniciar la fase siguiente mientras haya fallos de cálculo o de sincronización de filtros en la fase actual.

## Comandos previstos

Los comandos definitivos se fijarán al crear la configuración del proyecto. Como interfaz de uso, se recomienda documentar:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m streamlit run app.py
```

La configuración debe incluir Streamlit, la biblioteca de manejo de datos y visualización elegida, y pytest como dependencia de desarrollo. Las pruebas deben poder ejecutarse sin abrir un navegador; la validación manual de la UI complementa, pero no reemplaza, las pruebas automatizadas.
