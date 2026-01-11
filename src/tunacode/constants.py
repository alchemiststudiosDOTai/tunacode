"""
Module: tunacode.constants

Global constants and configuration values for the TunaCode CLI application.
Centralizes all magic strings, UI text, error messages, and application constants.
"""

from enum import Enum

KB = 1024
MB = KB * 1024

APP_NAME = "TunaCode"
APP_VERSION = "0.1.29"


GUIDE_FILE_NAME = "AGENTS.md"
ENV_FILE = ".env"
CONFIG_FILE_NAME = "tunacode.json"
ENV_OPENAI_BASE_URL = "OPENAI_BASE_URL"
SETTINGS_BASE_URL = "base_url"

MAX_FILE_SIZE = 100 * KB
MAX_COMMAND_OUTPUT = 5000
DEFAULT_READ_LIMIT = 2000
MAX_LINE_LENGTH = 2000
MAX_FILES_IN_DIR = 50

# Local mode limits (for small context windows)
LOCAL_MAX_COMMAND_OUTPUT = 1500
LOCAL_DEFAULT_READ_LIMIT = 200
LOCAL_MAX_LINE_LENGTH = 500
LOCAL_MAX_FILES_IN_DIR = 20
MAX_TOTAL_DIR_SIZE = 2 * MB
DEFAULT_CONTEXT_WINDOW = 200000

MAX_CALLBACK_CONTENT = 50_000
MAX_PANEL_LINES = 20
MAX_PANEL_LINE_WIDTH = 50
MAX_SEARCH_RESULTS_DISPLAY = 20
MODEL_PICKER_UNFILTERED_LIMIT = 50

TOOL_VIEWPORT_LINES = 8
MIN_VIEWPORT_LINES = 3
TOOL_PANEL_WIDTH = 50
URL_DISPLAY_MAX_LENGTH = 50

BOX_HORIZONTAL = "\u2500"  # ─
SEPARATOR_WIDTH = 10

AUTOCOMPLETE_MAX_DEPTH = 3
AUTOCOMPLETE_RESULT_LIMIT = 50

COMMAND_OUTPUT_THRESHOLD = 3500
COMMAND_OUTPUT_START_INDEX = 2500
COMMAND_OUTPUT_END_SIZE = 1000


class ToolName(str, Enum):
    """Enumeration of tool names."""

    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    UPDATE_FILE = "update_file"
    BASH = "bash"
    GREP = "grep"
    LIST_DIR = "list_dir"
    GLOB = "glob"
    REACT = "react"
    RESEARCH_CODEBASE = "research_codebase"
    WEB_FETCH = "web_fetch"
    PRESENT_PLAN = "present_plan"


READ_ONLY_TOOLS = [
    ToolName.READ_FILE,
    ToolName.GREP,
    ToolName.LIST_DIR,
    ToolName.GLOB,
    ToolName.REACT,
    ToolName.RESEARCH_CODEBASE,
    ToolName.WEB_FETCH,
    ToolName.PRESENT_PLAN,
]

WRITE_TOOLS = [
    ToolName.WRITE_FILE,
    ToolName.UPDATE_FILE,
]

EXECUTE_TOOLS = [
    ToolName.BASH,
]

COMMAND_PREFIX = "/"

# Plan mode sentinel for exit without revision
EXIT_PLAN_MODE_SENTINEL = "__EXIT_PLAN_MODE__"

TUNACODE_HOME_DIR = ".tunacode"
SESSIONS_SUBDIR = "sessions"
DEVICE_ID_FILE = "device_id"

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

UI_THINKING_MESSAGE = "[bold #00d7ff]Thinking...[/bold #00d7ff]"

ERROR_PROVIDER_EMPTY = "Provider number cannot be empty"
ERROR_INVALID_PROVIDER = "Invalid provider number"
ERROR_FILE_NOT_FOUND = "Error: File not found at '{filepath}'."
ERROR_FILE_TOO_LARGE = "Error: File '{filepath}' is too large (> 100KB)."
ERROR_FILE_DECODE = "Error reading file '{filepath}': Could not decode using UTF-8."
ERROR_FILE_DECODE_DETAILS = "It might be a binary file or use a different encoding. {error}"
ERROR_COMMAND_NOT_FOUND = "Error: Command not found or failed to execute:"
ERROR_COMMAND_EXECUTION = (
    "Error: Command not found or failed to execute: {command}. Details: {error}"
)
ERROR_TOOL_CALL_ID_MISSING = "Tool return missing tool_call_id."
ERROR_TOOL_ARGS_MISSING = "Tool args missing for tool_call_id '{tool_call_id}'."

ERROR_DIR_TOO_LARGE = (
    "Error: Directory '{path}' expansion aborted. Total size exceeds {limit_mb:.1f} MB limit."
)
ERROR_DIR_TOO_MANY_FILES = (
    "Error: Directory '{path}' expansion aborted. Exceeds limit of {limit} files."
)

CMD_OUTPUT_NO_OUTPUT = "No output."
CMD_OUTPUT_NO_ERRORS = "No errors."
CMD_OUTPUT_FORMAT = "STDOUT:\n{output}\n\nSTDERR:\n{error}"
CMD_OUTPUT_TRUNCATED = "\n...\n[truncated]\n...\n"


MSG_UPDATE_AVAILABLE = "Update available: v{latest_version}"
MSG_UPDATE_INSTRUCTION = "Exit, and run: [bold]pip install --upgrade tunacode-cli"
MSG_VERSION_DISPLAY = "TunaCode CLI {version}"
MSG_FILE_SIZE_LIMIT = " Please specify a smaller file or use other tools to process it."

JSON_PARSE_MAX_RETRIES = 10
JSON_PARSE_BASE_DELAY = 0.1
JSON_PARSE_MAX_DELAY = 5.0

TOOL_MAX_RETRIES = 3
TOOL_RETRY_BASE_DELAY = 0.5
TOOL_RETRY_MAX_DELAY = 5.0


THEME_NAME = "tunacode"

RESOURCE_BAR_HEIGHT = 1
RESOURCE_BAR_SEPARATOR = " - "
RESOURCE_BAR_TOKEN_FORMAT = "{tokens}/{max_tokens}"  # nosec B105
RESOURCE_BAR_COST_FORMAT = "${cost:.2f}"
RESOURCE_BAR_SESSION_LABEL = "session"

RICHLOG_CLASS_PAUSED = "paused"
RICHLOG_CLASS_STREAMING = "streaming"


def build_tunacode_theme():
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


def build_nextstep_theme():
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
