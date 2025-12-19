"""Web fetch tool for TunaCode - HTTP GET requests with HTML-to-text conversion.

CLAUDE_ANCHOR[web-fetch-module]: HTTP GET with HTML-to-text conversion
"""

import ipaddress
import re
from urllib.parse import urlparse

import html2text
import httpx
from pydantic_ai.exceptions import ModelRetry

from tunacode.configuration.tools_config.web_fetch_config import WebFetchConfig
from tunacode.tools.decorators import base_tool

web_fetch_config = WebFetchConfig()

# this seems like a anti patern
PRIVATE_IP_PATTERNS = [
    re.compile(r"^127\."),
    re.compile(r"^10\."),
    re.compile(r"^172\.(1[6-9]|2[0-9]|3[01])\."),
    re.compile(r"^192\.168\."),
    re.compile(r"^0\."),
    re.compile(r"^169\.254\."),
    re.compile(r"^::1$"),
    re.compile(r"^fe80:"),
    re.compile(r"^fc00:"),
    re.compile(r"^fd00:"),
]
# this  seems like anti pattern

BLOCKED_HOSTNAMES = frozenset(
    [
        "localhost",
        "localhost.localdomain",
        "local",
        "0.0.0.0",
        "127.0.0.1",
        "::1",
    ]
)


# why do we even have this
def _is_private_ip(ip_str: str) -> bool:
    for pattern in PRIVATE_IP_PATTERNS:
        if pattern.match(ip_str):
            return True

    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except ValueError:
        return False


# more anti patterns for sure
def _validate_url(url: str) -> str:
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
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_emphasis = False
    converter.body_width = 80
    converter.unicode_snob = True
    converter.skip_internal_links = True

    return converter.handle(html_content)


def _truncate_output(content: str, max_size: int | None = None) -> str:
    if max_size is None:
        max_size = web_fetch_config.max_output_size_bytes

    if len(content.encode("utf-8")) <= max_size:
        return content

    # Truncate to approximate character count
    truncated = content[: max_size // 2]
    return truncated + "\n\n... [Content truncated due to size] ..."


@base_tool
async def web_fetch(url: str, timeout: int | None = None) -> str:
    # Validate URL security
    validated_url = _validate_url(url)

    # Use configured timeout if not provided
    if timeout is None:
        timeout = web_fetch_config.default_timeout_seconds

    # Clamp timeout to reasonable bounds
    timeout = max(5, min(timeout, 300))

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=web_fetch_config.follow_redirects,
            max_redirects=web_fetch_config.max_redirects,
            headers={"User-Agent": web_fetch_config.user_agent},
            # TODO: Add stealth mode option based on web_fetch_config.enable_stealth_mode
        ) as client:
            try:
                head_response = await client.head(validated_url)
                content_length = head_response.headers.get("content-length")
                max_content_size = web_fetch_config.max_content_size_bytes
                if content_length and int(content_length) > max_content_size:
                    raise ModelRetry(
                        f"Content too large ({int(content_length) // 1024 // 1024}MB). "
                        f"Maximum allowed is {max_content_size // 1024 // 1024}MB."
                    )
            except httpx.HTTPError:
                pass

            # Fetch the actual content
            response = await client.get(validated_url)
            response.raise_for_status()

            final_url = str(response.url)
            if final_url != validated_url:
                _validate_url(final_url)

            content = response.content
            if len(content) > max_content_size:
                raise ModelRetry(
                    f"Content too large ({len(content) // 1024 // 1024}MB). "
                    f"Maximum allowed is {max_content_size // 1024 // 1024}MB."
                )

            try:
                text_content = content.decode("utf-8")
            except UnicodeDecodeError:
                text_content = content.decode("latin-1", errors="replace")

            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type or "<html" in text_content[:1000].lower():
                text_content = _convert_html_to_text(text_content)

            text_content = _truncate_output(text_content)
            return text_content
    # wha is the point of this
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
