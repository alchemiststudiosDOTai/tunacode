"""
Module: tunacode.configuration.defaults

Default configuration values for the TunaCode CLI.
Provides sensible defaults for user configuration and environment variables.
"""

from tunacode.constants import ENV_OPENAI_BASE_URL, MAX_COMMAND_OUTPUT
from tunacode.types import UserConfig

DEFAULT_USER_CONFIG: UserConfig = {
    "default_model": "openrouter:openai/gpt-4.1",
    "recent_models": [],
    "env": {
        "ANTHROPIC_API_KEY": "",
        "GEMINI_API_KEY": "",
        "MINIMAX_API_KEY": "",
        "MINIMAX_CN_API_KEY": "",
        "OPENAI_API_KEY": "",
        ENV_OPENAI_BASE_URL: "",
        "OPENROUTER_API_KEY": "",
    },
    "settings": {
        "max_retries": 3,
        "max_iterations": 40,
        "request_delay": 0.0,
        "global_request_timeout": 600.0,
        "tool_strict_validation": False,
        "theme": "dracula",
        "stream_agent_text": False,
        "max_command_output": MAX_COMMAND_OUTPUT,
        "max_tokens": None,
        "ripgrep": {
            "timeout": 10,
            "max_results": 100,
            "enable_metrics": False,
        },
        "lsp": {
            "enabled": True,
            "timeout": 5.0,
        },
    },
}
