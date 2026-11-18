from hashlib import sha256
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


def test_app_updates_table_after_filter_change(tmp_path, monkeypatch):
    csv_path = tmp_path / "enoe.csv"
    pd.DataFrame(
        {
            "cve_ent": [1, 14],
            "n_ent": [1, 2],
            "per": [226, 226],
            "grupo_edad": ["Adulto", "Joven"],
            "sexo_label": ["Mujer", "Hombre"],
            "cve_mun": [1, 2],
            "ocupado": [1, 0],
            "categoria_empleo": ["Empleador", "No aplica / no ocupado"],
            "fac_tri": [1.0, 1.0],
        }
    ).to_csv(csv_path, index=False)
    monkeypatch.setenv("ENOE_CSV_PATH", str(csv_path))

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(app_path).run()

    assert not app.exception
    assert any("Filas que coinciden con los filtros: **2**" in element.value for element in app.markdown)
    assert app.metric[1].value == "50.00%"
    assert app.metric[2].value == "50.00%"
    assert app.get("vega_lite_chart")

    app.multiselect(key="filter_sexo_label").set_value(["Mujer"]).run()

    assert not app.exception
    assert any("Filas que coinciden con los filtros: **1**" in element.value for element in app.markdown)
    assert app.dataframe[0].value["sexo_label"].tolist() == ["Mujer"]
    assert app.metric[1].value == "100.00%"
    assert app.metric[2].value == "100.00%"

    app.multiselect(key="filter_sexo_label").set_value([]).run()

    assert not app.exception
    assert app.metric[0].value == "0"
    assert app.metric[1].value == "N/D"
    assert app.metric[2].value == "N/D"


def test_app_renders_bayes_query_and_filtered_export(tmp_path, monkeypatch):
    csv_path = tmp_path / "enoe.csv"
    pd.DataFrame(
        {
            "cve_ent": [1, 1, 14, 14],
            "n_ent": [1, 1, 2, 1],
            "per": [226, 226, 226, 226],
            "grupo_edad": ["Adulto", "Adulto", "Joven", "Adulto"],
            "sexo_label": ["Mujer", "Mujer", "Hombre", "Hombre"],
            "cve_mun": [1, 1, 2, 2],
            "ocupado": [1, 1, 1, 1],
            "categoria_empleo": [
                "Empleador",
                "Empleador",
                "Empleador",
                "Otra categoría",
            ],
            "fac_tri": [2.0, 3.0, 1.0, 7.0],
        }
    ).to_csv(csv_path, index=False)
    monkeypatch.setenv("ENOE_CSV_PATH", str(csv_path))

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(app_path).run()

    assert not app.exception
    assert app.get("download_button")
    assert any("Denominador de la evidencia (n)" == metric.label for metric in app.metric)
    assert any(
        "P(Sexo, Grupo de edad | ocupado = Ocupado)." in element.value
        for element in app.caption
    )
    assert "sexo_label" in app.dataframe[0].value.columns
    assert "ocupado" in app.dataframe[0].value.columns


def test_app_longitudinal_diagnostic_treats_key_as_confirmed(
    tmp_path, monkeypatch, sample_frame
):
    base_path = tmp_path / "base.csv"
    sample_frame.to_csv(base_path, index=False)
    monkeypatch.setenv("ENOE_CSV_PATH", str(base_path))

    longitudinal_frame = pd.DataFrame(
        {
            "persona": ["a", "b", "a", "b"],
            "period_index": [1, 1, 2, 2],
            "categoria_empleo": [
                "Empleador",
                "Sin pago",
                "Subordinado",
                "Cuenta propia",
            ],
            "fac_tri": [1.0, 2.0, 1.1, 2.1],
        }
    )
    payload = longitudinal_frame.to_csv(index=False).encode("utf-8")
    upload_id = sha256(payload).hexdigest()[:12]
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(app_path).run()
    app.radio(key="longitudinal_source_mode").set_value("Cargar otro CSV").run()
    app.get("file_uploader")[0].set_value(
        ("longitudinal.csv", payload, "text/csv")
    ).run()

    assert not app.exception
    assert any("Seleccione al menos un campo candidato" in element.value for element in app.warning)

    app.multiselect(key=f"longitudinal_ids_{upload_id}").set_value(
        ["persona"]
    ).run()

    assert not app.exception
    assert not app.checkbox
    assert any("2 pares adyacentes están disponibles" in element.value for element in app.success)
    assert any(
        "la clave seleccionada se considera confirmada"
        in element.value.lower()
        for element in app.info
    )
    assert app.selectbox(key="markov_weighting").options == [
        "Simple (conteo de pares)",
        "Ponderada (fac_tri de origen)",
    ]
