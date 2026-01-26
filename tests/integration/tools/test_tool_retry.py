"""Tests for tool execution retry logic.

Tests automatic retry behavior in execute_tools_parallel with exponential backoff.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.exceptions import ModelRetry

from tunacode.constants import TOOL_MAX_RETRIES
from tunacode.exceptions import (
    ConfigurationError,
    FileOperationError,
    ToolExecutionError,
    UserAbortError,
    ValidationError,
)

from tunacode.core.agents.agent_components.tool_executor import (
    NON_RETRYABLE_ERRORS,
    _calculate_backoff,
    execute_tools_parallel,
)

MAX_PARALLEL_ENV = "TUNACODE_MAX_PARALLEL"
SINGLE_PARALLEL_LIMIT = 1
TOOL_NAME = "test_tool"
NON_RETRYABLE_MESSAGE = "abort"
CALLBACK_RESULT = "unused"


class TestCalculateBackoff:
    """Tests for backoff calculation."""

    def test_first_attempt_base_delay(self):
        """First attempt uses base delay (~0.5s)."""
        delay = _calculate_backoff(1)
        assert 0.5 <= delay <= 0.55  # Base + up to 10% jitter

    def test_second_attempt_doubles_delay(self):
        """Second attempt doubles the delay (~1.0s)."""
        delay = _calculate_backoff(2)
        assert 1.0 <= delay <= 1.1  # 2x base + up to 10% jitter

    def test_third_attempt_quadruples_delay(self):
        """Third attempt quadruples the delay (~2.0s)."""
        delay = _calculate_backoff(3)
        assert 2.0 <= delay <= 2.2  # 4x base + up to 10% jitter

    def test_respects_max_delay(self):
        """High attempt numbers cap at max delay."""
        delay = _calculate_backoff(100)
        assert delay <= 5.5  # Max 5.0 + 10% jitter


class TestNonRetryableErrors:
    """Tests for non-retryable error classification."""

    def test_user_abort_not_retried(self):
        """UserAbortError should not be retried."""
        assert UserAbortError in NON_RETRYABLE_ERRORS

    def test_model_retry_not_retried(self):
        """ModelRetry should not be retried (pydantic-ai handles)."""
        assert ModelRetry in NON_RETRYABLE_ERRORS

    def test_validation_error_not_retried(self):
        """ValidationError should not be retried."""
        assert ValidationError in NON_RETRYABLE_ERRORS

    def test_configuration_error_not_retried(self):
        """ConfigurationError should not be retried."""
        assert ConfigurationError in NON_RETRYABLE_ERRORS

    def test_keyboard_interrupt_not_retried(self):
        """KeyboardInterrupt should not be retried."""
        assert KeyboardInterrupt in NON_RETRYABLE_ERRORS

    def test_tool_execution_error_not_retried(self):
        """ToolExecutionError should not be retried (already handled)."""
        assert ToolExecutionError in NON_RETRYABLE_ERRORS

    def test_file_operation_error_not_retried(self):
        """FileOperationError should not be retried (unrecoverable)."""
        assert FileOperationError in NON_RETRYABLE_ERRORS


class TestExecuteToolsParallel:
    """Tests for execute_tools_parallel retry behavior."""

    @pytest.fixture
    def mock_part(self):
        """Create a mock tool call part."""
        part = MagicMock()
        part.tool_name = TOOL_NAME
        return part

    @pytest.fixture
    def mock_node(self):
        """Create a mock node."""
        return MagicMock()

    async def test_success_on_first_attempt(self, mock_part, mock_node):
        """Successful call on first attempt returns None (callback for side effects)."""
        callback = AsyncMock(return_value=None)
        tool_calls = [(mock_part, mock_node)]

        results = await execute_tools_parallel(tool_calls, callback)

        assert results == [None]
        assert callback.call_count == 1

    async def test_success_on_second_attempt(self, mock_part, mock_node):
        """Retry on failure, succeed on second attempt."""
        callback = AsyncMock(side_effect=[RuntimeError("transient"), None])
        tool_calls = [(mock_part, mock_node)]

        results = await execute_tools_parallel(tool_calls, callback)

        assert results == [None]
        assert callback.call_count == 2

    async def test_success_on_third_attempt(self, mock_part, mock_node):
        """Retry twice on failure, succeed on third attempt."""
        callback = AsyncMock(
            side_effect=[
                RuntimeError("transient1"),
                RuntimeError("transient2"),
                None,
            ]
        )
        tool_calls = [(mock_part, mock_node)]

        results = await execute_tools_parallel(tool_calls, callback)

        assert results == [None]
        assert callback.call_count == 3

    async def test_fails_after_max_retries(self, mock_part, mock_node):
        """Error raised after all retry attempts exhausted."""
        error = RuntimeError("persistent failure")
        callback = AsyncMock(side_effect=error)
        tool_calls = [(mock_part, mock_node)]

        with pytest.raises(RuntimeError, match="persistent failure"):
            await execute_tools_parallel(tool_calls, callback)

        assert callback.call_count == TOOL_MAX_RETRIES

    async def test_user_abort_not_retried(self, mock_part, mock_node):
        """UserAbortError propagates immediately without retry."""
        callback = AsyncMock(side_effect=UserAbortError("user cancelled"))
        tool_calls = [(mock_part, mock_node)]

        with pytest.raises(UserAbortError):
            await execute_tools_parallel(tool_calls, callback)

        assert callback.call_count == 1

    async def test_model_retry_not_retried(self, mock_part, mock_node):
        """ModelRetry propagates immediately without retry."""
        callback = AsyncMock(side_effect=ModelRetry("model wants retry"))
        tool_calls = [(mock_part, mock_node)]

        with pytest.raises(ModelRetry):
            await execute_tools_parallel(tool_calls, callback)

        assert callback.call_count == 1

    async def test_validation_error_not_retried(self, mock_part, mock_node):
        """ValidationError propagates immediately without retry."""
        callback = AsyncMock(side_effect=ValidationError("bad input"))
        tool_calls = [(mock_part, mock_node)]

        with pytest.raises(ValidationError):
            await execute_tools_parallel(tool_calls, callback)

        assert callback.call_count == 1

    async def test_configuration_error_not_retried(self, mock_part, mock_node):
        """ConfigurationError propagates immediately without retry."""
        callback = AsyncMock(side_effect=ConfigurationError("bad config"))
        tool_calls = [(mock_part, mock_node)]

        with pytest.raises(ConfigurationError):
            await execute_tools_parallel(tool_calls, callback)

        assert callback.call_count == 1

    async def test_tool_execution_error_not_retried(self, mock_part, mock_node):
        """ToolExecutionError propagates immediately without retry."""
        callback = AsyncMock(side_effect=ToolExecutionError("test", "tool failed"))
        tool_calls = [(mock_part, mock_node)]

        with pytest.raises(ToolExecutionError):
            await execute_tools_parallel(tool_calls, callback)

        assert callback.call_count == 1

    async def test_file_operation_error_not_retried(self, mock_part, mock_node):
        """FileOperationError propagates immediately without retry."""
        callback = AsyncMock(side_effect=FileOperationError("read", "/path", "permission denied"))
        tool_calls = [(mock_part, mock_node)]

        with pytest.raises(FileOperationError):
            await execute_tools_parallel(tool_calls, callback)

        assert callback.call_count == 1

    async def test_multiple_tools_all_succeed(self, mock_node):
        """Multiple tools all succeed on first attempt."""
        parts = [MagicMock(tool_name=f"tool_{i}") for i in range(3)]
        callback = AsyncMock(side_effect=[None, None, None])
        tool_calls = [(p, mock_node) for p in parts]

        results = await execute_tools_parallel(tool_calls, callback)

        assert results == [None, None, None]

    async def test_multiple_tools_one_fails(self, mock_node):
        """One failing tool causes entire batch to fail after retries."""
        parts = [MagicMock(tool_name=f"tool_{i}") for i in range(2)]
        # First tool succeeds, second always fails with retryable error
        error = RuntimeError("always fails")
        callback = AsyncMock(side_effect=[None, error, error, error])
        tool_calls = [(p, mock_node) for p in parts]

        with pytest.raises(RuntimeError, match="always fails"):
            await execute_tools_parallel(tool_calls, callback)

    async def test_batch_error_raises_first_exception(self, mock_node, monkeypatch):
        """Batch execution raises when a batch result is an exception."""
        monkeypatch.setenv(MAX_PARALLEL_ENV, str(SINGLE_PARALLEL_LIMIT))
        parts = [MagicMock(tool_name=f"{TOOL_NAME}_{i}") for i in range(2)]
        tool_calls = [(part, mock_node) for part in parts]
        callback = AsyncMock(side_effect=ValidationError(NON_RETRYABLE_MESSAGE))

        with pytest.raises(ValidationError, match=NON_RETRYABLE_MESSAGE):
            await execute_tools_parallel(tool_calls, callback)

    async def test_generic_exception_is_retried(self, mock_part, mock_node):
        """Generic exceptions (not in non-retryable) are retried."""
        callback = AsyncMock(side_effect=[RuntimeError("transient"), None])
        tool_calls = [(mock_part, mock_node)]

        results = await execute_tools_parallel(tool_calls, callback)

        assert results == [None]
        assert callback.call_count == 2

    async def test_timeout_error_is_retried(self, mock_part, mock_node):
        """TimeoutError is retried."""
        callback = AsyncMock(side_effect=[TimeoutError("network timeout"), None])
        tool_calls = [(mock_part, mock_node)]

        results = await execute_tools_parallel(tool_calls, callback)

        assert results == [None]
        assert callback.call_count == 2

    async def test_os_error_is_retried(self, mock_part, mock_node):
        """OSError is retried."""
        callback = AsyncMock(side_effect=[OSError("disk busy"), None])
        tool_calls = [(mock_part, mock_node)]

        results = await execute_tools_parallel(tool_calls, callback)

        assert results == [None]
        assert callback.call_count == 2
