import math

import pandas as pd
import pytest

from enoe_app.metrics import occupation_by_group, occupation_totals


def test_occupation_totals_calculates_simple_and_weighted_probabilities(sample_frame):
    totals = occupation_totals(sample_frame)

    assert totals.observations == 4
    assert totals.occupied == 2
    assert totals.total_weight == 7.0
    assert totals.occupied_weight == 5.0
    assert totals.probability_simple == 0.5
    assert totals.probability_weighted == pytest.approx(5 / 7)


def test_occupation_by_group_returns_joint_and_conditional_probabilities(
    sample_frame,
):
    summary = occupation_by_group(sample_frame, "grupo_edad").set_index("grupo_edad")

    adult = summary.loc["Adulto"]
    assert adult["observaciones"] == 3
    assert adult["ocupados"] == 2
    assert adult["peso_total_fac_tri"] == 6.0
    assert adult["ocupados_ponderados"] == 5.0
    assert adult["probabilidad_conjunta_simple"] == 0.5
    assert adult["probabilidad_conjunta_ponderada"] == pytest.approx(5 / 7)
    assert adult["probabilidad_condicional_simple"] == pytest.approx(2 / 3)
    assert adult["probabilidad_condicional_ponderada"] == pytest.approx(5 / 6)

    young = summary.loc["Joven"]
    assert young["probabilidad_condicional_simple"] == 0
    assert young["probabilidad_condicional_ponderada"] == 0


def test_empty_frame_returns_unavailable_probabilities():
    empty = pd.DataFrame({"ocupado": [], "fac_tri": [], "grupo_edad": []})

    totals = occupation_totals(empty)
    summary = occupation_by_group(empty, "grupo_edad")

    assert totals.observations == 0
    assert totals.probability_simple is None
    assert totals.probability_weighted is None
    assert summary.empty


@pytest.mark.parametrize("weight", [0, -1, math.inf, math.nan])
def test_occupation_totals_rejects_invalid_expansion_weights(weight):
    frame = pd.DataFrame({"ocupado": [1], "fac_tri": [weight]})

    with pytest.raises(ValueError, match="fac_tri"):
        occupation_totals(frame)
