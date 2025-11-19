"""
Module: tunacode.constants

Global constants and configuration values for the TunaCode CLI application.
Centralizes all magic strings, UI text, error messages, and application constants.
"""

from enum import Enum

# Application info
APP_NAME = "TunaCode"
APP_VERSION = "0.0.78.10"


# File patterns
GUIDE_FILE_PATTERN = "{name}.md"
GUIDE_FILE_NAME = "AGENTS.md"
ENV_FILE = ".env"
CONFIG_FILE_NAME = "tunacode.json"

# Default limits
MAX_FILE_SIZE = 100 * 1024  # 100KB
MAX_COMMAND_OUTPUT = 5000  # 5000 chars
MAX_FILES_IN_DIR = 50
MAX_TOTAL_DIR_SIZE = 2 * 1024 * 1024  # 2 MB
DEFAULT_CONTEXT_WINDOW = 200000  # 200k tokens


# Command output processing
COMMAND_OUTPUT_THRESHOLD = 3500  # Length threshold for truncation
COMMAND_OUTPUT_START_INDEX = 2500  # Where to start showing content
COMMAND_OUTPUT_END_SIZE = 1000  # How much to show from the end


class ToolName(str, Enum):
    """Enumeration of tool names."""

    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    UPDATE_FILE = "update_file"
    RUN_COMMAND = "run_command"
    BASH = "bash"
    GREP = "grep"
    LIST_DIR = "list_dir"
    GLOB = "glob"
    REACT = "react"
    RESEARCH_CODEBASE = "research_codebase"


# Tool names (backward compatibility)
TOOL_READ_FILE = ToolName.READ_FILE
TOOL_WRITE_FILE = ToolName.WRITE_FILE
TOOL_UPDATE_FILE = ToolName.UPDATE_FILE
TOOL_RUN_COMMAND = ToolName.RUN_COMMAND
TOOL_BASH = ToolName.BASH
TOOL_GREP = ToolName.GREP
TOOL_LIST_DIR = ToolName.LIST_DIR
TOOL_GLOB = ToolName.GLOB
TOOL_REACT = ToolName.REACT
TOOL_RESEARCH_CODEBASE = ToolName.RESEARCH_CODEBASE

# Tool categorization
READ_ONLY_TOOLS = [
    ToolName.READ_FILE,
    ToolName.GREP,
    ToolName.LIST_DIR,
    ToolName.GLOB,
    ToolName.REACT,
    ToolName.RESEARCH_CODEBASE,
]
WRITE_TOOLS = [ToolName.WRITE_FILE, ToolName.UPDATE_FILE]
EXECUTE_TOOLS = [ToolName.BASH, ToolName.RUN_COMMAND]

# Commands
CMD_HELP = "/help"
CMD_CLEAR = "/clear"
CMD_DUMP = "/dump"
CMD_YOLO = "/yolo"
CMD_COMPACT = "/compact"
CMD_MODEL = "/model"
CMD_EXIT = "exit"
CMD_QUIT = "quit"

# Command descriptions
DESC_HELP = "Show this help message"
DESC_CLEAR = "Clear the conversation history"
DESC_DUMP = "Show the current conversation history"
DESC_YOLO = "Toggle confirmation prompts on/off"
DESC_COMPACT = "Summarize the conversation context"
DESC_MODEL = "List available models"
DESC_MODEL_SWITCH = "Switch to a specific model"
DESC_MODEL_DEFAULT = "Set a model as the default"
DESC_EXIT = "Exit the application"

# Command Configuration
COMMAND_PREFIX = "/"
COMMAND_CATEGORIES = {
    "state": ["yolo"],
    "debug": ["dump", "compact"],
    "ui": ["clear", "help"],
    "config": ["model"],
}

# System paths
TUNACODE_HOME_DIR = ".tunacode"
SESSIONS_SUBDIR = "sessions"
DEVICE_ID_FILE = "device_id"

# UI colors - Professional monochromatic cyan scheme
UI_COLORS = {
    # Core brand colors
    "primary": "#00d7ff",  # Bright cyan (primary accent)
    "primary_light": "#4de4ff",  # Light cyan for hover states
    "primary_dark": "#0095b3",  # Dark cyan for interactive elements
    "accent": "#0ea5e9",  # Rich cyan (replaces purple)
    # Background & structure (cyan-tinted grays)
    "background": "#0d1720",  # Ultra dark with cyan undertone
    "surface": "#162332",  # Panels, cards
    "border": "#2d4461",  # Stronger cyan-gray borders
    "border_light": "#1e2d3f",  # Subtle borders
    # Text & content (cyan-tinted neutrals)
    "muted": "#6b8aa3",  # Secondary text, descriptions
    "secondary": "#4a6582",  # Tertiary text, less important
    # Semantic colors (professional, muted)
    "success": "#059669",  # Corporate emerald green
    "warning": "#d97706",  # Muted amber
    "error": "#dc2626",  # Clean red
    # Legacy compatibility
    "file_ref": "#00d7ff",  # Same as primary
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
