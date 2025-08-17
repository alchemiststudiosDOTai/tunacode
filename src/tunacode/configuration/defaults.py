"""
Module: tunacode.configuration.defaults

Default configuration values for the TunaCode CLI.
Provides sensible defaults for user configuration and environment variables.
"""

from tunacode.constants import GUIDE_FILE_NAME, ToolName
from tunacode.types import UserConfig

DEFAULT_USER_CONFIG: UserConfig = {
    "default_model": "openai:gpt-4.1",
    "env": {
        "ANTHROPIC_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENROUTER_API_KEY": "",
    },
    "settings": {
        "max_retries": 10,
        "max_iterations": 40,
        "tool_ignore": [ToolName.READ_FILE],
        "guide_file": GUIDE_FILE_NAME,
        "fallback_response": True,
        "fallback_verbosity": "normal",  # Options: minimal, normal, detailed
        "context_window_size": 200000,
        "enable_tutorial": True,
        "enable_streaming": True,
        "first_installation_date": None,  # Set during first setup
    },
    "mcpServers": {},
}
