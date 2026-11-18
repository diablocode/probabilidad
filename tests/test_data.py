import pandas as pd
import pytest

from enoe_app.data import DataValidationError, load_dataset, load_datasets


REQUIRED_DATA = {
    "cve_ent": [1, 1],
    "n_ent": [1, 2],
    "per": [226, 226],
    "grupo_edad": ["Adulto", "Joven"],
    "sexo_label": ["Mujer", "Hombre"],
    "cve_mun": [1, 1],
    "ocupado": [1, 0],
    "categoria_empleo": ["Empleador", "No aplica / no ocupado"],
    "fac_tri": [1.5, 2.0],
}


def test_load_dataset_accepts_valid_rows_and_reports_discarded_rows(tmp_path):
    frame = pd.DataFrame(
        {
            **REQUIRED_DATA,
            "n_ent": [1, 6],
        }
    )
    path = tmp_path / "input.csv"
    frame.to_csv(path, index=False)

    report = load_dataset(path)

    assert report.loaded_rows == 2
    assert report.accepted_rows == 1
    assert report.discarded_rows == 1
    assert report.discard_reasons == {
        "n_ent inválido (se espera un entero entre 1 y 5)": 1
    }
    assert report.frame["n_ent"].tolist() == [1]
    assert report.frame["fac_tri"].tolist() == [1.5]


def test_load_dataset_rejects_missing_required_columns(tmp_path):
    path = tmp_path / "input.csv"
    pd.DataFrame({"n_ent": [1]}).to_csv(path, index=False)

    with pytest.raises(DataValidationError, match="Faltan columnas requeridas"):
        load_dataset(path)


def test_load_dataset_reports_empty_file(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(DataValidationError, match="CSV está vacío"):
        load_dataset(path)


def test_load_dataset_rejects_file_without_valid_rows(tmp_path):
    path = tmp_path / "input.csv"
    pd.DataFrame(
        {
            **REQUIRED_DATA,
            "ocupado": [2, 3],
        }
    ).to_csv(path, index=False)

    with pytest.raises(DataValidationError, match="No hay observaciones válidas"):
        load_dataset(path)


def test_load_dataset_reports_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="No se encontró el archivo"):
        load_dataset(tmp_path / "missing.csv")


def test_load_dataset_derives_fields_from_raw_sdemt_codes(tmp_path):
    frame = pd.DataFrame(
        {
            "cve_ent": [1] * 6,
            "cve_mun": ["1"] * 6,
            "n_ent": [1] * 6,
            "per": [425] * 6,
            "mes_cal": [10] * 6,
            "sex": ["1", "2", "1", "2", " ", "1"],
            "eda": ["14", "15", "30", "60", " ", "25"],
            "pos_ocu": [0, 1, 2, 3, 4, 0],
            "fac_tri": [1, 2, 3, 4, 5, 0],
        }
    )
    path = tmp_path / "raw_sdemt.csv"
    frame.to_csv(path, index=False)

    report = load_dataset(path)

    assert report.loaded_rows == 6
    assert report.accepted_rows == 5
    assert report.discard_reasons == {
        "fac_tri inválido (se espera un valor positivo y finito)": 1
    }
    assert report.frame["categoria_empleo"].tolist() == [
        "No aplica / no ocupado",
        "Trabajador subordinado y remunerado",
        "Empleador",
        "Trabajador por cuenta propia",
        "Trabajador sin pago",
    ]
    assert report.frame["ocupado"].tolist() == [0, 1, 1, 1, 1]
    assert report.frame["sexo_label"].iloc[:4].tolist() == [
        "Hombre",
        "Mujer",
        "Hombre",
        "Mujer",
    ]
    assert report.frame["sexo_label"].isna().iloc[4]
    assert report.frame["grupo_edad"].iloc[:4].tolist() == [
        "Menor de 15",
        "Joven (15-29)",
        "Adulto (30-59)",
        "Mayor (60+)",
    ]
    assert report.frame["grupo_edad"].isna().iloc[4]
    assert report.frame["period_index"].tolist() == [8103] * 5


def test_load_datasets_combines_quarter_files_in_given_order(tmp_path):
    paths = []
    for per in (425, 126, 226):
        frame = pd.DataFrame(
            {
                **REQUIRED_DATA,
                "n_ent": [1, 2],
                "per": [per, per],
            }
        )
        path = tmp_path / f"ENOE_SDEMT{per}.csv"
        frame.to_csv(path, index=False)
        paths.append(path)

    combined, reports = load_datasets(paths)

    assert len(reports) == 3
    assert combined["per"].drop_duplicates().tolist() == [425, 126, 226]
    assert combined["period_index"].drop_duplicates().tolist() == [8103, 8104, 8105]
    assert combined["source_file"].drop_duplicates().tolist() == [
        "ENOE_SDEMT425.csv",
        "ENOE_SDEMT126.csv",
        "ENOE_SDEMT226.csv",
    ]


def test_load_datasets_rejects_mismatched_schemas(tmp_path):
    paths = []
    for index, extra_column in enumerate((None, "unexpected")):
        frame = pd.DataFrame(REQUIRED_DATA)
        if extra_column:
            frame[extra_column] = "value"
        path = tmp_path / f"input_{index}.csv"
        frame.to_csv(path, index=False)
        paths.append(path)

    with pytest.raises(DataValidationError, match="esquema.*no coincide"):
        load_datasets(paths)


def test_cve_ent_mapping_to_state_names(tmp_path):
    frame = pd.DataFrame(
        {
            "cve_ent": [1, 14, 9],
            "n_ent": [1, 1, 1],
            "per": [226, 226, 226],
            "grupo_edad": ["Adulto", "Adulto", "Adulto"],
            "sexo_label": ["Mujer", "Hombre", "Mujer"],
            "cve_mun": [1, 1, 1],
            "ocupado": [1, 1, 1],
            "categoria_empleo": ["Empleador", "Empleador", "Empleador"],
            "fac_tri": [1.0, 1.0, 1.0],
        }
    )
    path = tmp_path / "entidades.csv"
    frame.to_csv(path, index=False)
    report = load_dataset(path)
    assert report.frame["cve_ent"].tolist() == [
        "Aguascalientes",
        "Jalisco",
        "Ciudad de México",
    ]


def test_cve_mun_mapping_to_municipality_names(tmp_path):
    frame = pd.DataFrame(
        {
            "cve_ent": [1, 1, 14, 14],
            "cve_mun": [1, 5, 39, 120],
            "n_ent": [1, 1, 1, 1],
            "per": [226, 226, 226, 226],
            "grupo_edad": ["Adulto", "Adulto", "Adulto", "Adulto"],
            "sexo_label": ["Mujer", "Hombre", "Mujer", "Hombre"],
            "ocupado": [1, 1, 1, 1],
            "categoria_empleo": ["Empleador", "Empleador", "Empleador", "Empleador"],
            "fac_tri": [1.0, 1.0, 1.0, 1.0],
        }
    )
    path = tmp_path / "municipios.csv"
    frame.to_csv(path, index=False)
    report = load_dataset(path)
    assert report.frame["cve_mun"].tolist() == [
        "Aguascalientes",
        "Jesús María",
        "Guadalajara",
        "Zapopan",
    ]
