import pandas as pd
import pytest

from enoe_app.longitudinal import (
    LongitudinalDataError,
    analyze_longitudinal_data,
)


@pytest.fixture
def linked_frame():
    return pd.DataFrame(
        {
            "persona": ["a", "b", "a", "b"],
            "n_ent": [1, 1, 2, 2],
            "period_index": [1, 1, 2, 2],
            "categoria_empleo": [
                "No aplica / no ocupado",
                "Empleador",
                "Trabajador subordinado y remunerado",
                "Cuenta propia",
            ],
            "fac_tri": [1.0, 2.0, 1.1, 2.1],
        }
    )


def test_candidate_pairs_are_not_exposed_until_key_is_verified(linked_frame):
    report = analyze_longitudinal_data(
        linked_frame, ["persona"], "period_index", "categoria_empleo"
    )

    assert report.candidate_pair_count == 2
    assert report.round_increment_candidate_count == 2
    assert report.valid_rows == 4
    assert report.unpaired_valid_rows == 0
    assert not report.key_verified
    assert not report.ready_for_transition_model
    assert report.pairs.empty


def test_verified_key_builds_only_adjacent_normalized_state_pairs(linked_frame):
    report = analyze_longitudinal_data(
        linked_frame,
        ["persona"],
        "period_index",
        "categoria_empleo",
        key_verified=True,
    )

    assert report.ready_for_transition_model
    assert len(report.pairs) == 2
    assert report.pairs.loc[0, "estado_origen"] == "No ocupado"
    assert report.pairs.loc[0, "estado_destino"] == "Subordinado"
    assert report.pairs.loc[0, "periodo_origen"] == 1
    assert report.pairs.loc[0, "periodo_destino"] == 2
    assert report.pairs.loc[0, "n_ent_origen"] == 1
    assert report.pairs.loc[0, "n_ent_destino"] == 2


def test_duplicate_person_period_rows_block_pair_creation():
    frame = pd.DataFrame(
        {
            "persona": ["a", "a", "a"],
            "period_index": [1, 1, 2],
            "estado": ["Empleador", "Sin pago", "Subordinado"],
            "fac_tri": [1.0, 1.0, 1.0],
        }
    )

    report = analyze_longitudinal_data(
        frame, ["persona"], "period_index", "estado", key_verified=True
    )

    assert report.duplicate_person_period_rows == 2
    assert report.rejection_reasons["Clave persona-periodo duplicada"] == 2
    assert not report.ready_for_transition_model
    assert report.pairs.empty


def test_period_gaps_are_reported_and_do_not_create_nonadjacent_pairs():
    frame = pd.DataFrame(
        {
            "persona": ["a", "a"],
            "period_index": [1, 3],
            "estado": ["Empleador", "Sin pago"],
            "fac_tri": [1.0, 1.0],
        }
    )

    report = analyze_longitudinal_data(
        frame, ["persona"], "period_index", "estado", key_verified=True
    )

    assert report.periods == (1, 3)
    assert report.missing_period_indices == (2,)
    assert report.candidate_pair_count == 0
    assert not report.ready_for_transition_model


def test_bad_identifiers_periods_states_and_weights_are_reported():
    frame = pd.DataFrame(
        {
            "persona": [None, "bad-period", "missing-state", "unknown", "bad-weight"],
            "period_index": [1, "x", 1, 1, 1],
            "estado": ["Subordinado", "Empleador", None, "Otro", "Sin pago"],
            "fac_tri": [1.0, 1.0, 1.0, 1.0, 0.0],
        }
    )

    report = analyze_longitudinal_data(
        frame, ["persona"], "period_index", "estado"
    )

    assert report.valid_rows == 0
    assert report.rejection_reasons == {
        "Identificador faltante": 1,
        "Periodo no entero o inválido": 1,
        "Estado faltante": 1,
        "Estado laboral desconocido": 1,
        "fac_tri inválido": 1,
    }


def test_current_single_period_structure_does_not_make_pairs(linked_frame):
    frame = linked_frame.loc[linked_frame["period_index"].eq(1)].copy()

    report = analyze_longitudinal_data(
        frame, ["persona"], "period_index", "categoria_empleo", key_verified=True
    )

    assert report.periods == (1,)
    assert report.candidate_pair_count == 0
    assert not report.ready_for_transition_model


def test_longitudinal_schema_and_key_configuration_are_validated(linked_frame):
    with pytest.raises(LongitudinalDataError, match="al menos un campo"):
        analyze_longitudinal_data(linked_frame, [], "period_index", "categoria_empleo")

    with pytest.raises(LongitudinalDataError, match="distintos"):
        analyze_longitudinal_data(
            linked_frame, ["period_index"], "period_index", "categoria_empleo"
        )

    with pytest.raises(LongitudinalDataError, match="Faltan columnas requeridas"):
        analyze_longitudinal_data(
            linked_frame, ["persona"], "no_period", "categoria_empleo"
        )
