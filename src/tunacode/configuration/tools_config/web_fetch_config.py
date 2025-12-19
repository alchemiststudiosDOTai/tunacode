"""Web fetch tool configuration.

This module provides configuration and validation specifically for the web fetch tool,
including size limits, timeouts, and security settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any

from tunacode.configuration.tools_config import ToolConfigManager


class UrlScheme(str, Enum):
    HTTP = "http"
    HTTPS = "https"


class BlockedHostname(str, Enum):
    LOCALHOST = "localhost"
    LOCALHOST_LOCALDOMAIN = "localhost.localdomain"
    LOCAL = "local"


class HeaderName(str, Enum):
    CONTENT_LENGTH = "content-length"
    CONTENT_TYPE = "content-type"
    USER_AGENT = "User-Agent"


class HtmlToken(str, Enum):
    CONTENT_TYPE = "text/html"
    TAG_MARKER = "<html"


class HttpStatus(IntEnum):
    FORBIDDEN = 403
    METHOD_NOT_ALLOWED = 405
    NOT_FOUND = 404
    NOT_IMPLEMENTED = 501
    TOO_MANY_REQUESTS = 429
    SERVER_ERROR_MIN = 500


ALLOWED_SCHEMES: tuple[str, ...] = tuple(scheme.value for scheme in UrlScheme)
BLOCKED_HOSTNAMES: frozenset[str] = frozenset(hostname.value for hostname in BlockedHostname)
BYTES_PER_KB = 1024
BYTES_PER_MB = BYTES_PER_KB * BYTES_PER_KB
HTML_SNIFF_BYTES = 1000
HTML2TEXT_BODY_WIDTH = 80
MAX_TIMEOUT_SECONDS = 300
MIN_TIMEOUT_SECONDS = 5
MIN_CONTENT_LENGTH_BYTES = 0
TRUNCATION_DIVISOR = 2
TRUNCATION_NOTICE = "\n\n... [Content truncated due to size] ..."
UTF8_ENCODING = "utf-8"
STEALTH_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/119.0.0.0 Safari/537.36"
)

HEAD_UNSUPPORTED_STATUSES: frozenset[int] = frozenset(
    [
        HttpStatus.METHOD_NOT_ALLOWED,
        HttpStatus.NOT_IMPLEMENTED,
    ]
)


@dataclass(frozen=True)
class WebFetchSettings:
    max_content_size_bytes: int
    max_output_size_bytes: int
    default_timeout_seconds: int
    max_redirects: int
    follow_redirects: bool
    user_agent: str
    enable_stealth_mode: bool
    block_private_ips: bool


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
        return int(size_mb * BYTES_PER_MB)

    @property
    def max_output_size_bytes(self) -> int:
        """Maximum output size in bytes."""
        size_kb = self._config.get("max_output_size_kb", self.DEFAULT_MAX_OUTPUT_SIZE_KB)
        return int(size_kb * BYTES_PER_KB)

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
            "max_content_size_mb": self.max_content_size_bytes / BYTES_PER_MB,
            "max_output_size_kb": self.max_output_size_bytes / BYTES_PER_KB,
            "default_timeout_seconds": self.default_timeout_seconds,
            "user_agent": self.user_agent,
            "max_redirects": self.max_redirects,
            "enable_stealth_mode": self.enable_stealth_mode,
            "block_private_ips": self.block_private_ips,
            "follow_redirects": self.follow_redirects,
        }
