"""Diagnóstico de estructura y enlaces candidatos entre periodos ENOE."""

from collections.abc import Sequence
from dataclasses import dataclass
import math

import pandas as pd


CANONICAL_STATES = (
    "Subordinado",
    "Cuenta propia",
    "Empleador",
    "Sin pago",
    "No ocupado",
)

ENOE_STATE_MAPPING = {
    "Trabajador subordinado y remunerado": "Subordinado",
    "Trabajador por cuenta propia": "Cuenta propia",
    "Empleador": "Empleador",
    "Trabajador sin pago": "Sin pago",
    "No aplica / no ocupado": "No ocupado",
}

PAIR_COLUMNS = (
    "periodo_origen",
    "periodo_destino",
    "estado_origen",
    "estado_destino",
    "fac_tri_origen",
    "fac_tri_destino",
)
ROUND_PAIR_COLUMNS = ("n_ent_origen", "n_ent_destino")


class LongitudinalDataError(ValueError):
    """Error legible en la configuración o esquema longitudinal."""


@dataclass(frozen=True)
class LongitudinalReport:
    """Diagnóstico; los pares solo se entregan si la clave fue verificada."""

    input_rows: int
    valid_rows: int
    rejected_rows: int
    rejection_reasons: dict[str, int]
    duplicate_person_period_rows: int
    periods: tuple[int, ...]
    missing_period_indices: tuple[int, ...]
    candidate_pair_count: int
    round_increment_candidate_count: int | None
    unpaired_valid_rows: int
    key_verified: bool
    ready_for_transition_model: bool
    pairs: pd.DataFrame


def _normalize_states(values: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    raw = values.astype("string").str.strip()
    missing = raw.isna() | raw.eq("").fillna(False)
    mapped = raw.map(ENOE_STATE_MAPPING)
    canonical = raw.isin(CANONICAL_STATES)
    normalized = mapped.where(mapped.notna(), raw.where(canonical, pd.NA))
    unknown = ~missing & normalized.isna()
    return normalized, missing, unknown


def _empty_pairs(
    id_columns: Sequence[str], round_columns: Sequence[str] = ()
) -> pd.DataFrame:
    return pd.DataFrame(columns=[*id_columns, *PAIR_COLUMNS, *round_columns])


def analyze_longitudinal_data(
    frame: pd.DataFrame,
    id_columns: Sequence[str],
    period_column: str,
    state_column: str,
    *,
    key_verified: bool = False,
) -> LongitudinalReport:
    """Valida persona-periodo y cuenta pares adyacentes sin inferir identidad."""
    identifiers = list(id_columns)
    if not identifiers:
        raise LongitudinalDataError("Seleccione al menos un campo identificador.")
    if len(set(identifiers)) != len(identifiers):
        raise LongitudinalDataError("No se pueden repetir campos identificadores.")
    if period_column in identifiers or state_column in identifiers:
        raise LongitudinalDataError(
            "Los campos identificadores deben ser distintos del periodo y el estado."
        )
    if period_column == state_column:
        raise LongitudinalDataError("Periodo y estado deben ser campos distintos.")

    required = {
        *identifiers,
        period_column,
        state_column,
        "fac_tri",
    }
    missing_columns = sorted(required.difference(frame.columns))
    if missing_columns:
        raise LongitudinalDataError(
            "Faltan columnas requeridas: " + ", ".join(missing_columns)
        )
    if frame.empty:
        raise LongitudinalDataError("El archivo longitudinal no tiene observaciones.")

    data = frame.reset_index(drop=True).copy()
    periods_numeric = pd.to_numeric(data[period_column], errors="coerce")
    invalid_period = (
        periods_numeric.isna()
        | periods_numeric.map(
            lambda value: not math.isfinite(value)
            if pd.notna(value)
            else True
        )
        | periods_numeric.mod(1).ne(0)
    ).fillna(True)
    identifiers_as_text = data[identifiers].astype("string")
    missing_identifier = (
        identifiers_as_text.isna()
        | identifiers_as_text.apply(lambda column: column.str.strip().eq(""))
    ).fillna(False).any(axis=1)
    normalized_states, missing_state, unknown_state = _normalize_states(
        data[state_column]
    )
    weights = pd.to_numeric(data["fac_tri"], errors="coerce")
    invalid_weight = weights.map(
        lambda value: not math.isfinite(value) or value <= 0
        if pd.notna(value)
        else True
    )

    reasons = pd.Series("", index=data.index, dtype="object")
    validations = (
        ("Identificador faltante", missing_identifier),
        ("Periodo no entero o inválido", invalid_period),
        ("Estado faltante", missing_state),
        ("Estado laboral desconocido", unknown_state),
        ("fac_tri inválido", invalid_weight),
    )
    for reason, invalid_rows in validations:
        first_invalid = invalid_rows & reasons.eq("")
        reasons.loc[first_invalid] = reason

    eligible = reasons.eq("")
    duplicate_frame = data.loc[eligible, identifiers].copy()
    duplicate_frame["_period_index"] = (
        periods_numeric.loc[eligible].astype("int64")
    )
    duplicate_mask = duplicate_frame.duplicated(keep=False)
    duplicate_indices = duplicate_frame.index[duplicate_mask]
    reasons.loc[duplicate_indices] = "Clave persona-periodo duplicada"

    valid_mask = reasons.eq("")
    rejection_reasons = {
        str(reason): int(count)
        for reason, count in reasons.loc[~valid_mask].value_counts().items()
    }
    prepared = data.loc[valid_mask, identifiers].copy()
    prepared["_period_index"] = periods_numeric.loc[valid_mask].astype("int64")
    prepared["_state"] = normalized_states.loc[valid_mask].astype("string")
    prepared["_fac_tri"] = weights.loc[valid_mask].astype("float64")
    prepared["_row_id"] = prepared.index
    has_rounds = "n_ent" in data.columns and "n_ent" not in identifiers
    if has_rounds:
        prepared["_n_ent"] = pd.to_numeric(data.loc[valid_mask, "n_ent"], errors="coerce")
    round_columns = ROUND_PAIR_COLUMNS if has_rounds else ()

    periods = tuple(
        sorted(int(value) for value in prepared["_period_index"].unique())
    )
    missing_period_indices = tuple(
        missing
        for left, right in zip(periods, periods[1:])
        for missing in range(left + 1, right)
    )

    candidate_pairs = []
    linked_row_ids: set[int] = set()
    period_set = set(periods)
    for period in periods:
        if period + 1 not in period_set:
            continue
        origin = prepared.loc[
            prepared["_period_index"].eq(period),
            [
                *identifiers,
                "_row_id",
                "_state",
                "_fac_tri",
                *(["_n_ent"] if has_rounds else []),
            ],
        ].rename(
            columns={
                "_row_id": "_row_id_origen",
                "_state": "estado_origen",
                "_fac_tri": "fac_tri_origen",
                **({"_n_ent": "n_ent_origen"} if has_rounds else {}),
            }
        )
        destination = prepared.loc[
            prepared["_period_index"].eq(period + 1),
            [
                *identifiers,
                "_row_id",
                "_state",
                "_fac_tri",
                *(["_n_ent"] if has_rounds else []),
            ],
        ].rename(
            columns={
                "_row_id": "_row_id_destino",
                "_state": "estado_destino",
                "_fac_tri": "fac_tri_destino",
                **({"_n_ent": "n_ent_destino"} if has_rounds else {}),
            }
        )
        joined = origin.merge(
            destination,
            on=identifiers,
            how="inner",
            validate="one_to_one",
        )
        if joined.empty:
            continue
        joined["periodo_origen"] = period
        joined["periodo_destino"] = period + 1
        linked_row_ids.update(joined["_row_id_origen"].tolist())
        linked_row_ids.update(joined["_row_id_destino"].tolist())
        candidate_pairs.append(joined)

    candidate_pair_count = sum(len(pairs) for pairs in candidate_pairs)
    if candidate_pairs:
        all_candidate_pairs = pd.concat(candidate_pairs, ignore_index=True)
        all_candidate_pairs = all_candidate_pairs[
            [*identifiers, *PAIR_COLUMNS, *round_columns]
        ]
    else:
        all_candidate_pairs = _empty_pairs(identifiers, round_columns)

    duplicate_count = int((reasons == "Clave persona-periodo duplicada").sum())
    round_increment_candidate_count = (
        int(
            all_candidate_pairs["n_ent_destino"]
            .sub(all_candidate_pairs["n_ent_origen"])
            .eq(1)
            .sum()
        )
        if has_rounds
        else None
    )
    ready = bool(
        key_verified and duplicate_count == 0 and candidate_pair_count > 0
    )
    verified_pairs = (
        all_candidate_pairs if ready else _empty_pairs(identifiers, round_columns)
    )

    return LongitudinalReport(
        input_rows=len(data),
        valid_rows=int(valid_mask.sum()),
        rejected_rows=int((~valid_mask).sum()),
        rejection_reasons=rejection_reasons,
        duplicate_person_period_rows=duplicate_count,
        periods=periods,
        missing_period_indices=missing_period_indices,
        candidate_pair_count=candidate_pair_count,
        round_increment_candidate_count=round_increment_candidate_count,
        unpaired_valid_rows=int(len(prepared) - len(linked_row_ids)),
        key_verified=key_verified,
        ready_for_transition_model=ready,
        pairs=verified_pairs,
    )
