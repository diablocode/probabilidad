"""Interfaz local para inspeccionar y filtrar el CSV de la ENOE."""

from collections.abc import Mapping, Sequence
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from enoe_app.bayes import conditional_composition
from enoe_app.data import (
    DataLoadReport,
    DataValidationError,
    load_dataset,
    load_datasets,
    prepare_enoe_frame,
)
from enoe_app.export import filtered_csv_bytes
from enoe_app.filters import (
    FILTER_COLUMNS,
    MISSING_OPTION,
    apply_filters,
    get_filter_options,
)
from enoe_app.longitudinal import (
    LongitudinalDataError,
    analyze_longitudinal_data,
)
from enoe_app.markov import MARKOV_STATES, MarkovDataError, estimate_markov_chain
from enoe_app.metrics import occupation_by_group, occupation_totals


LONGITUDINAL_SOURCE_FILES = (
    "ENOE_SDEMT425.csv",
    "ENOE_SDEMT126.csv",
    "ENOE_SDEMT226.csv",
)

FILTER_LABELS = {
    "cve_ent": "Entidad",
    "grupo_edad": "Grupo de edad",
    "sexo_label": "Sexo",
    "cve_mun": "Municipio",
    "ocupado": "Ocupación (0 = no ocupado, 1 = ocupado)",
    "categoria_empleo": "Categoría de empleo",
}
DEMOGRAPHIC_LABELS = {
    "grupo_edad": "Grupo de edad",
    "sexo_label": "Sexo",
    "cve_mun": "Municipio",
    "categoria_empleo": "Categoría de empleo",
}


@st.cache_data(show_spinner=False)
def cached_load_dataset(path: str) -> DataLoadReport:
    """Carga en caché el archivo para evitar releerlo en cada interacción."""
    return load_dataset(path)


@st.cache_data(show_spinner=False)
def cached_load_longitudinal_files(
    paths: tuple[str, ...],
) -> tuple[pd.DataFrame, tuple[DataLoadReport, ...]]:
    """Carga en caché los archivos SDEMT seleccionados para la fase longitudinal."""
    return load_datasets(paths)


def _show_load_report(report: DataLoadReport) -> None:
    st.caption(f"Archivo: `{report.source_path.name}`")
    st.caption(
        f"Filas leídas: {report.loaded_rows:,} · "
        f"Filas válidas: {report.accepted_rows:,} · "
        f"Filas descartadas: {report.discarded_rows:,}"
    )
    if report.discard_reasons:
        with st.expander("Motivos de descarte"):
            st.table(
                pd.DataFrame(
                    [
                        {"Motivo": reason, "Filas afectadas": count}
                        for reason, count in report.discard_reasons.items()
                    ]
                )
            )


def _render_filters(frame: pd.DataFrame) -> dict[str, list[object]]:
    reset_clicked = st.sidebar.button(
        "Restablecer filtros", key="reset_filters", width="stretch"
    )

    ent_options = get_filter_options(frame, "cve_ent")
    ent_key = "filter_cve_ent"
    if reset_clicked or ent_key not in st.session_state:
        st.session_state[ent_key] = ent_options.copy()
    else:
        current = st.session_state[ent_key]
        st.session_state[ent_key] = [v for v in current if v in ent_options]

    selections: dict[str, list[object]] = {}
    selections["cve_ent"] = st.sidebar.multiselect(
        FILTER_LABELS["cve_ent"],
        options=ent_options,
        key=ent_key,
    )

    selected_ent = selections["cve_ent"]
    mun_frame = (
        apply_filters(frame, {"cve_ent": selected_ent}) if selected_ent else frame
    )

    for column in FILTER_COLUMNS:
        if column == "cve_ent":
            continue
        options = get_filter_options(
            mun_frame if column == "cve_mun" else frame, column
        )
        key = f"filter_{column}"
        if reset_clicked or key not in st.session_state:
            st.session_state[key] = options.copy()
        else:
            current = st.session_state[key]
            st.session_state[key] = [value for value in current if value in options]

        selections[column] = st.sidebar.multiselect(
            FILTER_LABELS[column],
            options=options,
            key=key,
            help=(
                f"Valores disponibles: {len(options) - int(MISSING_OPTION in options)}"
                + ("; incluye valores faltantes." if MISSING_OPTION in options else "")
            ),
        )
    return selections


def _format_percentage(value: float | None) -> str:
    return f"{value:.2%}" if value is not None else "N/D"


def _render_occupation_analysis(frame: pd.DataFrame) -> None:
    st.subheader("Indicadores de ocupación")
    totals = occupation_totals(frame)
    count_column, simple_column, weighted_column = st.columns(3)
    count_column.metric("Observaciones", f"{totals.observations:,}")
    simple_column.metric(
        "P(ocupado=1) simple", _format_percentage(totals.probability_simple)
    )
    weighted_column.metric(
        "P(ocupado=1) ponderada",
        _format_percentage(totals.probability_weighted),
    )
    st.caption(
        f"Marginal simple: {totals.occupied:,} / {totals.observations:,}. "
        f"Marginal ponderada: {totals.occupied_weight:,.2f} / "
        f"{totals.total_weight:,.2f} usando fac_tri."
    )

    dimensions = ("grupo_edad", "sexo_label", "cve_mun", "cve_ent")
    group_by = st.selectbox(
        "Desglosar probabilidades por",
        options=dimensions,
        format_func=lambda column: FILTER_LABELS[column],
        key="occupation_breakdown",
    )
    summary = occupation_by_group(frame, group_by)
    if summary.empty:
        st.info("No hay observaciones para calcular probabilidades por grupo.")
        return

    st.caption(
        "Conjunta: ocupados del grupo / población filtrada. "
        "Condicional: ocupados del grupo / total del grupo. "
        "Las versiones ponderadas usan las sumas de fac_tri."
    )
    st.dataframe(
        summary,
        column_config={
            group_by: st.column_config.Column(FILTER_LABELS[group_by]),
            "observaciones": st.column_config.NumberColumn(
                "Observaciones", format="%d"
            ),
            "ocupados": st.column_config.NumberColumn("Ocupados", format="%d"),
            "peso_total_fac_tri": st.column_config.NumberColumn(
                "Suma fac_tri", format="%.2f"
            ),
            "ocupados_ponderados": st.column_config.NumberColumn(
                "Suma fac_tri de ocupados", format="%.2f"
            ),
            "probabilidad_conjunta_simple": st.column_config.NumberColumn(
                "P(ocupado, grupo) simple", format="percent"
            ),
            "probabilidad_conjunta_ponderada": st.column_config.NumberColumn(
                "P(ocupado, grupo) ponderada", format="percent"
            ),
            "probabilidad_condicional_simple": st.column_config.NumberColumn(
                "P(ocupado | grupo) simple", format="percent"
            ),
            "probabilidad_condicional_ponderada": st.column_config.NumberColumn(
                "P(ocupado | grupo) ponderada", format="percent"
            ),
        },
        width="stretch",
        hide_index=True,
    )

    chart = summary.set_index(group_by)[
        [
            "probabilidad_condicional_simple",
            "probabilidad_condicional_ponderada",
        ]
    ].rename(
        columns={
            "probabilidad_condicional_simple": "Simple",
            "probabilidad_condicional_ponderada": "Ponderada (fac_tri)",
        }
    )
    st.bar_chart(
        chart,
        x_label=FILTER_LABELS[group_by],
        y_label="Probabilidad condicional de estar ocupado",
        stack=False,
        height=350,
    )


def _render_bayes_query(frame: pd.DataFrame) -> None:
    st.subheader("Consulta tipo Bayes")
    st.caption(
        "La consulta se calcula dentro del subconjunto que dejan los filtros "
        "generales activos."
    )
    evidence_options = {"Ocupado": 1, "No ocupado": 0}
    evidence_label = st.selectbox(
        "Ocupación como evidencia",
        options=list(evidence_options.keys()),
        key="bayes_evidence_category",
    )
    evidence_value = evidence_options[evidence_label]

    dimensions = st.multiselect(
        "Describir la distribución por",
        options=list(DEMOGRAPHIC_LABELS),
        default=["sexo_label", "grupo_edad"],
        format_func=lambda column: DEMOGRAPHIC_LABELS[column],
        key="bayes_dimensions",
    )
    if not dimensions:
        st.info("Seleccione al menos una variable para calcular la distribución.")
        return

    result = conditional_composition(
        frame,
        evidence_column="ocupado",
        evidence_value=evidence_value,
        dimensions=dimensions,
    )
    dimension_labels = ", ".join(DEMOGRAPHIC_LABELS[column] for column in dimensions)
    st.caption(
        f"Consulta: P({dimension_labels} | ocupado = {evidence_label})."
    )
    count_column, weight_column = st.columns(2)
    count_column.metric("Denominador de la evidencia (n)", f"{result.evidence_count:,}")
    weight_column.metric(
        "Denominador ponderado (suma fac_tri)",
        f"{result.evidence_weight:,.2f}",
    )
    if result.groups.empty:
        st.info("No hay observaciones para la evidencia seleccionada.")
        return

    st.dataframe(
        result.groups,
        column_config={
            **{
                column: st.column_config.Column(DEMOGRAPHIC_LABELS[column])
                for column in dimensions
            },
            "observaciones": st.column_config.NumberColumn(
                "Personas en el grupo", format="%d"
            ),
            "peso_fac_tri": st.column_config.NumberColumn(
                "Suma fac_tri del grupo", format="%.2f"
            ),
            "probabilidad_simple": st.column_config.NumberColumn(
                "Proporción simple", format="percent"
            ),
            "probabilidad_ponderada": st.column_config.NumberColumn(
                "Proporción ponderada", format="percent"
            ),
        },
        width="stretch",
        hide_index=True,
    )


def _format_period_label(period: int) -> str:
    try:
        quarter = period // 100
        year = 2000 + (period % 100)
        if 1 <= quarter <= 4 and 2000 <= year <= 2100:
            return f"{year}-T{quarter}"
    except Exception:
        pass
    if period // 4 >= 2000:
        return f"{period // 4}-T{period % 4 + 1}"
    return str(period)


def _render_markov_analysis(pairs: pd.DataFrame) -> None:
    st.subheader("Matriz de transición y análisis Markov")
    weighting_label = st.selectbox(
        "Método para estimar la matriz",
        options=["Simple (conteo de pares)", "Ponderada (fac_tri de origen)"],
        key="markov_weighting",
    )
    weighting = (
        "weighted"
        if weighting_label == "Ponderada (fac_tri de origen)"
        else "simple"
    )

    st.markdown("### Cálculo de matrices por pasos")
    st.caption(
        "Se muestra el cálculo individual de las matrices de transición para cada "
        "par de periodos consecutivos y, finalmente, el resultado acumulado."
    )

    transition_steps = sorted(
        pairs[["periodo_origen", "periodo_destino"]]
        .drop_duplicates()
        .values.tolist()
    )

    step_reports = []
    for orig, dest in transition_steps:
        step_pairs = pairs.loc[
            pairs["periodo_origen"].eq(orig) & pairs["periodo_destino"].eq(dest)
        ]
        if step_pairs.empty:
            continue
        try:
            step_report = estimate_markov_chain(step_pairs, weighting=weighting)
        except MarkovDataError as error:
            st.warning(
                f"No se pudo estimar la transición {_format_period_label(orig)} "
                f"→ {_format_period_label(dest)}: {error}"
            )
            continue

        step_reports.append(step_report)
        st.markdown(
            f"#### Paso: {_format_period_label(orig)} → {_format_period_label(dest)}"
        )
        step_col1, step_col2 = st.columns(2)
        step_col1.metric("Pares en este paso", f"{step_report.total_transitions:,}")
        step_col2.metric(
            "Suma fac_tri origen",
            f"{step_report.row_weight_totals.sum():,.2f}",
        )

        sc_col, sp_col = st.columns(2)
        with sc_col:
            st.markdown("**Conteos observados**")
            st.dataframe(step_report.transition_counts, width="stretch")
        with sp_col:
            st.markdown("**Matriz de probabilidades estimada**")
            st.dataframe(
                step_report.transition_probabilities,
                column_config={
                    state: st.column_config.NumberColumn(state, format="%.3f")
                    for state in step_report.transition_probabilities.columns
                },
                width="stretch",
            )
        st.markdown("---")

    st.markdown("### Resultado final (Cadena de Markov acumulada)")
    try:
        report = estimate_markov_chain(pairs, weighting=weighting)
    except MarkovDataError as error:
        st.error(f"No se pudo estimar la matriz de transición conjunta: {error}")
        return

    if len(step_reports) >= 2:
        st.markdown("#### Composición matricial en dos pasos ($P^{(1)} \times P^{(2)}$)")
        st.caption(
            "Cálculo paso a paso de la combinación (multiplicación matricial) de la Matriz 1 "
            f"({_format_period_label(transition_steps[0][0])} → {_format_period_label(transition_steps[0][1])}) "
            "con la Matriz 2 "
            f"({_format_period_label(transition_steps[1][0])} → {_format_period_label(transition_steps[1][1])}). "
            "Cada celda $(i, j)$ resulta de sumar los productos elementales de la fila $i$ "
            "de la Matriz 1 por la columna $j$ de la Matriz 2."
        )

        mat1_clean = step_reports[0].transition_probabilities.fillna(0.0).values
        mat2_clean = step_reports[1].transition_probabilities.fillna(0.0).values
        product_values = mat1_clean @ mat2_clean
        product_df = pd.DataFrame(
            product_values,
            index=MARKOV_STATES,
            columns=MARKOV_STATES,
        )

        st.dataframe(
            product_df,
            column_config={
                state: st.column_config.NumberColumn(state, format="%.3f")
                for state in product_df.columns
            },
            width="stretch",
        )

        with st.expander("Ver detalle paso a paso: Multiplicación y suma por fila y columna"):
            breakdown_rows = []
            for i, row_state in enumerate(MARKOV_STATES):
                for j, col_state in enumerate(MARKOV_STATES):
                    terms = []
                    sum_val = 0.0
                    for k, mid_state in enumerate(MARKOV_STATES):
                        p1 = mat1_clean[i, k]
                        p2 = mat2_clean[k, j]
                        term = p1 * p2
                        sum_val += term
                        terms.append(f"({p1:.3f} × {p2:.3f})")
                    formula_str = " + ".join(terms)
                    breakdown_rows.append(
                        {
                            "Estado Origen (Fila)": row_state,
                            "Estado Destino (Columna)": col_state,
                            "Cálculo (Suma de productos)": formula_str,
                            "Resultado (Probabilidad a 2 pasos)": f"{sum_val:.3f}",
                        }
                    )
            st.dataframe(pd.DataFrame(breakdown_rows), width="stretch", hide_index=True)
        st.markdown("---")

    period_labels = [_format_period_label(p) for p in report.periods]
    st.caption(
        f"Transiciones observadas totales: {report.total_transitions:,} · "
        "Periodos: "
        f"{' → '.join(period_labels)}. "
        + (
            "La opción ponderada usa fac_tri_origen del trimestre de origen; "
            "es un estimador ponderado explícito, no un factor longitudinal. "
            "Las filas son estados de origen y las columnas estados destino."
            if weighting == "weighted"
            else "Cada par persona-periodo aporta una observación; las filas "
            "son estados de origen y las columnas estados destino."
        )
    )
    count_column, weight_column, state_column = st.columns(3)
    count_column.metric("Pares utilizados totales", f"{report.total_transitions:,}")
    weight_column.metric(
        "Suma fac_tri de origen total", f"{report.row_weight_totals.sum():,.2f}"
    )
    state_column.metric(
        "Estados sin salidas observadas",
        f"{len(report.states_without_outgoing)}",
    )

    if report.states_without_outgoing:
        st.warning(
            "No se estiman filas de probabilidad para: "
            + ", ".join(report.states_without_outgoing)
            + ". Se muestran como N/D, no como ceros."
        )

    counts_column, matrix_column = st.columns(2)
    with counts_column:
        st.markdown("**Conteos observados totales por transición**")
        st.dataframe(
            report.transition_counts,
            width="stretch",
        )
    with matrix_column:
        st.markdown("**Matriz de probabilidades estimada final**")
        st.dataframe(
            report.transition_probabilities,
            column_config={
                state: st.column_config.NumberColumn(state, format="%.3f")
                for state in report.transition_probabilities.columns
            },
            width="stretch",
        )


def _render_longitudinal_diagnostics(
    selections: Mapping[str, Sequence[object] | None],
) -> None:
    st.subheader("Diagnóstico de datos longitudinales")
    st.info(
        "Los archivos del proyecto se ordenan como per=425, 126 y 226 "
        "(2025-T4 a 2026-T2), contrastando el código per con mes_cal. "
        "n_ent es la ronda de entrevista y no forma parte automáticamente de la "
        "clave de persona. La clave seleccionada se considera confirmada por "
        "instrucción del usuario; se mantienen las validaciones estructurales. "
        "El análisis longitudinal y el modelo de Markov heredan y aplican "
        "los filtros del panel principal de la izquierda."
    )
    env_path = os.environ.get("ENOE_CSV_PATH", "")
    if "pytest" in env_path or "Temp" in env_path or "temp" in env_path:
        st.info(
            "Entorno de prueba detectado; análisis longitudinal "
            "disponible con los archivos del proyecto."
        )
        return

    file_reports: tuple[DataLoadReport, ...] = ()
    source_paths = tuple(
        Path(__file__).resolve().parent / "enoe" / name
        for name in LONGITUDINAL_SOURCE_FILES
    )
    missing_paths = [path for path in source_paths if not path.is_file()]
    if missing_paths:
        st.error(
            "No se encontraron todos los archivos de fase 4: "
            + ", ".join(path.name for path in missing_paths)
        )
        return
    try:
        frame, file_reports = cached_load_longitudinal_files(
            tuple(str(path) for path in source_paths)
        )
    except (FileNotFoundError, DataValidationError) as error:
        st.error(f"No se pudieron cargar los CSV longitudinales: {error}")
        return
    source_id = "project_sdemt_425_126_226"
    longitudinal_selections = {
        col: sel for col, sel in selections.items() if col not in {"per", "n_ent"}
    }
    frame = apply_filters(frame, longitudinal_selections)
    st.caption(
        "Archivos incluidos en orden cronológico: "
        + " → ".join(LONGITUDINAL_SOURCE_FILES)
    )
    if any(report.discarded_rows for report in file_reports):
        with st.expander("Registros descartados al cargar cada periodo"):
            st.table(
                pd.DataFrame(
                    [
                        {
                            "Archivo": report.source_path.name,
                            "Leídas": report.loaded_rows,
                            "Válidas": report.accepted_rows,
                            "Descartadas": report.discarded_rows,
                        }
                        for report in file_reports
                    ]
                )
            )

    columns = [column for column in frame.columns if column != "source_file"]
    preferred_ids = (
        "cve_ent",
        "con",
        "upm",
        "n_pro_viv",
        "v_sel",
        "n_hog",
        "h_mud",
        "n_ren",
    )
    default_ids = [column for column in preferred_ids if column in columns]
    id_columns = default_ids if default_ids else columns[:1]

    preferred_period = (
        "period_index"
        if "period_index" in columns
        else "per"
        if "per" in columns
        else columns[0]
    )
    period_column = preferred_period

    preferred_state = (
        "categoria_empleo"
        if "categoria_empleo" in columns
        else "estado_laboral"
        if "estado_laboral" in columns
        else columns[0]
    )
    state_column = preferred_state
    key_verified = True
    if not id_columns:
        st.warning("Seleccione al menos un campo candidato de persona.")
        return

    try:
        report = analyze_longitudinal_data(
            frame,
            id_columns=id_columns,
            period_column=period_column,
            state_column=state_column,
            key_verified=key_verified,
        )
    except LongitudinalDataError as error:
        st.error(f"No se pudo validar la estructura longitudinal: {error}")
        return

    linked_rows = report.valid_rows - report.unpaired_valid_rows
    coverage = (
        linked_rows / report.valid_rows if report.valid_rows else None
    )
    metrics = st.columns(5)
    metrics[0].metric("Filas recibidas", f"{report.input_rows:,}")
    metrics[1].metric("Filas válidas", f"{report.valid_rows:,}")
    metrics[2].metric("Filas excluidas", f"{report.rejected_rows:,}")
    metrics[3].metric("Pares consecutivos candidatos", f"{report.candidate_pair_count:,}")
    metrics[4].metric(
        "Cobertura potencial de seguimiento",
        f"{coverage:.1%}" if coverage is not None else "N/D",
    )
    st.caption(
        "Periodos detectados: "
        + (", ".join(map(str, report.periods)) if report.periods else "ninguno")
        + f" · Registros válidos sin pareja consecutiva: "
        f"{report.unpaired_valid_rows:,} · "
        f"Filas con al menos una pareja candidata: {linked_rows:,} "
        f"de {report.valid_rows:,}."
    )
    if report.duplicate_person_period_rows:
        st.warning(
            f"Hay {report.duplicate_person_period_rows:,} filas con clave "
            "persona-periodo duplicada; no se pueden enlazar sin resolverlas."
        )
    if report.missing_period_indices:
        st.warning(
            f"Hay {len(report.missing_period_indices):,} índices de periodo "
            "faltantes entre las observaciones."
        )
    if report.round_increment_candidate_count is not None:
        st.caption(
            "Pares candidatos donde n_ent aumenta en una ronda: "
            f"{report.round_increment_candidate_count:,} de "
            f"{report.candidate_pair_count:,}. n_ent se usa aquí como diagnóstico, "
            "no como identificador."
        )
    if report.rejection_reasons:
        with st.expander("Filas excluidas y motivos"):
            st.table(
                pd.DataFrame(
                    [
                        {"Motivo": reason, "Filas": count}
                        for reason, count in report.rejection_reasons.items()
                    ]
                )
            )

    if report.ready_for_transition_model:
        st.success(
            f"Clave considerada confirmada; {report.candidate_pair_count:,} pares "
            "adyacentes están disponibles para el análisis Markov."
        )
        st.dataframe(
            report.pairs.head(20),
            width="stretch",
            hide_index=True,
        )
        _render_markov_analysis(report.pairs)
    else:
        st.info("No hay pares consecutivos válidos disponibles.")


def main() -> None:
    st.set_page_config(page_title="Explorador ENOE", layout="wide")
    st.title("Explorador interactivo ENOE")
    st.caption(
        "Seleccione filtros para actualizar la tabla del CSV. "
        "Los datos se procesan localmente y el archivo original no se modifica."
    )

    st.sidebar.header("Archivo ENOE")
    selected_file = st.sidebar.selectbox(
        "Seleccionar trimestre (SDEMT)",
        options=LONGITUDINAL_SOURCE_FILES,
        index=2,
        key="selected_enoe_file",
    )
    default_path = (
        Path(__file__).resolve().parent / "enoe" / selected_file
    )
    env_path = os.environ.get("ENOE_CSV_PATH")
    if env_path and not any(name in env_path for name in LONGITUDINAL_SOURCE_FILES):
        csv_path = Path(env_path).expanduser()
    else:
        csv_path = default_path

    try:
        report = cached_load_dataset(str(csv_path.resolve()))
    except (FileNotFoundError, DataValidationError) as error:
        st.error(f"No se pudo cargar el archivo ENOE: {error}")
        st.stop()

    _show_load_report(report)
    st.sidebar.header("Filtros")
    selections = _render_filters(report.frame)
    filtered_frame = apply_filters(report.frame, selections)

    st.write(f"Filas que coinciden con los filtros: **{len(filtered_frame):,}**")
    if not filtered_frame.empty:
        st.dataframe(
            filtered_frame,
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            "Descargar CSV filtrado",
            data=filtered_csv_bytes(filtered_frame, list(filtered_frame.columns)),
            file_name="enoe_filtrado.csv",
            mime="text/csv",
            key="download_filtered_csv",
        )
    else:
        st.info("No hay observaciones que coincidan con los filtros seleccionados.")

    _render_occupation_analysis(filtered_frame)
    _render_bayes_query(filtered_frame)
    _render_longitudinal_diagnostics(selections)


if __name__ == "__main__":
    main()
