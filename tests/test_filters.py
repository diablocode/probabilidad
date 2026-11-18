from enoe_app.filters import MISSING_OPTION, apply_filters, get_filter_options


def test_apply_filters_combines_selections(sample_frame):
    filtered = apply_filters(
        sample_frame,
        {"n_ent": [2], "grupo_edad": ["Adulto"], "sexo_label": ["Mujer"]},
    )

    assert filtered.index.tolist() == [2]


def test_apply_filters_keeps_all_rows_when_selection_is_none(sample_frame):
    filtered = apply_filters(sample_frame, {"n_ent": None})

    assert len(filtered) == len(sample_frame)


def test_apply_filters_empty_selection_returns_no_rows(sample_frame):
    filtered = apply_filters(sample_frame, {"n_ent": []})

    assert filtered.empty


def test_apply_filters_can_select_missing_values(sample_frame):
    filtered = apply_filters(sample_frame, {"sexo_label": [MISSING_OPTION]})

    assert filtered.index.tolist() == [3]


def test_get_filter_options_includes_missing_values(sample_frame):
    options = get_filter_options(sample_frame, "sexo_label")

    assert options == ["Hombre", "Mujer", MISSING_OPTION]
