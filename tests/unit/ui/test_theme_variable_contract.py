"""Tests for shared theme variable contract across Textual themes."""

from tunacode.constants import (
    NEXTSTEP_COLORS,
    THEME_VARIABLE_CONTRACT,
    UI_COLORS,
    build_nextstep_theme,
    build_tunacode_theme,
)


def test_palettes_include_required_theme_variable_keys() -> None:
    required_palette_keys = {palette_key for _, palette_key in THEME_VARIABLE_CONTRACT}

    assert required_palette_keys.issubset(UI_COLORS)
    assert required_palette_keys.issubset(NEXTSTEP_COLORS)


def test_theme_builders_emit_identical_variable_schema() -> None:
    expected_variable_keys = {variable_key for variable_key, _ in THEME_VARIABLE_CONTRACT}

    tunacode_variables = build_tunacode_theme().variables
    nextstep_variables = build_nextstep_theme().variables

    assert set(tunacode_variables) == expected_variable_keys
    assert set(nextstep_variables) == expected_variable_keys
    assert set(tunacode_variables) == set(nextstep_variables)


def test_theme_variables_map_to_palette_values() -> None:
    tunacode_variables = build_tunacode_theme().variables
    nextstep_variables = build_nextstep_theme().variables

    for variable_key, palette_key in THEME_VARIABLE_CONTRACT:
        assert tunacode_variables[variable_key] == UI_COLORS[palette_key]
        assert nextstep_variables[variable_key] == NEXTSTEP_COLORS[palette_key]
