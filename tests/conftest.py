"""Fixtures compartidos para las pruebas de la aplicación ENOE."""

import pandas as pd
import pytest


@pytest.fixture
def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cve_ent": [1, 1, 14, 14],
            "n_ent": [1, 1, 2, 2],
            "per": [226, 226, 226, 226],
            "period_index": [8104, 8104, 8104, 8104],
            "grupo_edad": ["Adulto", "Joven", "Adulto", "Adulto"],
            "sexo_label": ["Mujer", "Hombre", "Mujer", None],
            "cve_mun": [1, 1, 2, 2],
            "ocupado": [1, 0, 1, 0],
            "categoria_empleo": [
                "Empleador",
                "No aplica / no ocupado",
                "Cuenta propia",
                "No aplica / no ocupado",
            ],
            "fac_tri": [2.0, 1.0, 3.0, 1.0],
        }
    )
