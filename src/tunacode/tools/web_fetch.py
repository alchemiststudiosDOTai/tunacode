"""Web fetch tool — HTTP GET with HTML-to-text conversion.

Fetches a URL, validates it against SSRF targets, converts HTML to
readable markdown-ish text, and truncates oversized responses.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import html2text
import httpx

from tunacode.exceptions import ToolRetryError

from tunacode.tools.decorators import base_tool

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONTENT_BYTES = 5 * 1024 * 1024  # 5 MB download cap
MAX_OUTPUT_BYTES = 100 * 1024  # 100 KB returned to caller
TIMEOUT_FLOOR = 5
TIMEOUT_CEILING = 120
DEFAULT_TIMEOUT = 60  # seconds
MAX_REDIRECTS = 5
USER_AGENT = "TunaCode/1.0 (https://tunacode.xyz)"
TRUNCATION_MARKER = "\n\n... [Content truncated due to size] ..."

ALLOWED_SCHEMES = frozenset({"http", "https"})

BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "local",
    "0.0.0.0",  # nosec B104 — blocklist entry, not a bind address
    "127.0.0.1",
    "::1",
})

HTTP_ERROR_MESSAGES: dict[int, str] = {
    403: "Access forbidden (403): {url}. The page may require authentication.",
    404: "Page not found (404): {url}. Check the URL.",
    429: "Rate limited (429): {url}. Try again later.",
}


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

def _is_blocked_ip(hostname: str) -> bool:
    """Return True if *hostname* resolves to a private/reserved address."""
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local


def _validate_url(url: str) -> str:
    """Validate *url* for security and return the cleaned string.

    Raises ``ToolRetryError`` on empty input, bad scheme, missing host,
    localhost, or private-IP targets.
    """
    url = url.strip()
    if not url:
        raise ToolRetryError("URL cannot be empty.")

    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ToolRetryError(
            f"Invalid URL scheme '{parsed.scheme}'. Only http:// and https:// are allowed."
        )

    hostname = parsed.hostname
    if not hostname:
        raise ToolRetryError(f"URL missing hostname: {url}")

    hostname_lower = hostname.lower()

    if hostname_lower in BLOCKED_HOSTNAMES:
        raise ToolRetryError(
            f"Blocked URL: {url}. Cannot fetch from localhost or local addresses."
        )

    if _is_blocked_ip(hostname_lower):
        raise ToolRetryError(
            f"Blocked URL: {url}. Cannot fetch from private or reserved IP addresses."
        )

    return url


# ---------------------------------------------------------------------------
# Response processing
# ---------------------------------------------------------------------------

def _html_to_text(html: str) -> str:
    """Convert raw HTML into readable plain text."""
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_emphasis = False
    converter.body_width = 80
    converter.unicode_snob = True
    converter.skip_internal_links = True
    return converter.handle(html)


def _decode(content: bytes) -> str:
    """Decode response bytes with a latin-1 fallback."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1", errors="replace")


def _truncate(text: str, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
    """Trim *text* to roughly *max_bytes* UTF-8, appending a marker if cut."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text

    # Decode back to avoid splitting inside a multi-byte character.
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated + TRUNCATION_MARKER


def _raise_content_too_large(size: int) -> None:
    size_mb = size // (1024 * 1024)
    limit_mb = MAX_CONTENT_BYTES // (1024 * 1024)
    raise ToolRetryError(f"Content too large ({size_mb}MB). Maximum allowed is {limit_mb}MB.")


def _process_response(response: httpx.Response, original_url: str) -> str:
    """Validate, decode, optionally convert HTML, and truncate the response."""
    final_url = str(response.url)
    if final_url != original_url:
        _validate_url(final_url)

    raw = response.content
    if len(raw) > MAX_CONTENT_BYTES:
        _raise_content_too_large(len(raw))

    text = _decode(raw)

    content_type = response.headers.get("content-type", "").lower()
    is_html = "text/html" in content_type or "<html" in text[:1000].lower()
    if is_html:
        text = _html_to_text(text)

    return _truncate(text)


# ---------------------------------------------------------------------------
# HTTP error mapping
# ---------------------------------------------------------------------------

def _handle_status_error(url: str, exc: httpx.HTTPStatusError) -> None:
    """Re-raise *exc* as a ``ToolRetryError`` with a user-friendly message."""
    status = exc.response.status_code
    template = HTTP_ERROR_MESSAGES.get(status)

    if template:
        raise ToolRetryError(template.format(url=url)) from exc
    if status >= 500:
        raise ToolRetryError(f"Server error ({status}): {url}. The server may be down.") from exc
    raise ToolRetryError(f"HTTP error {status} fetching {url}") from exc


# ---------------------------------------------------------------------------
# Public tool
# ---------------------------------------------------------------------------

@base_tool
async def web_fetch(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Fetch web content from a URL and return as readable text.

    Args:
        url: The URL to fetch (http:// or https://).
        timeout: Request timeout in seconds (default: 60).

    Returns:
        Readable text content from the URL.
    """
    validated_url = _validate_url(url)
    clamped_timeout = max(TIMEOUT_FLOOR, min(timeout, TIMEOUT_CEILING))

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(clamped_timeout),
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            # Pre-flight size check — best-effort, failures are ignored.
            try:
                head = await client.head(validated_url)
                length = head.headers.get("content-length")
                if length and int(length) > MAX_CONTENT_BYTES:
                    _raise_content_too_large(int(length))
            except httpx.HTTPError:
                pass

            response = await client.get(validated_url)
            response.raise_for_status()
            return _process_response(response, validated_url)

    except httpx.TimeoutException as exc:
        raise ToolRetryError(
            f"Request timed out after {clamped_timeout}s. Try again or use a shorter timeout."
        ) from exc
    except httpx.TooManyRedirects as exc:
        raise ToolRetryError(
            f"Too many redirects while fetching {url}. The URL may be invalid."
        ) from exc
    except httpx.HTTPStatusError as exc:
        _handle_status_error(url, exc)
    except httpx.RequestError as exc:
        raise ToolRetryError(f"Failed to connect to {url}: {exc}") from exc
