"""Serialización de subconjuntos filtrados a CSV."""

from collections.abc import Sequence

import pandas as pd


def filtered_csv_bytes(
    frame: pd.DataFrame, columns: Sequence[str]
) -> bytes:
    """Serializa las columnas elegidas de un subconjunto sin modificarlo."""
    selected_columns = list(columns)
    if not selected_columns:
        raise ValueError("Seleccione al menos una columna para exportar.")
    if len(set(selected_columns)) != len(selected_columns):
        raise ValueError("No se pueden repetir columnas en la exportación.")

    missing_columns = sorted(set(selected_columns).difference(frame.columns))
    if missing_columns:
        raise ValueError("No existen estas columnas: " + ", ".join(missing_columns))

    return frame.loc[:, selected_columns].to_csv(index=False).encode("utf-8-sig")
