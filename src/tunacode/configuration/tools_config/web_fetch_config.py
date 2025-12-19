"""Web fetch tool configuration.

This module provides configuration and validation specifically for the web fetch tool,
including size limits, timeouts, and security settings.
"""

from __future__ import annotations

from typing import Any

from tunacode.configuration.tools_config import ToolConfigManager


class WebFetchConfig:
    """Configuration manager for the web fetch tool."""
    
    # Default constants (for backward compatibility)
    DEFAULT_MAX_CONTENT_SIZE_MB = 5
    DEFAULT_MAX_OUTPUT_SIZE_KB = 100  
    DEFAULT_TIMEOUT_SECONDS = 60
    DEFAULT_USER_AGENT = "TunaCode/1.0 (https://tunacode.xyz)"
    DEFAULT_MAX_REDIRECTS = 5
    
    def __init__(self, user_config: dict[str, Any] | None = None):
        self.config_manager = ToolConfigManager(user_config)
        self._config = self.config_manager.get_tool_config("web_fetch")
    
    @property
    def max_content_size_bytes(self) -> int:
        """Maximum content size in bytes."""
        size_mb = self._config.get("max_content_size_mb", self.DEFAULT_MAX_CONTENT_SIZE_MB)
        return int(size_mb * 1024 * 1024)
    
    @property
    def max_output_size_bytes(self) -> int:
        """Maximum output size in bytes."""
        size_kb = self._config.get("max_output_size_kb", self.DEFAULT_MAX_OUTPUT_SIZE_KB)
        return int(size_kb * 1024)
    
    @property
    def default_timeout_seconds(self) -> int:
        """Default timeout in seconds."""
        return int(self._config.get("default_timeout_seconds", self.DEFAULT_TIMEOUT_SECONDS))
    
    @property
    def user_agent(self) -> str:
        """User agent string."""
        return self._config.get("user_agent", self.DEFAULT_USER_AGENT)
    
    @property
    def max_redirects(self) -> int:
        """Maximum number of redirects to follow."""
        return int(self._config.get("max_redirects", self.DEFAULT_MAX_REDIRECTS))
    
    @property
    def enable_stealth_mode(self) -> bool:
        """Whether to enable stealth mode (future feature)."""
        return bool(self._config.get("enable_stealth_mode", False))
    
    @property
    def block_private_ips(self) -> bool:
        """Whether to block requests to private IPs."""
        return bool(self._config.get("block_private_ips", True))
    
    @property
    def follow_redirects(self) -> bool:
        """Whether to follow redirects."""
        return bool(self._config.get("follow_redirects", True))
    
    def validate_config(self) -> list[str]:
        """Validate current configuration.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        return self.config_manager.validate_tool_config("web_fetch", self._config)
    
    def get_config_summary(self) -> dict[str, Any]:
        """Get a summary of current configuration for debugging."""
        return {
            "max_content_size_mb": self.max_content_size_bytes / (1024 * 1024),
            "max_output_size_kb": self.max_output_size_bytes / 1024,
            "default_timeout_seconds": self.default_timeout_seconds,
            "user_agent": self.user_agent,
            "max_redirects": self.max_redirects,
            "enable_stealth_mode": self.enable_stealth_mode,
            "block_private_ips": self.block_private_ips,
            "follow_redirects": self.follow_redirects,
        }