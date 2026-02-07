"""Tests for pure helper functions in tunacode.tools.web_fetch."""

import httpx
import pytest

from tunacode.exceptions import ToolRetryError

from tunacode.tools.web_fetch import (
    _convert_html_to_text,
    _decode_response,
    _handle_http_error,
    _is_private_ip,
    _maybe_convert_html,
    _truncate_output,
    _validate_url,
)

# ---------------------------------------------------------------------------
# _is_private_ip
# ---------------------------------------------------------------------------


class TestIsPrivateIp:
    """Tests for _is_private_ip(ip_str)."""

    def test_loopback_127(self):
        assert _is_private_ip("127.0.0.1") is True

    def test_loopback_127_variant(self):
        assert _is_private_ip("127.255.255.255") is True

    def test_private_10_range(self):
        assert _is_private_ip("10.0.0.1") is True
        assert _is_private_ip("10.255.255.255") is True

    def test_private_172_16_range(self):
        assert _is_private_ip("172.16.0.1") is True
        assert _is_private_ip("172.31.255.255") is True

    def test_private_192_168_range(self):
        assert _is_private_ip("192.168.0.1") is True
        assert _is_private_ip("192.168.255.255") is True

    def test_link_local_169_254(self):
        assert _is_private_ip("169.254.1.1") is True

    def test_zero_prefix(self):
        assert _is_private_ip("0.0.0.0") is True  # nosec B104

    def test_ipv6_localhost(self):
        assert _is_private_ip("::1") is True

    def test_ipv6_link_local(self):
        assert _is_private_ip("fe80::1") is True

    def test_ipv6_unique_local_fc(self):
        assert _is_private_ip("fc00::1") is True

    def test_ipv6_unique_local_fd(self):
        assert _is_private_ip("fd00::1") is True

    def test_public_ip(self):
        assert _is_private_ip("8.8.8.8") is False

    def test_public_ip_cloudflare(self):
        assert _is_private_ip("1.1.1.1") is False

    def test_public_ip_example(self):
        assert _is_private_ip("93.184.216.34") is False

    def test_invalid_string_returns_false(self):
        assert _is_private_ip("not-an-ip") is False

    def test_empty_string_returns_false(self):
        assert _is_private_ip("") is False


# ---------------------------------------------------------------------------
# _validate_url
# ---------------------------------------------------------------------------


class TestValidateUrl:
    """Tests for _validate_url(url)."""

    def test_valid_https_url(self):
        result = _validate_url("https://example.com")
        assert result == "https://example.com"

    def test_valid_http_url(self):
        result = _validate_url("http://example.com/page")
        assert result == "http://example.com/page"

    def test_strips_whitespace(self):
        result = _validate_url("  https://example.com  ")
        assert result == "https://example.com"

    def test_empty_url_raises(self):
        with pytest.raises(ToolRetryError, match="URL cannot be empty"):
            _validate_url("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ToolRetryError, match="URL cannot be empty"):
            _validate_url("   ")

    def test_none_raises(self):
        with pytest.raises(ToolRetryError, match="URL cannot be empty"):
            _validate_url(None)  # type: ignore[arg-type]

    def test_ftp_scheme_blocked(self):
        with pytest.raises(ToolRetryError, match="Invalid URL scheme"):
            _validate_url("ftp://example.com/file")

    def test_file_scheme_blocked(self):
        with pytest.raises(ToolRetryError, match="Invalid URL scheme"):
            _validate_url("file:///etc/passwd")

    def test_missing_scheme_blocked(self):
        with pytest.raises(ToolRetryError, match="Invalid URL scheme"):
            _validate_url("example.com")

    def test_localhost_blocked(self):
        with pytest.raises(ToolRetryError, match="Blocked URL"):
            _validate_url("http://localhost/admin")

    def test_127_0_0_1_blocked(self):
        with pytest.raises(ToolRetryError, match="Blocked URL"):
            _validate_url("http://127.0.0.1/secret")

    def test_zero_ip_blocked(self):
        with pytest.raises(ToolRetryError, match="Blocked URL"):
            _validate_url("http://0.0.0.0/")  # nosec B104

    def test_ipv6_localhost_blocked(self):
        with pytest.raises(ToolRetryError, match="Blocked URL"):
            _validate_url("http://[::1]/")

    def test_private_ip_10_range_blocked(self):
        with pytest.raises(ToolRetryError, match="Blocked URL"):
            _validate_url("http://10.0.0.1/internal")

    def test_private_ip_192_168_blocked(self):
        with pytest.raises(ToolRetryError, match="Blocked URL"):
            _validate_url("http://192.168.1.1/router")

    def test_missing_hostname_raises(self):
        with pytest.raises(ToolRetryError, match="URL missing hostname"):
            _validate_url("http:///path")

    def test_localhost_localdomain_blocked(self):
        with pytest.raises(ToolRetryError, match="Blocked URL"):
            _validate_url("http://localhost.localdomain/")

    def test_local_blocked(self):
        with pytest.raises(ToolRetryError, match="Blocked URL"):
            _validate_url("http://local/")


# ---------------------------------------------------------------------------
# _convert_html_to_text
# ---------------------------------------------------------------------------


class TestConvertHtmlToText:
    """Tests for _convert_html_to_text(html_content)."""

    def test_simple_paragraph(self):
        result = _convert_html_to_text("<p>Hello, world!</p>")
        assert "Hello, world!" in result

    def test_strips_html_tags(self):
        html = "<div><b>Bold</b> and <i>italic</i></div>"
        result = _convert_html_to_text(html)
        assert "Bold" in result
        assert "italic" in result
        assert "<div>" not in result
        assert "<b>" not in result

    def test_heading_preserved_as_text(self):
        html = "<h1>Title</h1><p>Content here.</p>"
        result = _convert_html_to_text(html)
        assert "Title" in result
        assert "Content here." in result

    def test_plain_text_passthrough(self):
        text = "Just some plain text with no HTML."
        result = _convert_html_to_text(text)
        assert "Just some plain text with no HTML." in result

    def test_links_preserved(self):
        html = '<a href="https://example.com">Click here</a>'
        result = _convert_html_to_text(html)
        assert "Click here" in result
        # ignore_links is False, so the URL should appear
        assert any("https://example.com" in tok for tok in result.split())

    def test_empty_html(self):
        result = _convert_html_to_text("")
        assert result.strip() == ""


# ---------------------------------------------------------------------------
# _truncate_output
# ---------------------------------------------------------------------------


class TestTruncateOutput:
    """Tests for _truncate_output(content, max_size)."""

    def test_short_content_unchanged(self):
        content = "Hello"
        result = _truncate_output(content, max_size=1000)
        assert result == "Hello"

    def test_long_content_truncated(self):
        content = "A" * 10_000
        result = _truncate_output(content, max_size=200)
        assert len(result) < len(content)
        assert "[Content truncated due to size]" in result

    def test_exact_boundary_not_truncated(self):
        # ASCII characters: 1 byte each, so len == byte length
        content = "x" * 100
        result = _truncate_output(content, max_size=100)
        assert result == content

    def test_one_over_boundary_truncated(self):
        content = "x" * 101
        result = _truncate_output(content, max_size=100)
        assert "[Content truncated due to size]" in result

    def test_default_max_size_is_module_constant(self):
        # Short content should pass through with default max_size
        content = "short"
        result = _truncate_output(content)
        assert result == "short"

    def test_multibyte_content_respected(self):
        # Each emoji is 4 bytes in UTF-8
        content = "\U0001f600" * 30  # 30 emojis = 120 bytes
        result = _truncate_output(content, max_size=50)
        assert "[Content truncated due to size]" in result


# ---------------------------------------------------------------------------
# _decode_response
# ---------------------------------------------------------------------------


class TestDecodeResponse:
    """Tests for _decode_response(content: bytes)."""

    def test_valid_utf8(self):
        data = b"Hello, world!"
        assert _decode_response(data) == "Hello, world!"

    def test_utf8_with_unicode(self):
        data = "Caf\u00e9 \u2603 \U0001f600".encode()
        assert _decode_response(data) == "Caf\u00e9 \u2603 \U0001f600"

    def test_invalid_utf8_falls_back_to_latin1(self):
        # 0xe9 is not valid standalone UTF-8 but is 'e-acute' in latin-1
        data = b"Caf\xe9"
        result = _decode_response(data)
        assert result == "Caf\u00e9"

    def test_empty_bytes(self):
        assert _decode_response(b"") == ""

    def test_pure_ascii(self):
        data = b"plain ascii"
        assert _decode_response(data) == "plain ascii"


# ---------------------------------------------------------------------------
# _maybe_convert_html
# ---------------------------------------------------------------------------


class TestMaybeConvertHtml:
    """Tests for _maybe_convert_html(text_content, content_type)."""

    def test_text_html_triggers_conversion(self):
        html = "<p>Hello</p>"
        result = _maybe_convert_html(html, "text/html; charset=utf-8")
        # Conversion strips tags
        assert "<p>" not in result
        assert "Hello" in result

    def test_text_plain_passthrough(self):
        text = "<p>Not really HTML</p>"
        result = _maybe_convert_html(text, "text/plain")
        # No html tag in first 1000 chars except the <p> — but <p> is not <html>
        assert result == text

    def test_application_json_passthrough(self):
        json_text = '{"key": "value"}'
        result = _maybe_convert_html(json_text, "application/json")
        assert result == json_text

    def test_html_tag_in_body_triggers_conversion(self):
        # Even with non-html content-type, if <html> appears, conversion happens
        html = "<html><body><p>Content</p></body></html>"
        result = _maybe_convert_html(html, "text/plain")
        assert "<html>" not in result
        assert "Content" in result

    def test_empty_content_type(self):
        text = "Just plain text."
        result = _maybe_convert_html(text, "")
        assert result == text


# ---------------------------------------------------------------------------
# _handle_http_error
# ---------------------------------------------------------------------------


class TestHandleHttpError:
    """Tests for _handle_http_error(url, err)."""

    @staticmethod
    def _make_status_error(
        status_code: int,
        url: str = "https://example.com",
    ) -> httpx.HTTPStatusError:
        """Build a synthetic httpx.HTTPStatusError for the given status code."""
        request = httpx.Request("GET", url)
        response = httpx.Response(status_code, request=request)
        return httpx.HTTPStatusError(
            message=f"{status_code}",
            request=request,
            response=response,
        )

    def test_404_raises_tool_retry(self):
        err = self._make_status_error(404)
        with pytest.raises(ToolRetryError, match="Page not found"):
            _handle_http_error("https://example.com", err)

    def test_403_raises_tool_retry(self):
        err = self._make_status_error(403)
        with pytest.raises(ToolRetryError, match="Access forbidden"):
            _handle_http_error("https://example.com", err)

    def test_429_raises_tool_retry(self):
        err = self._make_status_error(429)
        with pytest.raises(ToolRetryError, match="Rate limited"):
            _handle_http_error("https://example.com", err)

    def test_500_server_error(self):
        err = self._make_status_error(500)
        with pytest.raises(ToolRetryError, match="Server error"):
            _handle_http_error("https://example.com", err)

    def test_502_server_error(self):
        err = self._make_status_error(502)
        with pytest.raises(ToolRetryError, match="Server error"):
            _handle_http_error("https://example.com", err)

    def test_503_server_error(self):
        err = self._make_status_error(503)
        with pytest.raises(ToolRetryError, match="Server error"):
            _handle_http_error("https://example.com", err)

    def test_generic_4xx(self):
        err = self._make_status_error(418)
        with pytest.raises(ToolRetryError, match="HTTP error 418"):
            _handle_http_error("https://example.com", err)

    def test_url_appears_in_message(self):
        url = "https://specific-site.example.org/page"
        err = self._make_status_error(404, url=url)
        with pytest.raises(ToolRetryError, match=r"specific-site\.example\.org"):
            _handle_http_error(url, err)

    def test_original_error_chained(self):
        err = self._make_status_error(404)
        with pytest.raises(ToolRetryError) as exc_info:
            _handle_http_error("https://example.com", err)
        assert exc_info.value.__cause__ is err
