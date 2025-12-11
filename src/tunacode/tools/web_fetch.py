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
from urllib.parse import urlparse

import html2text
import httpx
from pydantic_ai.exceptions import ModelRetry

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
        ModelRetry: If URL is invalid or blocked
    """
    if not url or not url.strip():
        raise ModelRetry("URL cannot be empty.")

    url = url.strip()

    try:
        parsed = urlparse(url)
    except Exception as err:
        raise ModelRetry(f"Invalid URL format: {url}") from err

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        raise ModelRetry(
            f"Invalid URL scheme '{parsed.scheme}'. Only http:// and https:// are allowed."
        )

    # Check hostname presence
    if not parsed.hostname:
        raise ModelRetry(f"URL missing hostname: {url}")

    hostname = parsed.hostname.lower()

    # Block known localhost hostnames
    if hostname in BLOCKED_HOSTNAMES:
        raise ModelRetry(f"Blocked URL: {url}. Cannot fetch from localhost or local addresses.")

    # Check if hostname is an IP address and validate
    if _is_private_ip(hostname):
        raise ModelRetry(f"Blocked URL: {url}. Cannot fetch from private or reserved IP addresses.")

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
    # Validate URL security
    validated_url = _validate_url(url)

    # Clamp timeout to reasonable bounds
    timeout = max(5, min(timeout, 120))

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            max_redirects=5,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            # First, do a HEAD request to check content size
            try:
                head_response = await client.head(validated_url)
                content_length = head_response.headers.get("content-length")
                if content_length and int(content_length) > MAX_CONTENT_SIZE:
                    raise ModelRetry(
                        f"Content too large ({int(content_length) // 1024 // 1024}MB). "
                        f"Maximum allowed is {MAX_CONTENT_SIZE // 1024 // 1024}MB."
                    )
            except httpx.HTTPError:
                # HEAD failed, proceed with GET and stream check
                pass

            # Fetch the actual content
            response = await client.get(validated_url)
            response.raise_for_status()

            # Check final URL after redirects for security
            final_url = str(response.url)
            if final_url != validated_url:
                _validate_url(final_url)

            # Check content size
            content = response.content
            if len(content) > MAX_CONTENT_SIZE:
                raise ModelRetry(
                    f"Content too large ({len(content) // 1024 // 1024}MB). "
                    f"Maximum allowed is {MAX_CONTENT_SIZE // 1024 // 1024}MB."
                )

            # Decode content
            try:
                text_content = content.decode("utf-8")
            except UnicodeDecodeError:
                text_content = content.decode("latin-1", errors="replace")

            # Convert HTML to text if content is HTML
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type or "<html" in text_content[:1000].lower():
                text_content = _convert_html_to_text(text_content)

            # Truncate if too large
            text_content = _truncate_output(text_content)

            return text_content

    except httpx.TimeoutException as err:
        msg = f"Request timed out after {timeout} seconds. Try again or use a shorter timeout."
        raise ModelRetry(msg) from err
    except httpx.TooManyRedirects as err:
        msg = f"Too many redirects while fetching {url}. The URL may be invalid."
        raise ModelRetry(msg) from err
    except httpx.HTTPStatusError as err:
        status = err.response.status_code
        if status == 404:
            raise ModelRetry(f"Page not found (404): {url}. Check the URL.") from err
        if status == 403:
            msg = f"Access forbidden (403): {url}. The page may require authentication."
            raise ModelRetry(msg) from err
        if status == 429:
            raise ModelRetry(f"Rate limited (429): {url}. Try again later.") from err
        if status >= 500:
            msg = f"Server error ({status}): {url}. The server may be down."
            raise ModelRetry(msg) from err
        raise ModelRetry(f"HTTP error {status} fetching {url}") from err
    except httpx.RequestError as err:
        raise ModelRetry(f"Failed to connect to {url}: {err}") from err
