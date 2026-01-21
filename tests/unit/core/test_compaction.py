"""Tests for tool output pruning (compaction.py).

Tests the compaction system that manages context window usage by pruning old tool outputs
while preserving recent content. The system uses a backward-scanning algorithm with:

1. Protection window for recent outputs (40k tokens)
2. Minimum threshold before pruning (20k tokens)
3. Minimum user turns required (2 turns)
4. Placeholder replacement for pruned content

Tests cover part type detection, token estimation, protection logic, and edge cases.
"""

from unittest.mock import MagicMock, patch

import pytest

from tunacode.core.agents.resume.prune import (
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
    for testing compaction behavior.

    Args:
        content: The tool output content string
        tool_name: Name of the tool that generated the output

    Returns:
        MagicMock: A mock ToolReturnPart with:
            - part_kind: "tool-return"
            - tool_name: Tool identifier
            - content: The tool output content
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
    to simulate user input messages in compaction tests.

    Args:
        content: The user message content

    Returns:
        MagicMock: A mock UserPromptPart with:
            - part_kind: "user-prompt"
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
    to simulate the container structure that holds message parts.

    Args:
        parts: List of message parts (UserPromptPart, ToolReturnPart, etc.)

    Returns:
        MagicMock: A mock ModelRequest with:
            - parts: The message parts list for processing
            - kind: "request"
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
        part = MagicMock()
        part.part_kind = "tool-return"
        part.content = "some output"
        assert is_tool_return_part(part) is True

    def test_rejects_tool_call_part_kind(self):
        part = MagicMock()
        part.part_kind = "tool-call"
        part.content = "args"
        assert is_tool_return_part(part) is False

    def test_rejects_missing_part_kind(self):
        part = MagicMock(spec=["content"])
        part.content = "some output"
        assert is_tool_return_part(part) is False

    def test_rejects_missing_content(self):
        part = MagicMock(spec=["part_kind"])
        part.part_kind = "tool-return"
        assert is_tool_return_part(part) is False


class TestIsUserPromptPart:
    """Test user prompt part detection."""

    def test_recognizes_user_prompt_part_kind(self):
        part = MagicMock()
        part.part_kind = "user-prompt"
        assert is_user_prompt_part(part) is True

    def test_rejects_other_part_kind(self):
        part = MagicMock()
        part.part_kind = "tool-return"
        assert is_user_prompt_part(part) is False


class TestCountUserTurns:
    """Test user turn counting."""

    def test_empty_messages_returns_zero(self):
        assert count_user_turns([]) == 0

    def test_counts_user_prompt_parts(self, mock_model_request, mock_user_prompt_part):
        messages = [
            mock_model_request([mock_user_prompt_part()]),
            mock_model_request([mock_user_prompt_part()]),
        ]
        assert count_user_turns(messages) == 2

    def test_counts_dict_user_messages(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "how are you"},
        ]
        assert count_user_turns(messages) == 2

    def test_ignores_tool_return_parts(self, mock_model_request, mock_tool_return_part):
        messages = [mock_model_request([mock_tool_return_part("output")])]
        assert count_user_turns(messages) == 0


class TestEstimatePartTokens:
    """Test token estimation for parts."""

    def test_estimates_tokens_for_string_content(self, mock_tool_return_part):
        part = mock_tool_return_part("hello world")
        tokens = estimate_part_tokens(part, "anthropic:claude-sonnet")
        assert tokens >= 1

    def test_returns_zero_for_missing_content(self):
        part = MagicMock(spec=["part_kind"])
        tokens = estimate_part_tokens(part, "anthropic:claude-sonnet")
        assert tokens == 0

    def test_handles_non_string_content(self, mock_tool_return_part):
        part = mock_tool_return_part({"key": "value"})  # type: ignore
        tokens = estimate_part_tokens(part, "anthropic:claude-sonnet")
        assert tokens >= 1


class TestPrunePartContent:
    """Test content replacement."""

    def test_replaces_content_with_placeholder(self, mock_tool_return_part):
        part = mock_tool_return_part("A" * 10000)
        prune_part_content(part, "anthropic:claude-sonnet")
        assert part.content == PRUNE_PLACEHOLDER

    def test_returns_tokens_reclaimed(self, mock_tool_return_part):
        part = mock_tool_return_part("x" * 4000)
        reclaimed = prune_part_content(part, "anthropic:claude-sonnet")
        assert reclaimed > 0

    def test_handles_already_pruned(self, mock_tool_return_part):
        part = mock_tool_return_part(PRUNE_PLACEHOLDER)
        reclaimed = prune_part_content(part, "anthropic:claude-sonnet")
        assert reclaimed == 0

    def test_handles_immutable_part(self):
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
        result, reclaimed = prune_old_tool_outputs([], "anthropic:claude-sonnet")
        assert result == []
        assert reclaimed == 0

    def test_returns_unchanged_when_insufficient_turns(
        self, mock_model_request, mock_tool_return_part
    ):
        messages = [mock_model_request([mock_tool_return_part("output")])]
        result, reclaimed = prune_old_tool_outputs(messages, "anthropic:claude-sonnet")
        assert reclaimed == 0

    def test_protects_recent_tool_outputs(
        self, mock_model_request, mock_user_prompt_part, mock_tool_return_part
    ):
        user_msgs = [
            mock_model_request([mock_user_prompt_part()]) for _ in range(PRUNE_MIN_USER_TURNS)
        ]
        tool_msg = mock_model_request([mock_tool_return_part("small output")])

        messages = user_msgs + [tool_msg]
        result, reclaimed = prune_old_tool_outputs(messages, "anthropic:claude-sonnet")
        assert reclaimed == 0
        assert tool_msg.parts[0].content == "small output"

    def test_prunes_old_tool_outputs_beyond_protection(
        self, mock_model_request, mock_user_prompt_part, mock_tool_return_part
    ):
        user_msgs = [
            mock_model_request([mock_user_prompt_part()]) for _ in range(PRUNE_MIN_USER_TURNS)
        ]

        tool_part = mock_tool_return_part("large content")
        tool_msgs = [mock_model_request([tool_part])]

        messages = user_msgs + tool_msgs

        with patch(
            "tunacode.core.agents.resume.prune.estimate_tokens",
            side_effect=lambda text, _: 70000 if text == "large content" else 10,
        ):
            result, reclaimed = prune_old_tool_outputs(messages, "anthropic:claude-sonnet")

        assert reclaimed > 0
        assert tool_part.content == PRUNE_PLACEHOLDER

    def test_respects_minimum_threshold(
        self, mock_model_request, mock_user_prompt_part, mock_tool_return_part
    ):
        user_msgs = [
            mock_model_request([mock_user_prompt_part()]) for _ in range(PRUNE_MIN_USER_TURNS)
        ]

        old_part = mock_tool_return_part("old content")
        recent_part = mock_tool_return_part("recent content")
        tool_msgs = [
            mock_model_request([old_part]),  # older, scanned last
            mock_model_request([recent_part]),  # newer, scanned first
        ]

        messages = user_msgs + tool_msgs

        def mock_tokens(text, _):
            if text == "recent content":
                return 35000
            if text == "old content":
                return 10000
            return 10

        with (
            patch("tunacode.core.agents.resume.prune.estimate_tokens", side_effect=mock_tokens),
            patch(
                "tunacode.core.agents.resume.prune.get_prune_thresholds",
                return_value=(PRUNE_PROTECT_TOKENS, PRUNE_MINIMUM_THRESHOLD),
            ),
        ):
            result, reclaimed = prune_old_tool_outputs(messages, "anthropic:claude-sonnet")

        assert reclaimed == 0
        assert old_part.content == "old content"

    def test_handles_mixed_message_types(
        self, mock_model_request, mock_user_prompt_part, mock_tool_return_part
    ):
        messages = [
            {"role": "user", "content": "hello"},
            mock_model_request([mock_user_prompt_part()]),
            {"thought": "thinking..."},  # dict without role
            mock_model_request([mock_tool_return_part("output")]),
        ]

        result, reclaimed = prune_old_tool_outputs(messages, "anthropic:claude-sonnet")
        assert result == messages  # Same list reference


class TestConstants:
    """Verify constant values."""

    def test_prune_protect_tokens(self):
        assert PRUNE_PROTECT_TOKENS == 40_000

    def test_prune_minimum_threshold(self):
        assert PRUNE_MINIMUM_THRESHOLD == 20_000

    def test_prune_min_user_turns(self):
        assert PRUNE_MIN_USER_TURNS == 2

    def test_placeholder_text(self):
        assert PRUNE_PLACEHOLDER == "[Old tool result content cleared]"
