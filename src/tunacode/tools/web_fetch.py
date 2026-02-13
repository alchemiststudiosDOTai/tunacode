"""
Web fetch tool for TunaCode - HTTP GET requests with HTML-to-text conversion.

This tool provides web content fetching with:
- HTTP GET requests with configurable timeout
- HTML-to-text conversion for readable output
- URL security validation (blocks localhost, private IPs, file://)
- Content size limiting (5MB max)

CLAUDE_ANCHOR[web-fetch-module]: HTTP GET with HTML-to-text conversion
"""

import ipaddress
import re
from typing import NoReturn
from urllib.parse import urlparse

import html2text
import httpx

from tunacode.exceptions import ToolRetryError

from tunacode.tools.decorators import base_tool

# Constants
MAX_CONTENT_SIZE = 5 * 1024 * 1024  # 5MB
MAX_OUTPUT_SIZE = 100 * 1024  # 100KB for output truncation
DEFAULT_TIMEOUT = 60  # seconds
USER_AGENT = "TunaCode/1.0 (https://tunacode.xyz)"

# Private IP ranges to block
PRIVATE_IP_PATTERNS = [
    re.compile(r"^127\."),  # 127.x.x.x
    re.compile(r"^10\."),  # 10.x.x.x
    re.compile(r"^172\.(1[6-9]|2[0-9]|3[01])\."),  # 172.16-31.x.x
    re.compile(r"^192\.168\."),  # 192.168.x.x
    re.compile(r"^0\."),  # 0.x.x.x
    re.compile(r"^169\.254\."),  # Link-local
    re.compile(r"^::1$"),  # IPv6 localhost
    re.compile(r"^fe80:"),  # IPv6 link-local
    re.compile(r"^fc00:"),  # IPv6 unique local
    re.compile(r"^fd00:"),  # IPv6 unique local
]

# Blocked hostnames
BLOCKED_HOSTNAMES = frozenset(
    [
        "localhost",
        "localhost.localdomain",
        "local",
        "0.0.0.0",  # nosec B104 - this is a blocklist, not a bind address
        "127.0.0.1",
        "::1",
    ]
)


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is private/reserved."""
    for pattern in PRIVATE_IP_PATTERNS:
        if pattern.match(ip_str):
            return True

    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except ValueError:
        return False


def _validate_url(url: str) -> str:
    """Validate URL for security.

    Args:
        url: URL to validate

    Returns:
        Validated URL

    Raises:
        ToolRetryError: If URL is invalid or blocked
    """
    if not url or not url.strip():
        raise ToolRetryError("URL cannot be empty.")

    url = url.strip()

    try:
        parsed = urlparse(url)
    except Exception as err:
        raise ToolRetryError(f"Invalid URL format: {url}") from err

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        raise ToolRetryError(
            f"Invalid URL scheme '{parsed.scheme}'. Only http:// and https:// are allowed."
        )

    # Check hostname presence
    if not parsed.hostname:
        raise ToolRetryError(f"URL missing hostname: {url}")

    hostname = parsed.hostname.lower()

    # Block known localhost hostnames
    if hostname in BLOCKED_HOSTNAMES:
        raise ToolRetryError(f"Blocked URL: {url}. Cannot fetch from localhost or local addresses.")

    # Check if hostname is an IP address and validate
    if _is_private_ip(hostname):
        raise ToolRetryError(
            f"Blocked URL: {url}. Cannot fetch from private or reserved IP addresses."
        )

    return url


def _convert_html_to_text(html_content: str) -> str:
    """Convert HTML to readable plain text.

    Args:
        html_content: Raw HTML content

    Returns:
        Plain text extracted from HTML
    """
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_emphasis = False
    converter.body_width = 80
    converter.unicode_snob = True
    converter.skip_internal_links = True

    return converter.handle(html_content)


def _truncate_output(content: str, max_size: int = MAX_OUTPUT_SIZE) -> str:
    """Truncate content if it exceeds max size.

    Args:
        content: Content to truncate
        max_size: Maximum size in bytes

    Returns:
        Truncated content with indicator if truncated
    """
    if len(content.encode("utf-8")) <= max_size:
        return content

    # Truncate to approximate character count
    truncated = content[: max_size // 2]
    return truncated + "\n\n... [Content truncated due to size] ..."


def _raise_content_too_large(size: int) -> None:
    """Raise ToolRetryError for oversized content."""
    raise ToolRetryError(
        f"Content too large ({size // 1024 // 1024}MB). "
        f"Maximum allowed is {MAX_CONTENT_SIZE // 1024 // 1024}MB."
    )


async def _head_check_size(client: httpx.AsyncClient, validated_url: str) -> None:
    """Pre-flight HEAD request to reject oversized responses early."""
    try:
        head_response = await client.head(validated_url)
        content_length = head_response.headers.get("content-length")
        if content_length and int(content_length) > MAX_CONTENT_SIZE:
            _raise_content_too_large(int(content_length))
    except httpx.HTTPError:
        pass  # HEAD failed, proceed with GET


def _decode_response(content: bytes) -> str:
    """Decode response bytes, falling back to latin-1."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1", errors="replace")


def _maybe_convert_html(text_content: str, content_type: str) -> str:
    """Convert HTML to text if the response is HTML."""
    if "text/html" in content_type or "<html" in text_content[:1000].lower():
        return _convert_html_to_text(text_content)
    return text_content


async def _fetch_and_process(client: httpx.AsyncClient, validated_url: str) -> str:
    """Fetch URL content, validate redirect, decode, and convert."""
    await _head_check_size(client, validated_url)

    response = await client.get(validated_url)
    response.raise_for_status()

    final_url = str(response.url)
    if final_url != validated_url:
        _validate_url(final_url)

    content = response.content
    if len(content) > MAX_CONTENT_SIZE:
        _raise_content_too_large(len(content))

    text_content = _decode_response(content)
    content_type = response.headers.get("content-type", "").lower()
    text_content = _maybe_convert_html(text_content, content_type)
    return _truncate_output(text_content)


_HTTP_STATUS_MESSAGES: dict[int, str] = {
    404: "Page not found (404): {url}. Check the URL.",
    403: "Access forbidden (403): {url}. The page may require authentication.",
    429: "Rate limited (429): {url}. Try again later.",
}


def _handle_http_error(url: str, err: httpx.HTTPStatusError) -> NoReturn:
    """Convert httpx.HTTPStatusError to ToolRetryError."""
    status = err.response.status_code
    template = _HTTP_STATUS_MESSAGES.get(status)
    if template:
        raise ToolRetryError(template.format(url=url)) from err
    if status >= 500:
        raise ToolRetryError(f"Server error ({status}): {url}. The server may be down.") from err
    raise ToolRetryError(f"HTTP error {status} fetching {url}") from err


@base_tool
async def web_fetch(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Fetch web content from a URL and return as readable text.

    Args:
        url: The URL to fetch (http:// or https://)
        timeout: Request timeout in seconds (default: 60)

    Returns:
        Readable text content from the URL
    """
    validated_url = _validate_url(url)
    timeout = max(5, min(timeout, 120))

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            max_redirects=5,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            return await _fetch_and_process(client, validated_url)

    except httpx.TimeoutException as err:
        msg = f"Request timed out after {timeout} seconds. Try again or use a shorter timeout."
        raise ToolRetryError(msg) from err
    except httpx.TooManyRedirects as err:
        msg = f"Too many redirects while fetching {url}. The URL may be invalid."
        raise ToolRetryError(msg) from err
    except httpx.HTTPStatusError as err:
        _handle_http_error(url, err)
    except httpx.RequestError as err:
        raise ToolRetryError(f"Failed to connect to {url}: {err}") from err
