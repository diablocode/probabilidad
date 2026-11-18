"""Composición condicional para consultas tipo Bayes."""

from dataclasses import dataclass
from collections.abc import Sequence

import pandas as pd

from enoe_app.filters import MISSING_OPTION
from enoe_app.metrics import occupation_totals


@dataclass(frozen=True)
class ConditionalComposition:
    """Distribución por dimensiones dada una evidencia seleccionada."""

    evidence_count: int
    evidence_weight: float
    groups: pd.DataFrame


def conditional_composition(
    frame: pd.DataFrame,
    evidence_column: str,
    evidence_value: object,
    dimensions: Sequence[str],
) -> ConditionalComposition:
    """Calcula P(dimensiones | evidencia), en versiones simple y ponderada."""
    selected_dimensions = list(dimensions)
    if not selected_dimensions:
        raise ValueError("Seleccione al menos una variable para describir.")
    if len(set(selected_dimensions)) != len(selected_dimensions):
        raise ValueError("No se pueden repetir variables de descripción.")
    if evidence_column in selected_dimensions:
        raise ValueError("La variable de evidencia no puede describirse a sí misma.")

    required = {evidence_column, *selected_dimensions}
    missing_columns = sorted(required.difference(frame.columns))
    if missing_columns:
        raise ValueError(
            "Faltan columnas requeridas: " + ", ".join(missing_columns)
        )

    evidence = frame[evidence_column]
    evidence_mask = (
        evidence.isna()
        if evidence_value == MISSING_OPTION
        else evidence.eq(evidence_value)
    )
    selected = frame.loc[evidence_mask].copy()
    totals = occupation_totals(selected)

    result_columns = [
        *selected_dimensions,
        "observaciones",
        "peso_fac_tri",
        "probabilidad_simple",
        "probabilidad_ponderada",
    ]
    if selected.empty:
        return ConditionalComposition(
            evidence_count=0,
            evidence_weight=0.0,
            groups=pd.DataFrame(columns=result_columns),
        )

    grouped_data = selected[selected_dimensions].copy()
    for column in selected_dimensions:
        grouped_data[column] = grouped_data[column].astype("object").where(
            grouped_data[column].notna(), MISSING_OPTION
        )
    grouped_data["_fac_tri"] = pd.to_numeric(selected["fac_tri"])
    grouped = (
        grouped_data.groupby(
            selected_dimensions, sort=False, observed=True, dropna=False
        )
        .agg(
            observaciones=("_fac_tri", "size"),
            peso_fac_tri=("_fac_tri", "sum"),
        )
        .reset_index()
    )
    grouped["probabilidad_simple"] = (
        grouped["observaciones"] / totals.observations
    )
    grouped["probabilidad_ponderada"] = (
        grouped["peso_fac_tri"] / totals.total_weight
    )

    return ConditionalComposition(
        evidence_count=totals.observations,
        evidence_weight=totals.total_weight,
        groups=grouped[result_columns],
    )
