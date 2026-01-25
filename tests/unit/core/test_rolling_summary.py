"""Tests for rolling summary integration.

Tests the rolling summary system that compresses long conversation histories
while preserving essential context. The system includes:

1. Token threshold detection (should_compact)
2. Summary checkpoint detection (is_summary_message)
3. History filtering at checkpoints (filter_compacted)
4. Summary message creation (SummaryMessage, create_summary_request_message)
5. Summary generation (generate_summary)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tunacode.core.agents.resume.filter import filter_compacted
from tunacode.core.agents.resume.summary import (
    LOCAL_SUMMARY_THRESHOLD,
    SUMMARY_MARKER,
    SUMMARY_THRESHOLD,
    SummaryMessage,
    create_summary_request_message,
    generate_summary,
    is_summary_message,
    should_compact,
)

# --- Fixtures ---


@pytest.fixture
def mock_model_request():
    """Create a mock ModelRequest with parts.

    Returns a factory function that creates mock ModelRequest objects
    to simulate the container structure that holds message parts.
    """

    def _create(parts: list, kind: str = "request"):
        msg = MagicMock()
        msg.parts = parts
        msg.kind = kind
        return msg

    return _create


@pytest.fixture
def mock_system_part():
    """Create a mock SystemPromptPart.

    Returns a factory function that creates mock SystemPromptPart objects.
    """

    def _create(content: str):
        part = MagicMock()
        part.part_kind = "system-prompt"
        part.content = content
        return part

    return _create


@pytest.fixture
def mock_user_part():
    """Create a mock UserPromptPart."""

    def _create(content: str = "user message"):
        part = MagicMock()
        part.part_kind = "user-prompt"
        part.content = content
        return part

    return _create


@pytest.fixture
def sample_summary() -> SummaryMessage:
    """Create a sample SummaryMessage for testing."""
    return SummaryMessage(
        content="Summary of the conversation: we discussed X, Y, and Z.",
        timestamp=datetime.now(UTC),
        source_range=(0, 5),
        token_count=50,
    )


# --- TestShouldCompact ---


class TestShouldCompact:
    """Test threshold detection for summary generation."""

    def test_empty_messages_returns_false(self):
        assert should_compact([], "anthropic:claude-sonnet") is False

    def test_below_threshold_returns_false(self, mock_model_request, mock_user_part):
        messages = [mock_model_request([mock_user_part("hello")])]
        assert should_compact(messages, "anthropic:claude-sonnet") is False

    def test_above_threshold_returns_true(self, mock_model_request, mock_user_part):
        messages = [mock_model_request([mock_user_part("hello")])]

        with patch(
            "tunacode.core.agents.resume.summary.estimate_tokens",
            return_value=SUMMARY_THRESHOLD + 1000,
        ):
            assert should_compact(messages, "anthropic:claude-sonnet") is True

    def test_local_mode_uses_lower_threshold(self, mock_model_request, mock_user_part):
        messages = [mock_model_request([mock_user_part("hello")])]

        # Should trigger with local_mode threshold but not standard
        with patch(
            "tunacode.core.agents.resume.summary.estimate_tokens",
            return_value=LOCAL_SUMMARY_THRESHOLD + 100,
        ):
            assert should_compact(messages, "test:model", local_mode=True) is True
            assert should_compact(messages, "test:model", local_mode=False) is False

    def test_threshold_override_takes_precedence(self, mock_model_request, mock_user_part):
        messages = [mock_model_request([mock_user_part("hello")])]
        custom_threshold = 1000

        with patch(
            "tunacode.core.agents.resume.summary.estimate_tokens",
            return_value=custom_threshold + 100,
        ):
            # Override should work regardless of local_mode
            assert (
                should_compact(
                    messages, "test:model", local_mode=False, threshold_override=custom_threshold
                )
                is True
            )
            assert (
                should_compact(
                    messages, "test:model", local_mode=True, threshold_override=custom_threshold
                )
                is True
            )

    def test_handles_dict_messages(self):
        messages = [
            {"role": "user", "content": "hello world"},
            {"role": "assistant", "content": "hi there"},
        ]

        with patch(
            "tunacode.core.agents.resume.summary.estimate_tokens",
            return_value=SUMMARY_THRESHOLD + 1000,
        ):
            assert should_compact(messages, "anthropic:claude-sonnet") is True


# --- TestIsSummaryMessage ---


class TestIsSummaryMessage:
    """Test summary checkpoint marker detection."""

    def test_detects_marker_in_dict_content(self):
        message = {"content": f"{SUMMARY_MARKER}\nSome summary text"}
        assert is_summary_message(message) is True

    def test_detects_marker_in_dict_parts(self):
        message = {
            "parts": [
                {"content": "regular content"},
                {"content": f"{SUMMARY_MARKER}\nSummary"},
            ]
        }
        assert is_summary_message(message) is True

    def test_detects_marker_in_pydantic_message(self, mock_model_request, mock_system_part):
        part = mock_system_part(f"{SUMMARY_MARKER}\nSummary of conversation")
        message = mock_model_request([part])
        assert is_summary_message(message) is True

    def test_rejects_message_without_marker(self, mock_model_request, mock_user_part):
        message = mock_model_request([mock_user_part("no marker here")])
        assert is_summary_message(message) is False

    def test_rejects_dict_without_marker(self):
        message = {"content": "regular message without marker"}
        assert is_summary_message(message) is False

    def test_handles_empty_content(self):
        message = {"content": ""}
        assert is_summary_message(message) is False

    def test_handles_non_string_content(self):
        message = {"content": 12345}
        assert is_summary_message(message) is False


# --- TestFilterCompacted ---


class TestFilterCompacted:
    """Test history truncation at summary checkpoint."""

    def test_empty_messages_returns_empty(self):
        assert filter_compacted([]) == []

    def test_no_summary_returns_full_history(self, mock_model_request, mock_user_part):
        messages = [
            mock_model_request([mock_user_part("msg1")]),
            mock_model_request([mock_user_part("msg2")]),
            mock_model_request([mock_user_part("msg3")]),
        ]
        result = filter_compacted(messages)
        assert len(result) == 3

    def test_truncates_at_summary_checkpoint(self, mock_model_request, mock_system_part):
        old_msg = MagicMock()
        old_msg.parts = []

        summary_msg = mock_model_request([mock_system_part(f"{SUMMARY_MARKER}\nSummary")])

        new_msg1 = MagicMock()
        new_msg1.parts = []

        new_msg2 = MagicMock()
        new_msg2.parts = []

        messages = [old_msg, summary_msg, new_msg1, new_msg2]
        result = filter_compacted(messages)

        assert len(result) == 3
        assert result[0] is summary_msg

    def test_uses_most_recent_summary(self, mock_model_request, mock_system_part):
        old_summary = mock_model_request([mock_system_part(f"{SUMMARY_MARKER}\nOld summary")])
        middle_msg = MagicMock()
        middle_msg.parts = []

        new_summary = mock_model_request([mock_system_part(f"{SUMMARY_MARKER}\nNew summary")])
        final_msg = MagicMock()
        final_msg.parts = []

        messages = [old_summary, middle_msg, new_summary, final_msg]
        result = filter_compacted(messages)

        assert len(result) == 2
        assert result[0] is new_summary
        assert result[1] is final_msg


# --- TestSummaryMessage ---


class TestSummaryMessage:
    """Test SummaryMessage dataclass and methods."""

    def test_creates_with_required_fields(self, sample_summary):
        assert sample_summary.content is not None
        assert sample_summary.timestamp is not None
        assert sample_summary.source_range == (0, 5)
        assert sample_summary.token_count == 50

    def test_to_marker_text_includes_marker(self, sample_summary):
        marker_text = sample_summary.to_marker_text()
        assert marker_text.startswith(SUMMARY_MARKER)
        assert sample_summary.content in marker_text


# --- TestCreateSummaryRequestMessage ---


class TestCreateSummaryRequestMessage:
    """Test creation of pydantic-ai compatible message from summary."""

    def test_creates_model_request(self, sample_summary):
        # Test with actual pydantic-ai imports (imports happen inside function)
        result = create_summary_request_message(sample_summary)

        # Verify it's a ModelRequest
        from pydantic_ai.messages import ModelRequest

        assert isinstance(result, ModelRequest)

    def test_message_contains_summary_content(self, sample_summary):
        # Test with actual pydantic-ai imports
        result = create_summary_request_message(sample_summary)

        # Verify it's a ModelRequest-like object
        assert hasattr(result, "parts")
        assert len(result.parts) == 1
        assert SUMMARY_MARKER in result.parts[0].content


# --- TestGenerateSummary ---


class TestGenerateSummary:
    """Test summary generation using agent."""

    @pytest.mark.asyncio
    async def test_generates_summary_from_messages(self, mock_model_request, mock_user_part):
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "Generated summary of the conversation."
        mock_agent.run = AsyncMock(return_value=mock_result)

        messages = [
            mock_model_request([mock_user_part("first message")]),
            mock_model_request([mock_user_part("second message")]),
        ]

        summary = await generate_summary(mock_agent, messages, "test:model")

        assert isinstance(summary, SummaryMessage)
        assert summary.content == "Generated summary of the conversation."
        assert summary.source_range[0] == 0

    @pytest.mark.asyncio
    async def test_respects_start_and_end_index(self, mock_model_request, mock_user_part):
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "Partial summary"
        mock_agent.run = AsyncMock(return_value=mock_result)

        messages = [
            mock_model_request([mock_user_part(f"msg{i}")]) for i in range(10)
        ]

        summary = await generate_summary(
            mock_agent, messages, "test:model", start_index=2, end_index=7
        )

        assert summary.source_range == (2, 7)

    @pytest.mark.asyncio
    async def test_fallback_on_generation_failure(self, mock_model_request, mock_user_part):
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("API Error"))

        messages = [
            mock_model_request([mock_user_part("message")]),
        ]

        summary = await generate_summary(mock_agent, messages, "test:model")

        assert "Summary generation failed" in summary.content


# --- TestConstants ---


class TestConstants:
    """Verify constant values."""

    def test_summary_threshold(self):
        assert SUMMARY_THRESHOLD == 40_000

    def test_local_summary_threshold(self):
        assert LOCAL_SUMMARY_THRESHOLD == 6_000

    def test_summary_marker(self):
        assert SUMMARY_MARKER == "[CONVERSATION_SUMMARY]"
