"""Tool-specific configuration settings for TunaCode.

This module provides configuration management for individual tools,
allowing per-tool customization of behavior, limits, and features.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tunacode.types import UserConfig


class ToolConfigManager:
    """Manages configuration for individual tools."""
    
    def __init__(self, user_config: UserConfig | None = None):
        self.user_config = user_config or {}
        self._tool_configs: dict[str, Any] = {}
    
    def get_tool_config(self, tool_name: str) -> dict[str, Any]:
        """Get configuration for a specific tool.
        
        Args:
            tool_name: Name of the tool (e.g., "web_fetch", "ripgrep")
            
        Returns:
            Tool configuration dictionary, merged with defaults
        """
        # Get user's tool config if exists
        user_tool_config = self.user_config.get("settings", {}).get("tools", {}).get(tool_name, {})
        
        # Get defaults for this tool
        default_tool_config = self._get_tool_defaults(tool_name)
        
        # Merge user config over defaults
        return {**default_tool_config, **user_tool_config}
    
    def _get_tool_defaults(self, tool_name: str) -> dict[str, Any]:
        """Get default configuration for a specific tool."""
        defaults = {
            "web_fetch": {
                "max_content_size_mb": 5,
                "max_output_size_kb": 100,
                "default_timeout_seconds": 60,
                "user_agent": "TunaCode/1.0 (https://tunacode.xyz)",
                "max_redirects": 5,
                "enable_stealth_mode": False,
                "block_private_ips": True,
                "follow_redirects": True,
            },
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
            }
        }
        return defaults.get(tool_name, {})
    
    def validate_tool_config(self, tool_name: str, config: dict[str, Any]) -> list[str]:
        """Validate tool configuration values.
        
        Args:
            tool_name: Name of the tool to validate
            config: Configuration dictionary to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if tool_name == "web_fetch":
            errors.extend(self._validate_web_fetch_config(config))
        elif tool_name == "ripgrep":
            errors.extend(self._validate_ripgrep_config(config))
        elif tool_name == "lsp":
            errors.extend(self._validate_lsp_config(config))
        
        return errors
    
    def _validate_web_fetch_config(self, config: dict[str, Any]) -> list[str]:
        """Validate web fetch specific configuration."""
        errors = []
        
        # Validate max_content_size_mb
        if "max_content_size_mb" in config:
            size = config["max_content_size_mb"]
            if not isinstance(size, (int, float)) or size <= 0 or size > 100:
                errors.append("max_content_size_mb must be between 0.1 and 100")
        
        # Validate max_output_size_kb
        if "max_output_size_kb" in config:
            size = config["max_output_size_kb"]
            if not isinstance(size, (int, float)) or size <= 0 or size > 10000:
                errors.append("max_output_size_kb must be between 0.1 and 10000")
        
        # Validate default_timeout_seconds
        if "default_timeout_seconds" in config:
            timeout = config["default_timeout_seconds"]
            if not isinstance(timeout, (int, float)) or timeout < 5 or timeout > 300:
                errors.append("default_timeout_seconds must be between 5 and 300")
        
        # Validate max_redirects
        if "max_redirects" in config:
            redirects = config["max_redirects"]
            if not isinstance(redirects, int) or redirects < 0 or redirects > 20:
                errors.append("max_redirects must be between 0 and 20")
        
        return errors
    
    def _validate_ripgrep_config(self, config: dict[str, Any]) -> list[str]:
        """Validate ripgrep specific configuration."""
        errors = []
        
        if "timeout" in config:
            if not isinstance(config["timeout"], (int, float)) or config["timeout"] <= 0:
                errors.append("timeout must be a positive number")
        
        if "max_buffer_size" in config:
            size = config["max_buffer_size"]
            if not isinstance(size, int) or size <= 0 or size > 10 * 1024 * 1024:
                errors.append("max_buffer_size must be between 1 and 10MB")
        
        if "max_results" in config:
            if not isinstance(config["max_results"], int) or config["max_results"] <= 0:
                errors.append("max_results must be a positive integer")
        
        return errors
    
    def _validate_lsp_config(self, config: dict[str, Any]) -> list[str]:
        """Validate LSP specific configuration."""
        errors = []
        
        if "timeout" in config:
            if not isinstance(config["timeout"], (int, float)) or config["timeout"] <= 0:
                errors.append("timeout must be a positive number")
        
        if "max_diagnostics" in config:
            if not isinstance(config["max_diagnostics"], int) or config["max_diagnostics"] <= 0:
                errors.append("max_diagnostics must be a positive integer")
        
        return errors