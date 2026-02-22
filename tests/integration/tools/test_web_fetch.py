"""Tests for the web_fetch tool."""

import pytest

from tunacode.exceptions import ToolRetryError

from tunacode.tools.web_fetch import (
    _html_to_text,
    _is_blocked_ip,
    _truncate,
    _validate_url,
)


class TestValidateUrl:
    """Tests for URL validation security."""

    def test_blocks_localhost(self) -> None:
        with pytest.raises(ToolRetryError, match="Cannot fetch from localhost"):
            _validate_url("http://localhost/")

    def test_blocks_localhost_with_port(self) -> None:
        with pytest.raises(ToolRetryError, match="Cannot fetch from localhost"):
            _validate_url("http://localhost:8080/")

    def test_blocks_127_0_0_1(self) -> None:
        with pytest.raises(ToolRetryError, match="Cannot fetch from localhost"):
            _validate_url("http://127.0.0.1/")

    def test_blocks_private_ip_10(self) -> None:
        with pytest.raises(ToolRetryError, match="private or reserved"):
            _validate_url("http://10.0.0.1/")

    def test_blocks_private_ip_192_168(self) -> None:
        with pytest.raises(ToolRetryError, match="private or reserved"):
            _validate_url("http://192.168.1.1/")

    def test_blocks_private_ip_172(self) -> None:
        with pytest.raises(ToolRetryError, match="private or reserved"):
            _validate_url("http://172.16.0.1/")

    def test_blocks_file_scheme(self) -> None:
        with pytest.raises(ToolRetryError, match="Invalid URL scheme"):
            _validate_url("file:///etc/passwd")

    def test_blocks_ftp_scheme(self) -> None:
        with pytest.raises(ToolRetryError, match="Invalid URL scheme"):
            _validate_url("ftp://example.com/")

    def test_allows_http(self) -> None:
        result = _validate_url("http://example.com/")
        assert result == "http://example.com/"

    def test_allows_https(self) -> None:
        result = _validate_url("https://example.com/")
        assert result == "https://example.com/"

    def test_blocks_empty_url(self) -> None:
        with pytest.raises(ToolRetryError, match="cannot be empty"):
            _validate_url("")

    def test_blocks_whitespace_url(self) -> None:
        with pytest.raises(ToolRetryError, match="cannot be empty"):
            _validate_url("   ")

    def test_blocks_missing_hostname(self) -> None:
        with pytest.raises(ToolRetryError, match="missing hostname"):
            _validate_url("http:///path")

    def test_strips_whitespace(self) -> None:
        result = _validate_url("  https://example.com/  ")
        assert result == "https://example.com/"


class TestIsBlockedIp:
    """Tests for private/reserved IP detection."""

    def test_loopback_is_blocked(self) -> None:
        assert _is_blocked_ip("127.0.0.1") is True
        assert _is_blocked_ip("127.255.255.255") is True

    def test_10_range_is_blocked(self) -> None:
        assert _is_blocked_ip("10.0.0.1") is True
        assert _is_blocked_ip("10.255.255.255") is True

    def test_172_16_to_31_is_blocked(self) -> None:
        assert _is_blocked_ip("172.16.0.1") is True
        assert _is_blocked_ip("172.31.255.255") is True

    def test_172_outside_range_not_blocked(self) -> None:
        assert _is_blocked_ip("172.15.0.1") is False
        assert _is_blocked_ip("172.32.0.1") is False

    def test_192_168_is_blocked(self) -> None:
        assert _is_blocked_ip("192.168.0.1") is True
        assert _is_blocked_ip("192.168.255.255") is True

    def test_public_ip_not_blocked(self) -> None:
        assert _is_blocked_ip("8.8.8.8") is False
        assert _is_blocked_ip("93.184.216.34") is False

    def test_non_ip_hostname_returns_false(self) -> None:
        assert _is_blocked_ip("example.com") is False

    def test_ipv6_loopback_is_blocked(self) -> None:
        assert _is_blocked_ip("::1") is True

    def test_ipv6_link_local_is_blocked(self) -> None:
        assert _is_blocked_ip("fe80::1") is True


class TestHtmlToText:
    """Tests for HTML to text conversion."""

    def test_converts_simple_html(self) -> None:
        html = "<html><body><h1>Hello</h1><p>World</p></body></html>"
        result = _html_to_text(html)
        assert "Hello" in result
        assert "World" in result

    def test_preserves_links(self) -> None:
        html = '<a href="https://example.com">Link</a>'
        result = _html_to_text(html)
        assert "example.com" in result or "Link" in result


class TestTruncate:
    """Tests for output truncation."""

    def test_no_truncation_for_small_content(self) -> None:
        content = "Small content"
        result = _truncate(content, max_bytes=1000)
        assert result == content

    def test_truncates_large_content(self) -> None:
        content = "x" * 10000
        result = _truncate(content, max_bytes=1000)
        assert len(result) < len(content)
        assert "truncated" in result.lower()

    def test_truncation_marker_present(self) -> None:
        content = "y" * 5000
        result = _truncate(content, max_bytes=500)
        assert result.endswith("... [Content truncated due to size] ...")
