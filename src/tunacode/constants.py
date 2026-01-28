"""
Module: tunacode.constants

Global constants and configuration values for the TunaCode CLI application.
Centralizes all magic strings, UI text, error messages, and application constants.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.theme import Theme

KB = 1024
MB = KB * 1024

APP_NAME = "TunaCode"
APP_VERSION = "0.1.49"


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
TOOL_PANEL_HORIZONTAL_INSET = 8
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
    SUBMIT = "submit"


TUNACODE_HOME_DIR = ".tunacode"
SESSIONS_SUBDIR = "sessions"

UI_COLORS = {
    "background": "#1a1a1a",
    "surface": "#252525",
    "border": "#ff6b9d",
    "text": "#e0e0e0",
    "muted": "#808080",
    "primary": "#00d7d7",
    "accent": "#ff6b9d",
    "success": "#4ec9b0",
    "warning": "#c3e88d",
    "error": "#f44747",
}

NEXTSTEP_COLORS = {
    "background": "#acacac",
    "surface": "#c8c8c8",
    "window_content": "#d0d0d0",
    "title_bar": "#3a3a3a",
    "title_bar_text": "#e0e0e0",
    "border": "#2a2a2a",
    "text": "#000000",
    "muted": "#404040",
    "bevel_light": "#e8e8e8",
    "bevel_dark": "#606060",
    "primary": "#1a1a1a",
    "accent": "#3a3a3a",
    "success": "#2a2a2a",
    "warning": "#4a4a4a",
    "error": "#1a1a1a",
}

ERROR_TOOL_CALL_ID_MISSING = "Tool return missing tool_call_id."
ERROR_TOOL_ARGS_MISSING = "Tool args missing for tool_call_id '{tool_call_id}'."

TOOL_MAX_RETRIES = 3
TOOL_RETRY_BASE_DELAY = 0.5
TOOL_RETRY_MAX_DELAY = 5.0


THEME_NAME = "tunacode"

RESOURCE_BAR_SEPARATOR = " - "
RESOURCE_BAR_COST_FORMAT = "${cost:.2f}"

RICHLOG_CLASS_PAUSED = "paused"
RICHLOG_CLASS_STREAMING = "streaming"


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
        variables={
            "text-muted": p["muted"],
            "border": p["border"],
        },
    )


def build_nextstep_theme() -> Theme:
    """Build and return the NeXTSTEP Textual theme.

    Classic 1990s NeXTSTEP look - light gray background, black text,
    pure monochrome with no colored accents. High contrast for readability.
    """
    from textual.theme import Theme

    p = NEXTSTEP_COLORS
    return Theme(
        name="nextstep",
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
        variables={
            "text-muted": p["muted"],
            "border": p["border"],
            "bevel-light": p["bevel_light"],
            "bevel-dark": p["bevel_dark"],
            "title-bar": p["title_bar"],
            "title-bar-text": p["title_bar_text"],
            "window-content": p["window_content"],
        },
    )
