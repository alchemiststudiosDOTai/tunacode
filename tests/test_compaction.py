"""Tests for tool output pruning (compaction.py).

This module tests the compaction system that manages context window usage in Tunacode
by strategically pruning old tool outputs while preserving recent and relevant content.

The compaction system addresses a critical challenge in AI agent conversations:
as interactions continue, tool outputs (file reads, command executions, etc.) accumulate
and can exceed the model's context window limits. The system uses a backward-scanning
algorithm that:

1. Protects recent tool outputs within a configurable token window (default: 40k tokens)
2. Only prunes when token savings exceed a minimum threshold (default: 20k tokens)
3. Requires minimum user interaction before pruning begins (default: 2 user turns)
4. Replaces pruned content with a placeholder to maintain conversation flow

Key Test Areas:
- Part type detection (tool-return vs user-prompt vs other)
- Token estimation and counting accuracy
- Protection window enforcement
- Minimum threshold validation
- Edge cases and error handling

Testing Strategy:
- Use mock objects to simulate different message parts without full dependencies
- Override token estimation to test boundary conditions reliably
- Verify backward scanning order (newest to oldest)
- Test mixed message formats (dicts, ModelRequest objects, etc.)
"""

from unittest.mock import MagicMock, patch

import pytest

from tunacode.core.compaction import (
    PRUNE_MIN_USER_TURNS,
    PRUNE_MINIMUM_THRESHOLD,
    PRUNE_PLACEHOLDER,
    PRUNE_PROTECT_TOKENS,
    count_user_turns,
    estimate_part_tokens,
    is_tool_return_part,
    is_user_prompt_part,
    prune_old_tool_outputs,
    prune_part_content,
)

# --- Fixtures ---


@pytest.fixture
def mock_tool_return_part():
    """Create a mock ToolReturnPart with specified content.

    Returns a factory function that creates mock ToolReturnPart objects
    with realistic attributes for testing compaction behavior. The mock
    includes all required attributes for part identification and token
    estimation purposes.

    Args:
        content: The tool output content string (default varies by test)
        tool_name: Name of the tool that generated the output (default: "test_tool")

    Returns:
        MagicMock: A mock object configured as a ToolReturnPart with:
            - part_kind: "tool-return" (identifies as tool output)
            - tool_name: Tool identifier for debugging
            - content: The actual tool output content
            - tool_call_id: Unique identifier for the tool call
    """

    def _create(content: str, tool_name: str = "test_tool"):
        part = MagicMock()
        part.part_kind = "tool-return"
        part.tool_name = tool_name
        part.content = content
        part.tool_call_id = "test-id"
        return part

    return _create


@pytest.fixture
def mock_user_prompt_part():
    """Create a mock UserPromptPart.

    Returns a factory function that creates mock UserPromptPart objects
    to simulate user input messages in compaction tests. These parts are
    used to count user turns and ensure the compaction system respects
    user interaction requirements before pruning tool outputs.

    Args:
        content: The user message content (default: "user message")

    Returns:
        MagicMock: A mock object configured as a UserPromptPart with:
            - part_kind: "user-prompt" (identifies as user input)
            - content: The user's message text
    """

    def _create(content: str = "user message"):
        part = MagicMock()
        part.part_kind = "user-prompt"
        part.content = content
        return part

    return _create


@pytest.fixture
def mock_model_request():
    """Create a mock ModelRequest with parts.

    Returns a factory function that creates mock ModelRequest objects
    to simulate the container structure that holds message parts in the
    Tunacode conversation system. This enables testing of how the
    compaction system navigates message hierarchies.

    Args:
        parts: List of message parts (UserPromptPart, ToolReturnPart, etc.)

    Returns:
        MagicMock: A mock object configured as a ModelRequest with:
            - parts: The message parts list for processing
            - kind: "request" (identifies as a request message)
    """

    def _create(parts: list):
        msg = MagicMock()
        msg.parts = parts
        msg.kind = "request"
        return msg

    return _create


# --- Unit Tests ---


class TestIsToolReturnPart:
    """Test tool return part detection."""

    def test_recognizes_tool_return_part_kind(self):
        """Part with part_kind='tool-return' and content is recognized."""
        part = MagicMock()
        part.part_kind = "tool-return"
        part.content = "some output"
        assert is_tool_return_part(part) is True

    def test_rejects_tool_call_part_kind(self):
        """Part with part_kind='tool-call' is rejected."""
        part = MagicMock()
        part.part_kind = "tool-call"
        part.content = "args"
        assert is_tool_return_part(part) is False

    def test_rejects_missing_part_kind(self):
        """Part without part_kind attribute is rejected."""
        part = MagicMock(spec=["content"])
        part.content = "some output"
        assert is_tool_return_part(part) is False

    def test_rejects_missing_content(self):
        """Part without content attribute is rejected."""
        part = MagicMock(spec=["part_kind"])
        part.part_kind = "tool-return"
        assert is_tool_return_part(part) is False


class TestIsUserPromptPart:
    """Test user prompt part detection."""

    def test_recognizes_user_prompt_part_kind(self):
        """Part with part_kind='user-prompt' is recognized."""
        part = MagicMock()
        part.part_kind = "user-prompt"
        assert is_user_prompt_part(part) is True

    def test_rejects_other_part_kind(self):
        """Part with different part_kind is rejected."""
        part = MagicMock()
        part.part_kind = "tool-return"
        assert is_user_prompt_part(part) is False


class TestCountUserTurns:
    """Test user turn counting."""

    def test_empty_messages_returns_zero(self):
        """Empty message list returns 0."""
        assert count_user_turns([]) == 0

    def test_counts_user_prompt_parts(self, mock_model_request, mock_user_prompt_part):
        """Messages with UserPromptPart are counted."""
        messages = [
            mock_model_request([mock_user_prompt_part()]),
            mock_model_request([mock_user_prompt_part()]),
        ]
        assert count_user_turns(messages) == 2

    def test_counts_dict_user_messages(self):
        """Dict messages with role='user' are counted."""
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "how are you"},
        ]
        assert count_user_turns(messages) == 2

    def test_ignores_tool_return_parts(self, mock_model_request, mock_tool_return_part):
        """Tool return parts are not counted as user turns."""
        messages = [mock_model_request([mock_tool_return_part("output")])]
        assert count_user_turns(messages) == 0


class TestEstimatePartTokens:
    """Test token estimation for parts."""

    def test_estimates_tokens_for_string_content(self, mock_tool_return_part):
        """String content is estimated correctly."""
        # "hello world" is about 2-3 tokens
        part = mock_tool_return_part("hello world")
        tokens = estimate_part_tokens(part, "anthropic:claude-sonnet")
        assert tokens >= 1

    def test_returns_zero_for_missing_content(self):
        """Part without content returns 0."""
        part = MagicMock(spec=["part_kind"])
        tokens = estimate_part_tokens(part, "anthropic:claude-sonnet")
        assert tokens == 0

    def test_handles_non_string_content(self, mock_tool_return_part):
        """Non-string content is converted to repr."""
        part = mock_tool_return_part({"key": "value"})  # type: ignore
        tokens = estimate_part_tokens(part, "anthropic:claude-sonnet")
        assert tokens >= 1


class TestPrunePartContent:
    """Test content replacement."""

    def test_replaces_content_with_placeholder(self, mock_tool_return_part):
        """Content is replaced with placeholder."""
        part = mock_tool_return_part("A" * 10000)
        prune_part_content(part, "anthropic:claude-sonnet")
        assert part.content == PRUNE_PLACEHOLDER

    def test_returns_tokens_reclaimed(self, mock_tool_return_part):
        """Returns positive number of tokens reclaimed."""
        part = mock_tool_return_part("x" * 4000)
        reclaimed = prune_part_content(part, "anthropic:claude-sonnet")
        assert reclaimed > 0

    def test_handles_already_pruned(self, mock_tool_return_part):
        """Already-pruned content returns 0."""
        part = mock_tool_return_part(PRUNE_PLACEHOLDER)
        reclaimed = prune_part_content(part, "anthropic:claude-sonnet")
        assert reclaimed == 0

    def test_handles_immutable_part(self):
        """Immutable part returns 0 without error."""

        class FrozenPart:
            part_kind = "tool-return"
            tool_call_id = "test"

            @property
            def content(self):
                return "immutable content"

            @content.setter
            def content(self, _value):
                raise AttributeError("cannot set content")

        part = FrozenPart()
        reclaimed = prune_part_content(part, "anthropic:claude-sonnet")  # type: ignore
        assert reclaimed == 0


class TestPruneOldToolOutputs:
    """Integration tests for the main pruning function."""

    def test_returns_unchanged_for_empty_messages(self):
        """Empty message list returns unchanged."""
        result, reclaimed = prune_old_tool_outputs([], "anthropic:claude-sonnet")
        assert result == []
        assert reclaimed == 0

    def test_returns_unchanged_when_insufficient_turns(
        self, mock_model_request, mock_tool_return_part
    ):
        """Insufficient user turns returns unchanged."""
        # Only tool outputs, no user turns
        messages = [mock_model_request([mock_tool_return_part("output")])]
        result, reclaimed = prune_old_tool_outputs(messages, "anthropic:claude-sonnet")
        assert reclaimed == 0

    def test_protects_recent_tool_outputs(
        self, mock_model_request, mock_user_prompt_part, mock_tool_return_part
    ):
        """Recent tool outputs within protection window are not pruned."""
        # Create enough user turns
        user_msgs = [
            mock_model_request([mock_user_prompt_part()]) for _ in range(PRUNE_MIN_USER_TURNS)
        ]
        # Small tool output that fits in protection window
        tool_msg = mock_model_request([mock_tool_return_part("small output")])

        messages = user_msgs + [tool_msg]
        result, reclaimed = prune_old_tool_outputs(messages, "anthropic:claude-sonnet")
        assert reclaimed == 0
        assert tool_msg.parts[0].content == "small output"

    def test_prunes_old_tool_outputs_beyond_protection(
        self, mock_model_request, mock_user_prompt_part, mock_tool_return_part
    ):
        """Old tool outputs beyond protection window are pruned."""
        # Create enough user turns
        user_msgs = [
            mock_model_request([mock_user_prompt_part()]) for _ in range(PRUNE_MIN_USER_TURNS)
        ]

        # Create tool output with small content, mock token count to exceed thresholds
        tool_part = mock_tool_return_part("large content")
        tool_msgs = [mock_model_request([tool_part])]

        messages = user_msgs + tool_msgs

        # Mock estimate_tokens to return 70k tokens (exceeds 40k protect + 20k minimum)
        with patch(
            "tunacode.core.compaction.estimate_tokens",
            side_effect=lambda text, _: 70000 if text == "large content" else 10,
        ):
            result, reclaimed = prune_old_tool_outputs(messages, "anthropic:claude-sonnet")

        # The old tool output should be pruned
        assert reclaimed > 0
        assert tool_part.content == PRUNE_PLACEHOLDER

    def test_respects_minimum_threshold(
        self, mock_model_request, mock_user_prompt_part, mock_tool_return_part
    ):
        """Pruning is skipped if savings below minimum threshold."""
        # Create enough user turns
        user_msgs = [
            mock_model_request([mock_user_prompt_part()]) for _ in range(PRUNE_MIN_USER_TURNS)
        ]

        # Create TWO tool outputs:
        # - recent_part: 35k tokens (within protection)
        # - old_part: 10k tokens (would be prunable, but 10k < 20k minimum)
        old_part = mock_tool_return_part("old content")
        recent_part = mock_tool_return_part("recent content")
        tool_msgs = [
            mock_model_request([old_part]),  # older, scanned last
            mock_model_request([recent_part]),  # newer, scanned first
        ]

        messages = user_msgs + tool_msgs

        # Mock: recent=35k (protected), old=10k (prunable but < 20k min)
        def mock_tokens(text, _):
            if text == "recent content":
                return 35000
            if text == "old content":
                return 10000
            return 10

        with patch("tunacode.core.compaction.estimate_tokens", side_effect=mock_tokens):
            result, reclaimed = prune_old_tool_outputs(messages, "anthropic:claude-sonnet")

        # Should not prune because 10k savings < 20k minimum threshold
        assert reclaimed == 0
        assert old_part.content == "old content"

    def test_handles_mixed_message_types(
        self, mock_model_request, mock_user_prompt_part, mock_tool_return_part
    ):
        """Handles mix of dicts, ModelRequest, and messages without parts."""
        messages = [
            {"role": "user", "content": "hello"},
            mock_model_request([mock_user_prompt_part()]),
            {"thought": "thinking..."},  # dict without role
            mock_model_request([mock_tool_return_part("output")]),
        ]

        # Should not crash
        result, reclaimed = prune_old_tool_outputs(messages, "anthropic:claude-sonnet")
        assert result == messages  # Same list reference


class TestConstants:
    """Verify constant values match expected OpenCode values."""

    def test_prune_protect_tokens(self):
        """Protection window is 40k tokens."""
        assert PRUNE_PROTECT_TOKENS == 40_000

    def test_prune_minimum_threshold(self):
        """Minimum threshold is 20k tokens."""
        assert PRUNE_MINIMUM_THRESHOLD == 20_000

    def test_prune_min_user_turns(self):
        """Require at least 2 user turns."""
        assert PRUNE_MIN_USER_TURNS == 2

    def test_placeholder_text(self):
        """Placeholder text matches expected value."""
        assert PRUNE_PLACEHOLDER == "[Old tool result content cleared]"
