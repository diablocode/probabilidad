import pandas as pd
import pytest

from enoe_app.bayes import conditional_composition
from enoe_app.filters import MISSING_OPTION


@pytest.fixture
def employer_frame():
    return pd.DataFrame(
        {
            "categoria_empleo": [
                "Empleador",
                "Empleador",
                "Empleador",
                "Otra categoría",
            ],
            "sexo_label": ["Mujer", "Mujer", "Hombre", "Mujer"],
            "grupo_edad": ["Adulto", "Adulto", "Joven", "Adulto"],
            "ocupado": [1, 1, 1, 1],
            "fac_tri": [2.0, 3.0, 1.0, 7.0],
        }
    )


def test_conditional_composition_uses_evidence_denominator_and_weights(
    employer_frame,
):
    result = conditional_composition(
        employer_frame,
        evidence_column="categoria_empleo",
        evidence_value="Empleador",
        dimensions=["sexo_label", "grupo_edad"],
    )
    adult_women = result.groups.set_index(["sexo_label", "grupo_edad"]).loc[
        ("Mujer", "Adulto")
    ]

    assert result.evidence_count == 3
    assert result.evidence_weight == 6.0
    assert adult_women["observaciones"] == 2
    assert adult_women["peso_fac_tri"] == 5.0
    assert adult_women["probabilidad_simple"] == pytest.approx(2 / 3)
    assert adult_women["probabilidad_ponderada"] == pytest.approx(5 / 6)
    assert result.groups["probabilidad_simple"].sum() == pytest.approx(1.0)
    assert result.groups["probabilidad_ponderada"].sum() == pytest.approx(1.0)


def test_conditional_composition_keeps_missing_dimension_as_group():
    frame = pd.DataFrame(
        {
            "categoria_empleo": ["Empleador", "Empleador"],
            "sexo_label": [None, "Mujer"],
            "ocupado": [1, 1],
            "fac_tri": [2.0, 1.0],
        }
    )

    result = conditional_composition(
        frame, "categoria_empleo", "Empleador", ["sexo_label"]
    )

    assert MISSING_OPTION in result.groups["sexo_label"].tolist()
    assert result.groups["probabilidad_simple"].sum() == pytest.approx(1.0)


def test_conditional_composition_returns_empty_distribution_for_absent_evidence(
    employer_frame,
):
    result = conditional_composition(
        employer_frame,
        evidence_column="categoria_empleo",
        evidence_value="No observado",
        dimensions=["sexo_label"],
    )

    assert result.evidence_count == 0
    assert result.evidence_weight == 0.0
    assert result.groups.empty


def test_conditional_composition_can_select_missing_evidence(employer_frame):
    frame = employer_frame.copy()
    frame.loc[0, "categoria_empleo"] = None

    result = conditional_composition(
        frame,
        evidence_column="categoria_empleo",
        evidence_value=MISSING_OPTION,
        dimensions=["sexo_label"],
    )

    assert result.evidence_count == 1
    assert result.groups.iloc[0]["sexo_label"] == "Mujer"


@pytest.mark.parametrize(
    "dimensions",
    [[], ["sexo_label", "sexo_label"], ["categoria_empleo"]],
)
def test_conditional_composition_validates_dimensions(employer_frame, dimensions):
    with pytest.raises(ValueError):
        conditional_composition(
            employer_frame,
            evidence_column="categoria_empleo",
            evidence_value="Empleador",
            dimensions=dimensions,
        )
