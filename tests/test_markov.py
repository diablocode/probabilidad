import math

import pandas as pd
import pytest

from enoe_app.markov import (
    MARKOV_STATES,
    MarkovDataError,
    estimate_markov_chain,
)


def _pairs(transitions):
    return pd.DataFrame(
        [
            {
                "periodo_origen": 1,
                "periodo_destino": 2,
                "estado_origen": origin,
                "estado_destino": destination,
                "fac_tri_origen": weight,
            }
            for origin, destination, weight in transitions
        ]
    )


def test_five_state_cycle_has_uniform_stationarity_and_period_five():
    pairs = _pairs(
        [
            (state, MARKOV_STATES[(index + 1) % len(MARKOV_STATES)], 1.0)
            for index, state in enumerate(MARKOV_STATES)
        ]
    )

    report = estimate_markov_chain(pairs)

    assert report.irreducible is True
    assert report.aperiodic is False
    assert report.ergodic is False
    assert report.communicating_classes[0].period == 5
    assert report.stationary_distribution is not None
    assert report.stationary_distribution.tolist() == pytest.approx(
        [0.2] * len(MARKOV_STATES)
    )
    assert report.mean_first_passage is not None
    assert report.mean_first_passage.loc["No ocupado", "Subordinado"] == 1
    assert report.periods == (1, 2)


def test_five_state_chain_with_self_loops_is_aperiodic_and_ergodic():
    pairs = _pairs(
        [
            transition
            for index, state in enumerate(MARKOV_STATES)
            for transition in (
                (state, state, 1.0),
                (
                    state,
                    MARKOV_STATES[(index + 1) % len(MARKOV_STATES)],
                    1.0,
                ),
            )
        ]
    )

    report = estimate_markov_chain(pairs)

    assert report.irreducible is True
    assert report.aperiodic is True
    assert report.ergodic is True
    assert report.communicating_classes[0].period == 1
    assert report.stationary_distribution is not None
    assert sum(report.stationary_distribution) == pytest.approx(1.0)


def test_weighted_matrix_uses_origin_expansion_factor():
    pairs = _pairs(
        [
            ("Subordinado", "Subordinado", 1.0),
            ("Subordinado", "Empleador", 3.0),
            ("Cuenta propia", "Cuenta propia", 1.0),
            ("Empleador", "Empleador", 1.0),
            ("Sin pago", "Sin pago", 1.0),
            ("No ocupado", "No ocupado", 1.0),
        ]
    )

    simple = estimate_markov_chain(pairs)
    weighted = estimate_markov_chain(pairs, weighting="weighted")

    assert simple.transition_counts.loc["Subordinado", "Subordinado"] == 1
    assert simple.transition_counts.loc["Subordinado", "Empleador"] == 1
    assert simple.transition_probabilities.loc[
        "Subordinado", "Subordinado"
    ] == pytest.approx(0.5)
    assert weighted.transition_weight_totals.loc[
        "Subordinado", "Empleador"
    ] == pytest.approx(3.0)
    assert weighted.transition_probabilities.loc[
        "Subordinado", "Subordinado"
    ] == pytest.approx(0.25)
    assert weighted.transition_probabilities.loc[
        "Subordinado", "Empleador"
    ] == pytest.approx(0.75)


def test_reducible_chain_reports_multiple_stationary_classes_and_infinite_hitting():
    pairs = _pairs(
        [
            ("Subordinado", "Subordinado", 1.0),
            ("Cuenta propia", "Subordinado", 1.0),
            ("Cuenta propia", "Empleador", 1.0),
            ("Empleador", "Empleador", 1.0),
            ("Sin pago", "Sin pago", 1.0),
            ("No ocupado", "Subordinado", 1.0),
        ]
    )

    report = estimate_markov_chain(pairs)

    assert report.irreducible is False
    assert report.ergodic is False
    assert report.stationary_distribution is None
    assert "no hay una distribución estacionaria única" in report.stationary_status.lower()
    assert report.mean_first_passage is not None
    assert report.mean_first_passage.loc["No ocupado", "Subordinado"] == 1
    assert math.isinf(
        report.mean_first_passage.loc["Cuenta propia", "Subordinado"]
    )
    assert math.isinf(report.mean_first_passage.loc["Sin pago", "Empleador"])


def test_missing_outgoing_states_are_not_filled_with_zero_probabilities():
    report = estimate_markov_chain(
        _pairs([("No ocupado", "Subordinado", 1.0)])
    )

    assert report.states_without_outgoing == (
        "Subordinado",
        "Cuenta propia",
        "Empleador",
        "Sin pago",
    )
    assert math.isnan(
        report.transition_probabilities.loc["Subordinado", "No ocupado"]
    )
    assert report.irreducible is None
    assert report.aperiodic is None
    assert report.ergodic is None
    assert report.stationary_distribution is None
    assert report.mean_first_passage is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"estado_origen": "Otra categoría"}, "estados laborales"),
        ({"fac_tri_origen": 0.0}, "positivo y finito"),
        ({"periodo_destino": 3}, "periodos enteros consecutivos"),
    ],
)
def test_invalid_pairs_are_rejected(changes, message):
    pairs = _pairs([("No ocupado", "Subordinado", 1.0)])
    for column, value in changes.items():
        pairs.loc[0, column] = value

    with pytest.raises(MarkovDataError, match=message):
        estimate_markov_chain(pairs)


def test_empty_pairs_and_unknown_weighting_are_rejected():
    with pytest.raises(MarkovDataError, match="No hay pares"):
        estimate_markov_chain(pd.DataFrame())
    with pytest.raises(MarkovDataError, match="ponderación"):
        estimate_markov_chain(
            _pairs([("No ocupado", "Subordinado", 1.0)]),
            weighting="arbitrary",
        )
