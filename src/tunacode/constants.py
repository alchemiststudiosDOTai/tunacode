"""
Module: tunacode.constants

Global constants and configuration values for the TunaCode CLI application.
Centralizes all magic strings, UI text, error messages, and application constants.
"""

from enum import Enum

# Application info
APP_NAME = "TunaCode"
APP_VERSION = "0.1.15"


# File patterns
GUIDE_FILE_NAME = "AGENTS.md"
ENV_FILE = ".env"
CONFIG_FILE_NAME = "tunacode.json"

# Default limits
MAX_FILE_SIZE = 100 * 1024  # 100KB
MAX_COMMAND_OUTPUT = 5000  # 5000 chars
DEFAULT_READ_LIMIT = 2000  # Max lines per read_file call
MAX_LINE_LENGTH = 2000  # Truncate lines beyond this length
MAX_FILES_IN_DIR = 50
MAX_TOTAL_DIR_SIZE = 2 * 1024 * 1024  # 2 MB
DEFAULT_CONTEXT_WINDOW = 200000  # 200k tokens

# Display truncation limits (NeXTSTEP information hierarchy)
MAX_CALLBACK_CONTENT = 50_000  # Emergency safety - prevents UI freeze
MAX_PANEL_LINES = 30  # Focus zone limit for tool results
MAX_PANEL_LINE_WIDTH = 200  # Individual line truncation
MAX_SEARCH_RESULTS_DISPLAY = 20  # Search results shown before "+N more"

# Tool panel viewport sizing (standardized across all renderers)
LINES_RESERVED_FOR_HEADER_FOOTER = 4  # Header, params, separators, status
TOOL_VIEWPORT_LINES = 10  # Fixed viewport height for uniform panels
MIN_VIEWPORT_LINES = TOOL_VIEWPORT_LINES  # Min equals max for consistency

# File autocomplete settings
AUTOCOMPLETE_MAX_DEPTH = 3  # Levels deep from current prefix (sliding window)
AUTOCOMPLETE_RESULT_LIMIT = 50

# Command output processing
COMMAND_OUTPUT_THRESHOLD = 3500  # Length threshold for truncation
COMMAND_OUTPUT_START_INDEX = 2500  # Where to start showing content
COMMAND_OUTPUT_END_SIZE = 1000  # How much to show from the end


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


# Tool names (backward compatibility)
TOOL_READ_FILE = ToolName.READ_FILE
TOOL_WRITE_FILE = ToolName.WRITE_FILE
TOOL_UPDATE_FILE = ToolName.UPDATE_FILE
TOOL_BASH = ToolName.BASH
TOOL_GREP = ToolName.GREP
TOOL_LIST_DIR = ToolName.LIST_DIR
TOOL_GLOB = ToolName.GLOB

# Tool categorization
READ_ONLY_TOOLS = [
    ToolName.READ_FILE,
    ToolName.GREP,
    ToolName.LIST_DIR,
    ToolName.GLOB,
    ToolName.REACT,
    ToolName.RESEARCH_CODEBASE,
    ToolName.WEB_FETCH,
]
WRITE_TOOLS = [ToolName.WRITE_FILE, ToolName.UPDATE_FILE]
EXECUTE_TOOLS = [ToolName.BASH]

# Commands
CMD_HELP = "/help"
CMD_CLEAR = "/clear"
CMD_YOLO = "/yolo"
CMD_MODEL = "/model"
CMD_EXIT = "exit"
CMD_QUIT = "quit"

# Command descriptions
DESC_HELP = "Show this help message"
DESC_CLEAR = "Clear the conversation history"
DESC_YOLO = "Toggle confirmation prompts on/off"
DESC_MODEL = "List available models"
DESC_EXIT = "Exit the application"

# Command Configuration
COMMAND_PREFIX = "/"

# System paths
TUNACODE_HOME_DIR = ".tunacode"
SESSIONS_SUBDIR = "sessions"
DEVICE_ID_FILE = "device_id"

# UI colors - High contrast neutral scheme (matches reference)
UI_COLORS = {
    # Backgrounds (neutral, not cyan-tinted)
    "background": "#1a1a1a",  # Near black
    "surface": "#252525",  # Panels, slightly lighter
    "border": "#ff6b9d",  # Magenta borders
    # Text (HIGH CONTRAST)
    "text": "#e0e0e0",  # Primary text - light gray
    "muted": "#808080",  # Secondary text
    # Accents (used sparingly)
    "primary": "#00d7d7",  # Cyan - model, tokens
    "accent": "#ff6b9d",  # Magenta - brand
    "success": "#4ec9b0",  # Green - costs
    "warning": "#c3e88d",  # Yellow/lime
    "error": "#f44747",  # Red
}

# NeXTSTEP theme colors - Classic 1990s monochrome (high contrast)
NEXTSTEP_COLORS = {
    # Desktop/app background - medium gray
    "background": "#acacac",
    # Window content area - lighter gray
    "surface": "#c8c8c8",
    "window_content": "#d0d0d0",
    # Title bar - dark charcoal (distinctive NeXTSTEP look)
    "title_bar": "#3a3a3a",
    "title_bar_text": "#e0e0e0",
    # Borders - strong definition
    "border": "#2a2a2a",
    # Text - BLACK on light gray = MAXIMUM contrast
    "text": "#000000",
    "muted": "#404040",
    # 3D Bevel effect (essential for NeXTSTEP)
    "bevel_light": "#e8e8e8",  # Top/left highlight
    "bevel_dark": "#606060",  # Bottom/right shadow
    # PURE MONOCHROME - all accents are grayscale
    "primary": "#1a1a1a",
    "accent": "#3a3a3a",
    "success": "#2a2a2a",
    "warning": "#4a4a4a",
    "error": "#1a1a1a",
}

# UI text and formatting
UI_PROMPT_PREFIX = '<style fg="#00d7ff"><b>> </b></style>'
UI_THINKING_MESSAGE = "[bold #00d7ff]Thinking...[/bold #00d7ff]"
UI_DARKGREY_OPEN = "<darkgrey>"
UI_DARKGREY_CLOSE = "</darkgrey>"
UI_BOLD_OPEN = "<bold>"
UI_BOLD_CLOSE = "</bold>"
UI_KEY_ENTER = "Enter"
UI_KEY_ESC_ENTER = "Esc + Enter"

# Panel titles
PANEL_ERROR = "Error"
PANEL_MESSAGE_HISTORY = "Message History"
PANEL_MODELS = "Models"
PANEL_AVAILABLE_COMMANDS = "Available Commands"

# Error messages
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
# Directory expansion errors
ERROR_DIR_TOO_LARGE = (
    "Error: Directory '{path}' expansion aborted. Total size exceeds {limit_mb:.1f} MB limit."
)
ERROR_DIR_TOO_MANY_FILES = (
    "Error: Directory '{path}' expansion aborted. Exceeds limit of {limit} files."
)

# Command output messages
CMD_OUTPUT_NO_OUTPUT = "No output."
CMD_OUTPUT_NO_ERRORS = "No errors."
CMD_OUTPUT_FORMAT = "STDOUT:\n{output}\n\nSTDERR:\n{error}"
CMD_OUTPUT_TRUNCATED = "\n...\n[truncated]\n...\n"


# Log/status messages
MSG_UPDATE_AVAILABLE = "Update available: v{latest_version}"
MSG_UPDATE_INSTRUCTION = "Exit, and run: [bold]pip install --upgrade tunacode-cli"
MSG_VERSION_DISPLAY = "TunaCode CLI {version}"
MSG_FILE_SIZE_LIMIT = " Please specify a smaller file or use other tools to process it."

# JSON parsing retry configuration
JSON_PARSE_MAX_RETRIES = 10
JSON_PARSE_BASE_DELAY = 0.1  # Initial delay in seconds
JSON_PARSE_MAX_DELAY = 5.0  # Maximum delay in seconds

# Tool execution retry configuration
TOOL_MAX_RETRIES = 3
TOOL_RETRY_BASE_DELAY = 0.5  # seconds
TOOL_RETRY_MAX_DELAY = 5.0  # seconds


# Textual TUI Theme
THEME_NAME = "tunacode"

# ResourceBar display constants (NeXTSTEP: Persistent Status Zone)
RESOURCE_BAR_HEIGHT = 1
RESOURCE_BAR_SEPARATOR = " - "
RESOURCE_BAR_TOKEN_FORMAT = "{tokens}/{max_tokens}"  # nosec B105 - not a password
RESOURCE_BAR_COST_FORMAT = "${cost:.2f}"
RESOURCE_BAR_SESSION_LABEL = "session"

# RichLog pause mode CSS class (NeXTSTEP: Mode Visibility)
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
        foreground=p["text"],  # KEY: Light gray for readable text
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
        dark=False,  # LIGHT theme - authentic NeXTSTEP
        primary=p["primary"],
        secondary=p["muted"],
        accent=p["accent"],
        background=p["background"],
        surface=p["surface"],
        panel=p["surface"],
        success=p["success"],
        warning=p["warning"],
        error=p["error"],
        foreground=p["text"],  # Black text on gray
        variables={
            "text-muted": p["muted"],
            "border": p["border"],
            # NeXTSTEP 3D bevel colors
            "bevel-light": p["bevel_light"],
            "bevel-dark": p["bevel_dark"],
            # Title bar styling
            "title-bar": p["title_bar"],
            "title-bar-text": p["title_bar_text"],
            # Window content
            "window-content": p["window_content"],
        },
    )
