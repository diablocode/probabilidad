"""Carga y validación del CSV de entrada."""

from collections.abc import Sequence
from dataclasses import dataclass
import math
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "cve_ent",
    "n_ent",
    "per",
    "grupo_edad",
    "sexo_label",
    "cve_mun",
    "ocupado",
    "categoria_empleo",
    "fac_tri",
}

POS_OCU_CATEGORIES = {
    0: "No aplica / no ocupado",
    1: "Trabajador subordinado y remunerado",
    2: "Empleador",
    3: "Trabajador por cuenta propia",
    4: "Trabajador sin pago",
}


class DataValidationError(ValueError):
    """Error legible de estructura o contenido de los datos de entrada."""


@dataclass(frozen=True)
class DataLoadReport:
    """Datos validados y resumen de filas aceptadas o descartadas."""

    frame: pd.DataFrame
    source_path: Path
    loaded_rows: int
    accepted_rows: int
    discarded_rows: int
    discard_reasons: dict[str, int]


def _period_index_from_per(frame: pd.DataFrame) -> pd.Series:
    per = pd.to_numeric(frame["per"], errors="coerce")
    quarter = (per // 100).astype("Float64")
    year_suffix = per.mod(100)
    valid = (
        per.notna()
        & per.mod(1).eq(0)
        & quarter.between(1, 4)
        & year_suffix.between(0, 99)
    ).fillna(False)

    if "mes_cal" in frame.columns:
        month = pd.to_numeric(frame["mes_cal"], errors="coerce")
        calendar_month = month.between(1, 12).fillna(False)
        expected_first_month = (quarter - 1) * 3 + 1
        mismatch = calendar_month & ~month.between(
            expected_first_month, expected_first_month + 2
        )
        valid &= ~mismatch.fillna(False)

    period_index = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    valid_year = (2000 + year_suffix.loc[valid]).astype("int64")
    valid_quarter = quarter.loc[valid].astype("int64")
    period_index.loc[valid] = valid_year * 4 + valid_quarter - 1
    return period_index


INEGI_ENTIDADES = {
    1: "Aguascalientes",
    2: "Baja California",
    3: "Baja California Sur",
    4: "Campeche",
    5: "Coahuila de Zaragoza",
    6: "Colima",
    7: "Chiapas",
    8: "Chihuahua",
    9: "Ciudad de México",
    10: "Durango",
    11: "Guanajuato",
    12: "Guerrero",
    13: "Hidalgo",
    14: "Jalisco",
    15: "México",
    16: "Michoacán de Ocampo",
    17: "Morelos",
    18: "Nayarit",
    19: "Nuevo León",
    20: "Oaxaca",
    21: "Puebla",
    22: "Querétaro",
    23: "Quintana Roo",
    24: "San Luis Potosí",
    25: "Sinaloa",
    26: "Sonora",
    27: "Tabasco",
    28: "Tamaulipas",
    29: "Tlaxcala",
    30: "Veracruz de Ignacio de la Llave",
    31: "Yucatán",
    32: "Zacatecas",
}


def _map_cve_ent(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    mapped = numeric.map(INEGI_ENTIDADES)
    fallback = values.astype("string").str.strip()
    return mapped.where(mapped.notna(), fallback)


MUNICIPIOS_AGUASCALIENTES = {
    1: "Aguascalientes",
    2: "Asientos",
    3: "Calvillo",
    4: "Cosío",
    5: "Jesús María",
    6: "Pabellón de Arteaga",
    7: "Rincón de Romos",
    8: "San José de Gracia",
    9: "Tepezalá",
    10: "El Llano",
    11: "San Francisco de los Romo",
}

MUNICIPIOS_JALISCO = {
    1: "Acatic",
    2: "Acatlán de Juárez",
    3: "Ahualulco de Mercado",
    4: "Amacueca",
    5: "Amatitán",
    6: "Ameca",
    7: "San Juanito de Escobedo",
    8: "Arandas",
    9: "El Arenal",
    10: "Atemajac de Brizuela",
    11: "Atengo",
    12: "Atenguillo",
    13: "Atotonilco el Alto",
    14: "Atoyac",
    15: "Autlán de Navarro",
    16: "Ayotlán",
    17: "Ayutla",
    18: "La Barca",
    19: "Bolaños",
    20: "Cabo Corrientes",
    21: "Casimiro Castillo",
    22: "Cihuatlán",
    23: "Zapotlán el Grande",
    24: "Cocula",
    25: "Colotlán",
    26: "Concepción de Buenos Aires",
    27: "Cuautitlán de García Barragán",
    28: "Cuautla",
    29: "Cuquío",
    30: "Chapala",
    31: "Chimalitán",
    32: "Chiquilistlán",
    33: "Degollado",
    34: "Ejutla",
    35: "Encarnación de Díaz",
    36: "Etzatlán",
    37: "El Grullo",
    38: "Guachinango",
    39: "Guadalajara",
    40: "Hostotipaquillo",
    41: "Huejúcar",
    42: "Huejuquilla el Alto",
    43: "La Huerta",
    44: "Ixtlahuacán de los Membrillos",
    45: "Ixtlahuacán del Río",
    46: "Jalostotitlán",
    47: "Jamay",
    48: "Jesús María",
    49: "Jilotlán de los Dolores",
    50: "Jocotepec",
    51: "Juanacatlán",
    52: "Juchitlán",
    53: "Lagos de Moreno",
    54: "El Limón",
    55: "Magdalena",
    56: "Santa María del Oro",
    57: "La Manzanilla de la Paz",
    58: "Mascota",
    59: "Mazamitla",
    60: "Mexticacán",
    61: "Mezquitic",
    62: "Mixtlán",
    63: "Ocotlán",
    64: "Ojuelos de Jalisco",
    65: "Pihuamo",
    66: "Poncitlán",
    67: "Puerto Vallarta",
    68: "Villa Purificación",
    69: "Quitupan",
    70: "El Salto",
    71: "San Cristóbal de la Barranca",
    72: "San Diego de Alejandría",
    73: "San Juan de los Lagos",
    74: "San Julián",
    75: "San Marcos",
    76: "San Martín de Bolaños",
    77: "San Martín Hidalgo",
    78: "San Miguel el Alto",
    79: "Gómez Farías",
    80: "San Sebastián del Oeste",
    81: "Santa María de los Ángeles",
    82: "Sayula",
    83: "Tala",
    84: "Talpa de Allende",
    85: "Tamazula de Gordiano",
    86: "Tapalpa",
    87: "Tecalitlán",
    88: "Tecolotlán",
    89: "Techaluta de Montenegro",
    90: "Tenamaxtlán",
    91: "Teocaltiche",
    92: "Teocuitatlán de Corona",
    93: "Tepatitlán de Morelos",
    94: "Tequila",
    95: "Teuchitlán",
    96: "Tizapán el Alto",
    97: "Tlajomulco de Zúñiga",
    98: "San Pedro Tlaquepaque",
    99: "Tolimán",
    100: "Tomatlán",
    101: "Tonalá",
    102: "Tonaya",
    103: "Tonila",
    104: "Totatiche",
    105: "Tototlán",
    106: "Tuxcacuesco",
    107: "Tuxcueca",
    108: "Tuxpan",
    109: "Unión de San Antonio",
    110: "Unión de Tula",
    111: "Valle de Guadalupe",
    112: "Valle de Juárez",
    113: "San Gabriel",
    114: "Villa Corona",
    115: "Villa Guerrero",
    116: "Villa Hidalgo",
    117: "Cañadas de Obregón",
    118: "Yahualica de González Gallo",
    119: "Zacoalco de Torres",
    120: "Zapopan",
    121: "Zapotiltic",
    122: "Zapotitlán de Vadillo",
    123: "Zapotlán del Rey",
    124: "Zapotlanejo",
    125: "San Ignacio Cerro Gordo",
}


def _map_cve_mun(frame: pd.DataFrame) -> pd.Series:
    if "cve_mun" not in frame.columns or "cve_ent" not in frame.columns:
        return (
            frame["cve_mun"]
            if "cve_mun" in frame.columns
            else pd.Series(dtype="string")
        )

    cve_mun_num = pd.to_numeric(frame["cve_mun"], errors="coerce")
    result = frame["cve_mun"].astype("string").str.strip()

    aguascalientes_mask = frame["cve_ent"].eq("Aguascalientes")
    jalisco_mask = frame["cve_ent"].eq("Jalisco")

    if aguascalientes_mask.any():
        mapped_ags = cve_mun_num.map(MUNICIPIOS_AGUASCALIENTES)
        result.loc[aguascalientes_mask & mapped_ags.notna()] = mapped_ags.loc[
            aguascalientes_mask & mapped_ags.notna()
        ]

    if jalisco_mask.any():
        mapped_jal = cve_mun_num.map(MUNICIPIOS_JALISCO)
        result.loc[jalisco_mask & mapped_jal.notna()] = mapped_jal.loc[
            jalisco_mask & mapped_jal.notna()
        ]

    return result


def prepare_enoe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Deriva etiquetas analíticas desde campos crudos del archivo SDEMT."""
    prepared = frame.copy()
    if "cve_ent" in prepared.columns:
        prepared["cve_ent"] = _map_cve_ent(prepared["cve_ent"])
    if "cve_mun" in prepared.columns:
        prepared["cve_mun"] = _map_cve_mun(prepared)
    if "per" in prepared.columns:
        prepared["period_index"] = _period_index_from_per(prepared)

    derived_columns = {
        "grupo_edad",
        "sexo_label",
        "ocupado",
        "categoria_empleo",
    }
    if derived_columns.issubset(prepared.columns):
        return prepared

    raw_columns = {"sex", "eda", "pos_ocu"}
    if not raw_columns.issubset(prepared.columns):
        return prepared

    position = pd.to_numeric(prepared["pos_ocu"], errors="coerce")
    prepared["categoria_empleo"] = position.map(POS_OCU_CATEGORIES)
    prepared["ocupado"] = position.map(
        {0: 0, 1: 1, 2: 1, 3: 1, 4: 1}
    ).astype("Int64")

    sex = prepared["sex"].astype("string").str.strip()
    prepared["sexo_label"] = sex.map({"1": "Hombre", "2": "Mujer"})

    age = pd.to_numeric(prepared["eda"], errors="coerce")
    age_group = pd.Series(pd.NA, index=prepared.index, dtype="string")
    age_group.loc[age.between(0, 14)] = "Menor de 15"
    age_group.loc[age.between(15, 29)] = "Joven (15-29)"
    age_group.loc[age.between(30, 59)] = "Adulto (30-59)"
    age_group.loc[age.ge(60)] = "Mayor (60+)"
    prepared["grupo_edad"] = age_group
    return prepared


def load_dataset(path: str | Path) -> DataLoadReport:
    """Carga el CSV y descarta filas con valores numéricos inválidos."""
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {source_path}")

    try:
        frame = pd.read_csv(source_path, encoding="utf-8-sig", low_memory=False)
    except pd.errors.EmptyDataError as error:
        raise DataValidationError("El archivo CSV está vacío.") from error
    except pd.errors.ParserError as error:
        raise DataValidationError(f"No se pudo interpretar el CSV: {error}") from error
    except UnicodeDecodeError as error:
        raise DataValidationError(
            "El archivo no está codificado como UTF-8 o UTF-8 con BOM."
        ) from error

    frame = prepare_enoe_frame(frame)
    missing_columns = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing_columns:
        raise DataValidationError(
            "Faltan columnas requeridas: " + ", ".join(missing_columns)
        )
    if frame.empty:
        raise DataValidationError("El CSV no contiene observaciones.")

    numeric = {
        column: pd.to_numeric(frame[column], errors="coerce")
        for column in ("n_ent", "ocupado", "fac_tri", "period_index")
    }

    invalid_n_ent = (
        numeric["n_ent"].isna()
        | numeric["n_ent"].mod(1).ne(0)
        | ~numeric["n_ent"].between(1, 5)
    )
    invalid_period = (
        numeric["period_index"].isna()
        | numeric["period_index"].mod(1).ne(0)
    )
    invalid_ocupado = (
        numeric["ocupado"].isna()
        | numeric["ocupado"].mod(1).ne(0)
        | ~numeric["ocupado"].isin((0, 1))
    )
    invalid_fac_tri = numeric["fac_tri"].map(
        lambda value: not math.isfinite(value) or value <= 0
        if pd.notna(value)
        else True
    )

    invalid_reasons = pd.Series("", index=frame.index, dtype="object")
    for reason, invalid_rows in (
        ("n_ent inválido (se espera un entero entre 1 y 5)", invalid_n_ent),
        ("per inválido o incongruente con mes_cal", invalid_period),
        ("ocupado inválido (se espera 0 o 1)", invalid_ocupado),
        ("fac_tri inválido (se espera un valor positivo y finito)", invalid_fac_tri),
    ):
        first_invalid = invalid_rows & invalid_reasons.eq("")
        invalid_reasons.loc[first_invalid] = reason

    valid_rows = invalid_reasons.eq("")
    reasons = {
        str(reason): int(count)
        for reason, count in invalid_reasons.loc[~valid_rows]
        .value_counts()
        .items()
    }
    valid_frame = frame.loc[valid_rows].copy()
    for column, values in numeric.items():
        valid_frame[column] = values.loc[valid_rows]

    discarded_rows = int((~valid_rows).sum())
    if valid_frame.empty:
        raise DataValidationError(
            "No hay observaciones válidas. Revise per, n_ent, ocupado y fac_tri."
        )

    return DataLoadReport(
        frame=valid_frame,
        source_path=source_path,
        loaded_rows=len(frame),
        accepted_rows=len(valid_frame),
        discarded_rows=discarded_rows,
        discard_reasons=reasons,
    )


def load_datasets(
    paths: Sequence[str | Path],
) -> tuple[pd.DataFrame, tuple[DataLoadReport, ...]]:
    """Carga varios CSV ENOE compatibles y conserva su archivo de origen."""
    if not paths:
        raise DataValidationError("Seleccione al menos un archivo ENOE.")

    reports = tuple(load_dataset(path) for path in paths)
    expected_columns = list(reports[0].frame.columns)
    for report in reports[1:]:
        if list(report.frame.columns) != expected_columns:
            raise DataValidationError(
                f"El esquema de {report.source_path.name} no coincide con "
                f"{reports[0].source_path.name}."
            )

    frames = []
    for report in reports:
        file_frame = report.frame.copy()
        file_frame["source_file"] = report.source_path.name
        frames.append(file_frame)
    return pd.concat(frames, ignore_index=True), reports
