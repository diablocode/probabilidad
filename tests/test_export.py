from io import BytesIO

import pandas as pd
import pytest

from enoe_app.export import filtered_csv_bytes


def test_filtered_csv_bytes_preserves_filtered_rows_and_selected_columns(
    sample_frame,
):
    filtered = sample_frame.loc[sample_frame["sexo_label"].eq("Mujer")]
    original = filtered.copy(deep=True)

    exported = filtered_csv_bytes(filtered, ["sexo_label", "ocupado"])
    round_trip = pd.read_csv(BytesIO(exported))

    assert round_trip.columns.tolist() == ["sexo_label", "ocupado"]
    assert round_trip.to_dict(orient="records") == [
        {"sexo_label": "Mujer", "ocupado": 1},
        {"sexo_label": "Mujer", "ocupado": 1},
    ]
    pd.testing.assert_frame_equal(filtered, original)
    assert exported.startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize(
    "columns, message",
    [
        ([], "Seleccione al menos una columna"),
        (["sexo_label", "sexo_label"], "No se pueden repetir columnas"),
        (["no_existe"], "No existen estas columnas"),
    ],
)
def test_filtered_csv_bytes_rejects_invalid_column_selection(
    sample_frame, columns, message
):
    with pytest.raises(ValueError, match=message):
        filtered_csv_bytes(sample_frame, columns)
