"""Tests for shared theme variable contract across all supported themes."""

from textual.app import App

from tunacode.constants import (
    BUILTIN_THEME_PALETTES,
    NEXTSTEP_COLORS,
    THEME_VARIABLE_CONTRACT,
    UI_COLORS,
    build_nextstep_theme,
    build_tunacode_theme,
    wrap_builtin_themes,
)


def test_palettes_include_required_theme_variable_keys() -> None:
    required_palette_keys = {palette_key for _, palette_key in THEME_VARIABLE_CONTRACT}

    assert required_palette_keys.issubset(UI_COLORS)
    assert required_palette_keys.issubset(NEXTSTEP_COLORS)


def test_builtin_palettes_include_required_keys() -> None:
    required_palette_keys = {palette_key for _, palette_key in THEME_VARIABLE_CONTRACT}

    for name, palette in BUILTIN_THEME_PALETTES.items():
        missing = required_palette_keys - set(palette)
        assert not missing, f"{name} palette missing keys: {missing}"


def test_theme_builders_emit_identical_variable_schema() -> None:
    expected_variable_keys = {variable_key for variable_key, _ in THEME_VARIABLE_CONTRACT}

    tunacode_variables = build_tunacode_theme().variables
    nextstep_variables = build_nextstep_theme().variables

    assert set(tunacode_variables) == expected_variable_keys
    assert set(nextstep_variables) == expected_variable_keys


def test_wrapped_builtins_emit_contract_variables() -> None:
    expected_variable_keys = {variable_key for variable_key, _ in THEME_VARIABLE_CONTRACT}
    available = App().available_themes
    wrapped = wrap_builtin_themes(available)

    assert len(wrapped) == len(BUILTIN_THEME_PALETTES)

    for theme in wrapped:
        missing = expected_variable_keys - set(theme.variables)
        assert not missing, f"{theme.name} missing contract variables: {missing}"


def test_wrapped_builtins_preserve_non_contract_variables() -> None:
    contract_keys = {variable_key for variable_key, _ in THEME_VARIABLE_CONTRACT}
    available = App().available_themes
    wrapped = wrap_builtin_themes(available)

    for theme in wrapped:
        original = available[theme.name]
        for key, value in original.variables.items():
            if key in contract_keys:
                continue
            assert theme.variables[key] == value, (
                f"{theme.name}: original variable '{key}' was overwritten"
            )


def test_theme_variables_map_to_palette_values() -> None:
    tunacode_variables = build_tunacode_theme().variables
    nextstep_variables = build_nextstep_theme().variables

    for variable_key, palette_key in THEME_VARIABLE_CONTRACT:
        assert tunacode_variables[variable_key] == UI_COLORS[palette_key]
        assert nextstep_variables[variable_key] == NEXTSTEP_COLORS[palette_key]
