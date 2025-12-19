"""Web fetch tool for TunaCode - HTTP GET requests with HTML-to-text conversion.

CLAUDE_ANCHOR[web-fetch-module]: HTTP GET with HTML-to-text conversion
"""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from urllib.parse import ParseResult, urlparse

import html2text
import httpx
from pydantic_ai.exceptions import ModelRetry

from tunacode.configuration.tools_config import web_fetch_config
from tunacode.tools.decorators import base_tool

tool_config = web_fetch_config.WebFetchConfig()


def _load_settings(
    config: web_fetch_config.WebFetchConfig,
) -> web_fetch_config.WebFetchSettings:
    return web_fetch_config.WebFetchSettings(
        max_content_size_bytes=config.max_content_size_bytes,
        max_output_size_bytes=config.max_output_size_bytes,
        default_timeout_seconds=config.default_timeout_seconds,
        max_redirects=config.max_redirects,
        follow_redirects=config.follow_redirects,
        user_agent=config.user_agent,
        enable_stealth_mode=config.enable_stealth_mode,
        block_private_ips=config.block_private_ips,
    )


def _select_user_agent(settings: web_fetch_config.WebFetchSettings) -> str:
    if settings.enable_stealth_mode:
        return web_fetch_config.STEALTH_USER_AGENT

    return settings.user_agent


def _normalize_timeout(
    timeout_seconds: int | None,
    default_timeout_seconds: int,
    min_timeout_seconds: int,
    max_timeout_seconds: int,
) -> int:
    if timeout_seconds is None:
        timeout_seconds = default_timeout_seconds

    return max(min_timeout_seconds, min(timeout_seconds, max_timeout_seconds))


def _normalize_url(url: str) -> str:
    stripped_url = url.strip()
    if not stripped_url:
        raise ModelRetry("URL cannot be empty.")

    return stripped_url


def _parse_url(url: str) -> ParseResult:
    return urlparse(url)


def _validate_scheme(parsed_url: ParseResult, allowed_schemes: tuple[str, ...]) -> None:
    scheme = parsed_url.scheme
    if scheme not in allowed_schemes:
        raise ModelRetry(f"Invalid URL scheme '{scheme}'. Only http:// and https:// are allowed.")


def _get_hostname(parsed_url: ParseResult, url: str) -> str:
    hostname = parsed_url.hostname
    if not hostname:
        raise ModelRetry(f"URL missing hostname: {url}")

    return hostname.lower()


def _ensure_allowed_hostname(
    hostname: str,
    url: str,
    blocked_hostnames: frozenset[str],
    block_private_ips: bool,
) -> None:
    if hostname in blocked_hostnames:
        raise ModelRetry(f"Blocked URL: {url}. Cannot fetch from localhost or local addresses.")

    if block_private_ips and _is_private_ip(hostname):
        raise ModelRetry(f"Blocked URL: {url}. Cannot fetch from private or reserved IP addresses.")


def _validate_url(
    url: str,
    *,
    allowed_schemes: tuple[str, ...],
    blocked_hostnames: frozenset[str],
    block_private_ips: bool,
) -> str:
    normalized_url = _normalize_url(url)
    parsed_url = _parse_url(normalized_url)
    _validate_scheme(parsed_url, allowed_schemes)
    hostname = _get_hostname(parsed_url, normalized_url)
    _ensure_allowed_hostname(hostname, normalized_url, blocked_hostnames, block_private_ips)
    return normalized_url


def _is_private_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    is_blocked = (
        ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_unspecified
    )
    return is_blocked


def _format_size_limit_error(content_size_bytes: int, max_size_bytes: int) -> str:
    content_size_mb = content_size_bytes // web_fetch_config.BYTES_PER_MB
    max_size_mb = max_size_bytes // web_fetch_config.BYTES_PER_MB
    return f"Content too large ({content_size_mb}MB). Maximum allowed is {max_size_mb}MB."


def _parse_content_length(headers: Mapping[str, str]) -> int | None:
    content_length_header = web_fetch_config.HeaderName.CONTENT_LENGTH.value
    content_length_value = headers.get(content_length_header)
    if content_length_value is None:
        return None

    try:
        content_length = int(content_length_value)
    except ValueError as err:
        raise ModelRetry("Invalid content-length header.") from err

    if content_length < web_fetch_config.MIN_CONTENT_LENGTH_BYTES:
        raise ModelRetry("Invalid content-length header.")

    return content_length


def _enforce_content_length(
    content_length_bytes: int | None,
    max_content_size_bytes: int,
) -> None:
    if content_length_bytes is None:
        return

    if content_length_bytes > max_content_size_bytes:
        raise ModelRetry(_format_size_limit_error(content_length_bytes, max_content_size_bytes))


def _decode_content(content: bytes, encoding: str | None) -> str:
    resolved_encoding = encoding or web_fetch_config.UTF8_ENCODING
    try:
        return content.decode(resolved_encoding)
    except LookupError as err:
        raise ModelRetry(f"Unknown response encoding: {resolved_encoding}") from err
    except UnicodeDecodeError as err:
        msg = (
            f"Failed to decode response using {resolved_encoding}. "
            "The content may be binary or use an unsupported encoding."
        )
        raise ModelRetry(msg) from err


def _should_convert_html(content_type: str, text_content: str) -> bool:
    content_type_value = content_type.lower()
    html_content_type = web_fetch_config.HtmlToken.CONTENT_TYPE.value
    if html_content_type in content_type_value:
        return True

    snippet = text_content[: web_fetch_config.HTML_SNIFF_BYTES].lower()
    html_tag_marker = web_fetch_config.HtmlToken.TAG_MARKER.value
    return html_tag_marker in snippet


def _convert_html_to_text(html_content: str) -> str:
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_emphasis = False
    converter.body_width = web_fetch_config.HTML2TEXT_BODY_WIDTH
    converter.unicode_snob = True
    converter.skip_internal_links = True

    return converter.handle(html_content)


def _truncate_output(content: str, max_size_bytes: int) -> str:
    content_size_bytes = len(content.encode(web_fetch_config.UTF8_ENCODING))
    if content_size_bytes <= max_size_bytes:
        return content

    truncated_length = max_size_bytes // web_fetch_config.TRUNCATION_DIVISOR
    truncated_content = content[:truncated_length]
    return f"{truncated_content}{web_fetch_config.TRUNCATION_NOTICE}"


def _format_http_status_error(status: int, url: str) -> str:
    status_not_found = web_fetch_config.HttpStatus.NOT_FOUND.value
    if status == status_not_found:
        return f"Page not found ({status_not_found}): {url}. Check the URL."

    status_forbidden = web_fetch_config.HttpStatus.FORBIDDEN.value
    if status == status_forbidden:
        return f"Access forbidden ({status_forbidden}): {url}. The page may require authentication."

    status_too_many_requests = web_fetch_config.HttpStatus.TOO_MANY_REQUESTS.value
    if status == status_too_many_requests:
        return f"Rate limited ({status_too_many_requests}): {url}. Try again later."

    server_error_min = web_fetch_config.HttpStatus.SERVER_ERROR_MIN.value
    if status >= server_error_min:
        return f"Server error ({status}): {url}. The server may be down."

    return f"HTTP error {status} fetching {url}"


@base_tool
async def web_fetch(url: str, timeout: int | None = None) -> str:
    settings = _load_settings(tool_config)
    validated_url = _validate_url(
        url,
        allowed_schemes=web_fetch_config.ALLOWED_SCHEMES,
        blocked_hostnames=web_fetch_config.BLOCKED_HOSTNAMES,
        block_private_ips=settings.block_private_ips,
    )

    timeout_seconds = _normalize_timeout(
        timeout,
        default_timeout_seconds=settings.default_timeout_seconds,
        min_timeout_seconds=web_fetch_config.MIN_TIMEOUT_SECONDS,
        max_timeout_seconds=web_fetch_config.MAX_TIMEOUT_SECONDS,
    )

    user_agent = _select_user_agent(settings)
    user_agent_header = web_fetch_config.HeaderName.USER_AGENT.value
    headers = {user_agent_header: user_agent}
    max_content_size_bytes = settings.max_content_size_bytes
    max_output_size_bytes = settings.max_output_size_bytes

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=settings.follow_redirects,
            max_redirects=settings.max_redirects,
            headers=headers,
        ) as client:
            head_response = await client.head(validated_url)
            head_status = head_response.status_code
            if head_status not in web_fetch_config.HEAD_UNSUPPORTED_STATUSES:
                head_response.raise_for_status()
                head_content_length = _parse_content_length(head_response.headers)
                _enforce_content_length(head_content_length, max_content_size_bytes)

            response = await client.get(validated_url)
            response.raise_for_status()

            final_url = str(response.url)
            if final_url != validated_url:
                _validate_url(
                    final_url,
                    allowed_schemes=web_fetch_config.ALLOWED_SCHEMES,
                    blocked_hostnames=web_fetch_config.BLOCKED_HOSTNAMES,
                    block_private_ips=settings.block_private_ips,
                )

            content = response.content
            content_size_bytes = len(content)
            _enforce_content_length(content_size_bytes, max_content_size_bytes)

            text_content = _decode_content(content, response.encoding)
            content_type_header = web_fetch_config.HeaderName.CONTENT_TYPE.value
            content_type = response.headers.get(content_type_header, "")
            if _should_convert_html(content_type, text_content):
                text_content = _convert_html_to_text(text_content)

            return _truncate_output(text_content, max_size_bytes=max_output_size_bytes)
    except httpx.TimeoutException as err:
        msg = (
            f"Request timed out after {timeout_seconds} seconds. "
            "Try again or use a shorter timeout."
        )
        raise ModelRetry(msg) from err
    except httpx.TooManyRedirects as err:
        msg = f"Too many redirects while fetching {url}. The URL may be invalid."
        raise ModelRetry(msg) from err
    except httpx.HTTPStatusError as err:
        status = err.response.status_code
        msg = _format_http_status_error(status, url)
        raise ModelRetry(msg) from err
    except httpx.RequestError as err:
        raise ModelRetry(f"Failed to connect to {url}: {err}") from err
