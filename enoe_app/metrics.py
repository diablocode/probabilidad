"""Cálculos descriptivos simples y ponderados de ocupación."""

from dataclasses import dataclass
import math

import pandas as pd

from enoe_app.filters import MISSING_OPTION


@dataclass(frozen=True)
class OccupationTotals:
    """Conteos y probabilidades de ocupación para un universo seleccionado."""

    observations: int
    occupied: int
    total_weight: float
    occupied_weight: float
    probability_simple: float | None
    probability_weighted: float | None


GROUP_SUMMARY_COLUMNS = (
    "observaciones",
    "ocupados",
    "peso_total_fac_tri",
    "ocupados_ponderados",
    "probabilidad_conjunta_simple",
    "probabilidad_conjunta_ponderada",
    "probabilidad_condicional_simple",
    "probabilidad_condicional_ponderada",
)


def _validated_measures(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    required = {"ocupado", "fac_tri"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError("Faltan columnas requeridas: " + ", ".join(missing))

    occupied = pd.to_numeric(frame["ocupado"], errors="coerce")
    weights = pd.to_numeric(frame["fac_tri"], errors="coerce")
    if occupied.isna().any() or not occupied.isin((0, 1)).all():
        raise ValueError("'ocupado' debe contener únicamente valores 0 o 1.")
    invalid_weight = weights.map(
        lambda value: not math.isfinite(value) or value <= 0
        if pd.notna(value)
        else True
    )
    if invalid_weight.any():
        raise ValueError("'fac_tri' debe contener valores positivos y finitos.")
    return occupied.astype("int64"), weights.astype("float64")


def occupation_totals(frame: pd.DataFrame) -> OccupationTotals:
    """Calcula probabilidad marginal simple y ponderada de estar ocupado."""
    occupied, weights = _validated_measures(frame)
    observations = len(frame)
    occupied_count = int(occupied.sum())
    total_weight = float(weights.sum())
    occupied_weight = float(weights.loc[occupied.eq(1)].sum())

    return OccupationTotals(
        observations=observations,
        occupied=occupied_count,
        total_weight=total_weight,
        occupied_weight=occupied_weight,
        probability_simple=occupied_count / observations if observations else None,
        probability_weighted=(
            occupied_weight / total_weight if total_weight > 0 else None
        ),
    )


def occupation_by_group(frame: pd.DataFrame, group_by: str) -> pd.DataFrame:
    """Calcula probabilidades conjuntas y condicionales por categoría."""
    if group_by not in frame.columns:
        raise ValueError(f"No existe la columna de agrupación: {group_by}")

    occupied, weights = _validated_measures(frame)
    columns = [group_by, *GROUP_SUMMARY_COLUMNS]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    total_weight = float(weights.sum())
    work = pd.DataFrame(
        {
            group_by: frame[group_by]
            .astype("object")
            .where(frame[group_by].notna(), MISSING_OPTION),
            "_ocupado": occupied,
            "_fac_tri": weights,
            "_ocupados_ponderados": weights.where(occupied.eq(1), 0.0),
        },
        index=frame.index,
    )
    grouped = (
        work.groupby(group_by, sort=False, observed=True, dropna=False)
        .agg(
            observaciones=("_ocupado", "size"),
            ocupados=("_ocupado", "sum"),
            peso_total_fac_tri=("_fac_tri", "sum"),
            ocupados_ponderados=("_ocupados_ponderados", "sum"),
        )
        .reset_index()
    )

    overall_observations = len(frame)
    grouped["probabilidad_conjunta_simple"] = (
        grouped["ocupados"] / overall_observations
    )
    grouped["probabilidad_conjunta_ponderada"] = (
        grouped["ocupados_ponderados"] / total_weight if total_weight > 0 else None
    )
    grouped["probabilidad_condicional_simple"] = (
        grouped["ocupados"] / grouped["observaciones"]
    )
    grouped["probabilidad_condicional_ponderada"] = (
        grouped["ocupados_ponderados"] / grouped["peso_total_fac_tri"]
    )
    return grouped[columns]
