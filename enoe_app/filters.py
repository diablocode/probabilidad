"""Opciones dinámicas y aplicación de filtros a las observaciones."""

from collections.abc import Mapping, Sequence

import pandas as pd


MISSING_OPTION = "(Valor faltante)"
FILTER_COLUMNS = (
    "cve_ent",
    "grupo_edad",
    "sexo_label",
    "cve_mun",
    "ocupado",
    "categoria_empleo",
)


def get_filter_options(frame: pd.DataFrame, column: str) -> list[object]:
    """Devuelve los valores distintos de una columna e incluye valores faltantes."""
    values = frame[column].dropna().unique().tolist()
    values.sort(key=lambda value: str(value))
    if frame[column].isna().any():
        values.append(MISSING_OPTION)
    return values


def apply_filters(
    frame: pd.DataFrame,
    selections: Mapping[str, Sequence[object] | None],
) -> pd.DataFrame:
    """Devuelve una copia con todos los filtros seleccionados aplicados."""
    mask = pd.Series(True, index=frame.index)
    for column, selected in selections.items():
        if selected is None or column not in frame.columns:
            continue
        selected_values = [value for value in selected if value != MISSING_OPTION]
        column_mask = frame[column].isin(selected_values)
        if MISSING_OPTION in selected:
            column_mask |= frame[column].isna()
        mask &= column_mask
    return frame.loc[mask].copy()
