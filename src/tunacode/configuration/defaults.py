"""
Module: tunacode.configuration.defaults

Default configuration values for the TunaCode CLI.
Provides sensible defaults for user configuration and environment variables.
"""

from tunacode.constants import ENV_OPENAI_BASE_URL, GUIDE_FILE_NAME
from tunacode.types import UserConfig

DEFAULT_USER_CONFIG: UserConfig = {
    "default_model": "openrouter:openai/gpt-4.1",
    "env": {
        "ANTHROPIC_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "",
        ENV_OPENAI_BASE_URL: "",
        "OPENROUTER_API_KEY": "",
    },
    "settings": {
        "max_retries": 3,
        "max_iterations": 40,
        "request_delay": 0.0,
        "global_request_timeout": 120.0,
        "tool_ignore": [],
        "guide_file": GUIDE_FILE_NAME,
        "fallback_response": True,
        "fallback_verbosity": "normal",
        "context_window_size": 200000,
        "enable_streaming": True,
        "theme": "dracula",
        "ripgrep": {
            "timeout": 10,
            "max_buffer_size": 1048576,
            "max_results": 100,
            "enable_metrics": False,
            "debug": False,
        },
        "lsp": {
            "enabled": True,
            "timeout": 5.0,
            "max_diagnostics": 20,
        },
    },
}
