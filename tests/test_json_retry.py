"""Unit tests for JSON retry functionality."""

import asyncio
import json
from unittest.mock import patch

import pytest

from tunacode.utils.retry import (
    retry_json_parse,
    retry_json_parse_async,
    retry_on_json_error,
)


class TestRetryDecorator:
    """Test the retry_on_json_error decorator."""

    def test_successful_parse_no_retry(self):
        """Test that successful JSON parsing doesn't trigger retries."""
        call_count = 0

        @retry_on_json_error(max_retries=3)
        def parse_json():
            nonlocal call_count
            call_count += 1
            return json.loads('{"valid": "json"}')

        result = parse_json()
        assert result == {"valid": "json"}
        assert call_count == 1

    def test_retry_on_json_error(self):
        """Test that JSONDecodeError triggers retries."""
        call_count = 0

        @retry_on_json_error(max_retries=3, base_delay=0.01)
        def parse_json():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                json.loads('{"invalid": json}')  # Missing quotes
            return json.loads('{"valid": "json"}')

        result = parse_json()
        assert result == {"valid": "json"}
        assert call_count == 3

    def test_max_retries_exhausted(self):
        """Test that exception is raised after max retries."""
        call_count = 0

        @retry_on_json_error(max_retries=2, base_delay=0.01)
        def parse_json():
            nonlocal call_count
            call_count += 1
            json.loads('{"invalid": json}')  # Always fails

        with pytest.raises(json.JSONDecodeError):
            parse_json()

        # Should have tried initial + 2 retries = 3 times
        assert call_count == 3

    def test_exponential_backoff(self):
        """Test that delays increase exponentially."""
        delays = []

        @retry_on_json_error(max_retries=3, base_delay=0.1, max_delay=1.0)
        def parse_json():
            json.loads('{"invalid": json}')

        with patch("time.sleep") as mock_sleep:
            mock_sleep.side_effect = lambda d: delays.append(d)

            with pytest.raises(json.JSONDecodeError):
                parse_json()

        # Check delays: 0.1, 0.2, 0.4
        assert len(delays) == 3
        assert delays[0] == pytest.approx(0.1)
        assert delays[1] == pytest.approx(0.2)
        assert delays[2] == pytest.approx(0.4)

    def test_max_delay_cap(self):
        """Test that delays are capped at max_delay."""
        delays = []

        @retry_on_json_error(max_retries=5, base_delay=0.1, max_delay=0.3)
        def parse_json():
            json.loads('{"invalid": json}')

        with patch("time.sleep") as mock_sleep:
            mock_sleep.side_effect = lambda d: delays.append(d)

            with pytest.raises(json.JSONDecodeError):
                parse_json()

        # Check that delays are capped at 0.3
        assert len(delays) == 5
        assert delays[0] == pytest.approx(0.1)
        assert delays[1] == pytest.approx(0.2)
        assert delays[2] == pytest.approx(0.3)  # Capped
        assert delays[3] == pytest.approx(0.3)  # Capped
        assert delays[4] == pytest.approx(0.3)  # Capped


class TestAsyncRetryDecorator:
    """Test the async version of retry_on_json_error decorator."""

    @pytest.mark.asyncio
    async def test_async_successful_parse(self):
        """Test async successful JSON parsing."""
        call_count = 0

        @retry_on_json_error(max_retries=3)
        async def parse_json():
            nonlocal call_count
            call_count += 1
            return json.loads('{"valid": "json"}')

        result = await parse_json()
        assert result == {"valid": "json"}
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_on_error(self):
        """Test async retry on JSONDecodeError."""
        call_count = 0

        @retry_on_json_error(max_retries=3, base_delay=0.01)
        async def parse_json():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                json.loads('{"invalid": json}')
            return json.loads('{"valid": "json"}')

        result = await parse_json()
        assert result == {"valid": "json"}
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_exponential_backoff(self):
        """Test async exponential backoff."""
        delays = []

        @retry_on_json_error(max_retries=3, base_delay=0.1, max_delay=1.0)
        async def parse_json():
            json.loads('{"invalid": json}')

        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.side_effect = lambda d: delays.append(d) or asyncio.sleep(0)

            with pytest.raises(json.JSONDecodeError):
                await parse_json()

        assert len(delays) == 3
        assert delays[0] == pytest.approx(0.1)
        assert delays[1] == pytest.approx(0.2)
        assert delays[2] == pytest.approx(0.4)


class TestRetryHelpers:
    """Test the helper functions for JSON parsing with retry."""

    def test_retry_json_parse_success(self):
        """Test retry_json_parse with valid JSON."""
        result = retry_json_parse('{"key": "value"}')
        assert result == {"key": "value"}

    def test_retry_json_parse_failure(self):
        """Test retry_json_parse with invalid JSON."""
        with pytest.raises(json.JSONDecodeError):
            retry_json_parse('{"invalid": json}', max_retries=2, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_retry_json_parse_async_success(self):
        """Test retry_json_parse_async with valid JSON."""
        result = await retry_json_parse_async('{"key": "value"}')
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_retry_json_parse_async_failure(self):
        """Test retry_json_parse_async with invalid JSON."""
        with pytest.raises(json.JSONDecodeError):
            await retry_json_parse_async('{"invalid": json}', max_retries=2, base_delay=0.01)

    def test_retry_with_different_errors(self):
        """Test that non-JSON errors are not retried."""
        call_count = 0

        @retry_on_json_error(max_retries=3)
        def parse_json():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Not a JSON error")
            return {"success": True}

        with pytest.raises(ValueError):
            parse_json()

        # Should not retry on non-JSON errors
        assert call_count == 1


class TestLogging:
    """Test logging behavior during retries."""

    def test_retry_logging(self, caplog):
        """Test that retries are logged properly."""

        @retry_on_json_error(max_retries=2, base_delay=0.01)
        def parse_json():
            json.loads('{"bad": json}')

        with pytest.raises(json.JSONDecodeError):
            parse_json()

        # Check that warning and error logs were created
        assert any(
            "JSON parsing error (attempt 1/3)" in record.message for record in caplog.records
        )
        assert any(
            "JSON parsing error (attempt 2/3)" in record.message for record in caplog.records
        )
        assert any(
            "JSON parsing failed after 2 retries" in record.message for record in caplog.records
        )
