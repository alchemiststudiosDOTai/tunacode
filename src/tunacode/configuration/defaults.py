"""
Module: tunacode.configuration.defaults

Default configuration values for the TunaCode CLI.
Provides sensible defaults for user configuration and environment variables.
"""

from tunacode.constants import GUIDE_FILE_NAME
from tunacode.types import UserConfig

DEFAULT_USER_CONFIG: UserConfig = {
    "default_model": "openrouter:openai/gpt-4.1",
    "env": {
        "ANTHROPIC_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENROUTER_API_KEY": "",
    },
    "settings": {
        "max_retries": 10,
        "max_iterations": 40,
        "request_delay": 0.0,
        "global_request_timeout": 90.0,
        "tool_ignore": [],
        "guide_file": GUIDE_FILE_NAME,
        "fallback_response": True,
        "fallback_verbosity": "normal",  # Options: minimal, normal, detailed
        "context_window_size": 200000,
        "enable_streaming": True,  # Always enable streaming
        "ripgrep": {
            "use_bundled": False,  # Use system ripgrep binary
            "timeout": 10,  # Search timeout in seconds
            "max_buffer_size": 1048576,  # 1MB max output buffer
            "max_results": 100,  # Maximum results per search
            "enable_metrics": False,  # Enable performance metrics collection
            "debug": False,  # Enable debug logging for ripgrep operations
        },
    },
    "mcpServers": {},
}
