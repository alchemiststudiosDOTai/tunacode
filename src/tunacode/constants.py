"""
Module: tunacode.constants

Global constants and configuration values for the TunaCode CLI application.
Centralizes all magic strings, UI text, error messages, and application constants.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.theme import Theme

KB = 1024
MB = KB * 1024

APP_NAME = "TunaCode"
APP_VERSION = "0.1.62"


GUIDE_FILE_NAME = "AGENTS.md"
ENV_FILE = ".env"
CONFIG_FILE_NAME = "tunacode.json"
ENV_OPENAI_BASE_URL = "OPENAI_BASE_URL"

MAX_COMMAND_OUTPUT = 5000
MAX_FILES_IN_DIR = 50
DEFAULT_CONTEXT_WINDOW = 200000

MAX_CALLBACK_CONTENT = 50_000
MAX_PANEL_LINES = 20
MIN_TOOL_PANEL_LINE_WIDTH = 4
TOOL_PANEL_HORIZONTAL_INSET = 4  # CSS border (1+1) + padding (1+1)
TOOL_PANEL_WIDTH_DEBUG = False
SYNTAX_LINE_NUMBER_PADDING = 2
SYNTAX_LINE_NUMBER_SEPARATOR_WIDTH = 1
MAX_SEARCH_RESULTS_DISPLAY = 20
MODEL_PICKER_UNFILTERED_LIMIT = 50

TOOL_VIEWPORT_LINES = 8
MIN_VIEWPORT_LINES = 3
URL_DISPLAY_MAX_LENGTH = 50

BOX_HORIZONTAL = "\u2500"  # ─
HOOK_ARROW = "↳"
HOOK_ARROW_PREFIX = f"{HOOK_ARROW} "
SEPARATOR_WIDTH = 10

AUTOCOMPLETE_MAX_DEPTH = 3
AUTOCOMPLETE_RESULT_LIMIT = 50


class ToolName(str, Enum):
    """Enumeration of tool names."""

    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    UPDATE_FILE = "update_file"
    BASH = "bash"
    GREP = "grep"
    LIST_DIR = "list_dir"
    GLOB = "glob"
    WEB_FETCH = "web_fetch"


TUNACODE_HOME_DIR = ".tunacode"
SESSIONS_SUBDIR = "sessions"

UI_COLORS = {
    "background": "#1a1a1a",
    "surface": "#252525",
    "border": "#333333",
    "text": "#e0e0e0",
    "muted": "#808080",
    "bevel_light": "#3a3a3a",
    "bevel_dark": "#101010",
    "scrollbar_thumb": "#ff6b9d",
    "scrollbar_track": "#252525",
    "primary": "#00d7d7",
    "accent": "#ff6b9d",
    "success": "#4ec9b0",
    "warning": "#c3e88d",
    "error": "#f44747",
}

NEXTSTEP_COLORS = {
    "background": "#acacac",
    "surface": "#c8c8c8",
    "border": "#2a2a2a",
    "text": "#000000",
    "muted": "#404040",
    "bevel_light": "#e8e8e8",
    "bevel_dark": "#606060",
    "scrollbar_thumb": "#606060",
    "scrollbar_track": "#c8c8c8",
    "primary": "#1a1a1a",
    "accent": "#3a3a3a",
    "success": "#2a2a2a",
    "warning": "#4a4a4a",
    "error": "#1a1a1a",
}

THEME_VARIABLE_CONTRACT: tuple[tuple[str, str], ...] = (
    ("bevel-light", "bevel_light"),
    ("bevel-dark", "bevel_dark"),
    ("border", "border"),
    ("text-muted", "muted"),
    ("scrollbar-thumb", "scrollbar_thumb"),
    ("scrollbar-track", "scrollbar_track"),
)

THEME_NAME = "tunacode"
NEXTSTEP_THEME_NAME = "nextstep"

# Palettes for Textual built-in themes (only the 6 contract keys).
# Each palette feeds through _build_theme_variables() unchanged.
BUILTIN_THEME_PALETTES: dict[str, dict[str, str]] = {
    "catppuccin-latte": {
        "bevel_light": "#F5F5F8",
        "bevel_dark": "#ACB0BE",
        "border": "#BCC0CC",
        "muted": "#8C8FA1",
        "scrollbar_thumb": "#8839EF",
        "scrollbar_track": "#E6E9EF",
    },
    "catppuccin-mocha": {
        "bevel_light": "#45475A",
        "bevel_dark": "#11111B",
        "border": "#585B70",
        "muted": "#6C7086",
        "scrollbar_thumb": "#F5C2E7",
        "scrollbar_track": "#313244",
    },
    "dracula": {
        "bevel_light": "#44475A",
        "bevel_dark": "#191A21",
        "border": "#6272A4",
        "muted": "#6272A4",
        "scrollbar_thumb": "#BD93F9",
        "scrollbar_track": "#2B2E3B",
    },
    "flexoki": {
        "bevel_light": "#343331",
        "bevel_dark": "#080808",
        "border": "#575653",
        "muted": "#878580",
        "scrollbar_thumb": "#205EA6",
        "scrollbar_track": "#1C1B1A",
    },
    "gruvbox": {
        "bevel_light": "#504945",
        "bevel_dark": "#1D2021",
        "border": "#665C54",
        "muted": "#A89984",
        "scrollbar_thumb": "#85A598",
        "scrollbar_track": "#3C3836",
    },
    "monokai": {
        "bevel_light": "#49483E",
        "bevel_dark": "#1A1A16",
        "border": "#75715E",
        "muted": "#797979",
        "scrollbar_thumb": "#AE81FF",
        "scrollbar_track": "#2E2E2E",
    },
    "nord": {
        "bevel_light": "#4C566A",
        "bevel_dark": "#242933",
        "border": "#4C566A",
        "muted": "#616E88",
        "scrollbar_thumb": "#88C0D0",
        "scrollbar_track": "#3B4252",
    },
    "solarized-light": {
        "bevel_light": "#FDF6E3",
        "bevel_dark": "#93A1A1",
        "border": "#839496",
        "muted": "#93A1A1",
        "scrollbar_thumb": "#268BD2",
        "scrollbar_track": "#EEE8D5",
    },
    "textual-ansi": {
        "bevel_light": "ansi_white",
        "bevel_dark": "ansi_bright_black",
        "border": "ansi_blue",
        "muted": "ansi_bright_black",
        "scrollbar_thumb": "ansi_bright_blue",
        "scrollbar_track": "ansi_default",
    },
    "textual-dark": {
        "bevel_light": "#3A3A3A",
        "bevel_dark": "#0A0A0A",
        "border": "#333333",
        "muted": "#808080",
        "scrollbar_thumb": "#0178D4",
        "scrollbar_track": "#1E1E1E",
    },
    "textual-light": {
        "bevel_light": "#EEEEEE",
        "bevel_dark": "#999999",
        "border": "#AAAAAA",
        "muted": "#707070",
        "scrollbar_thumb": "#004578",
        "scrollbar_track": "#D8D8D8",
    },
    "tokyo-night": {
        "bevel_light": "#3B4261",
        "bevel_dark": "#13141E",
        "border": "#414868",
        "muted": "#565F89",
        "scrollbar_thumb": "#BB9AF7",
        "scrollbar_track": "#24283B",
    },
}

SUPPORTED_THEME_NAMES: tuple[str, ...] = (
    THEME_NAME,
    NEXTSTEP_THEME_NAME,
    *BUILTIN_THEME_PALETTES,
)

RESOURCE_BAR_SEPARATOR = " - "
RESOURCE_BAR_COST_FORMAT = "${cost:.2f}"

RICHLOG_CLASS_PAUSED = "paused"
RICHLOG_CLASS_STREAMING = "streaming"


def _build_theme_variables(palette: Mapping[str, str]) -> dict[str, str]:
    required_palette_keys = {palette_key for _, palette_key in THEME_VARIABLE_CONTRACT}
    missing_palette_keys = sorted(required_palette_keys - set(palette))
    if missing_palette_keys:
        missing_keys = ", ".join(missing_palette_keys)
        raise ValueError(f"Theme palette missing required keys: {missing_keys}")

    return {
        variable_key: palette[palette_key] for variable_key, palette_key in THEME_VARIABLE_CONTRACT
    }


def build_tunacode_theme() -> Theme:
    """Build and return the TunaCode Textual theme.

    Uses UI_COLORS palette - high contrast neutral scheme.
    Import Theme lazily to avoid import cycles and allow non-TUI usage.
    """
    from textual.theme import Theme

    p = UI_COLORS
    return Theme(
        name=THEME_NAME,
        primary=p["primary"],
        secondary=p["muted"],
        accent=p["accent"],
        background=p["background"],
        surface=p["surface"],
        panel=p["surface"],
        success=p["success"],
        warning=p["warning"],
        error=p["error"],
        foreground=p["text"],
        variables=_build_theme_variables(p),
    )


def build_nextstep_theme() -> Theme:
    """Build and return the NeXTSTEP Textual theme.

    Classic 1990s NeXTSTEP look - light gray background, black text,
    pure monochrome with no colored accents. High contrast for readability.
    """
    from textual.theme import Theme

    p = NEXTSTEP_COLORS
    return Theme(
        name=NEXTSTEP_THEME_NAME,
        dark=False,
        primary=p["primary"],
        secondary=p["muted"],
        accent=p["accent"],
        background=p["background"],
        surface=p["surface"],
        panel=p["surface"],
        success=p["success"],
        warning=p["warning"],
        error=p["error"],
        foreground=p["text"],
        variables=_build_theme_variables(p),
    )


def _wrap_builtin_theme(theme: Theme, palette: Mapping[str, str]) -> Theme:
    """Re-register a Textual built-in theme with contract variables injected.

    Preserves all original theme properties. Merges contract variables on top
    of the theme's existing variables so nothing is lost.
    """
    from textual.theme import Theme as ThemeCls

    merged_vars = {**theme.variables, **_build_theme_variables(palette)}

    name = theme.name
    return ThemeCls(
        name=name,
        primary=theme.primary,
        secondary=theme.secondary,
        accent=theme.accent,
        foreground=theme.foreground,
        background=theme.background,
        surface=theme.surface,
        panel=theme.panel,
        warning=theme.warning,
        error=theme.error,
        success=theme.success,
        variables=merged_vars,
        dark=theme.dark,
    )


def wrap_builtin_themes(available: Mapping[str, Theme]) -> list[Theme]:
    """Wrap Textual built-in themes with contract variables.

    Takes the app's available_themes mapping, wraps each one that has a
    palette defined in BUILTIN_THEME_PALETTES, and returns the wrapped themes.
    """
    wrapped: list[Theme] = []
    for name, palette in BUILTIN_THEME_PALETTES.items():
        if name in available:
            wrapped.append(_wrap_builtin_theme(available[name], palette))
    return wrapped
