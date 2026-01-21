"""Property-based tests for tool call lifecycle and edge cases.

Tests the args storage/consumption contract and tool call pairing invariant
using hypothesis for property-based testing and real pydantic_ai types.

Related:
- #249 (docs: Document pydantic_ai tool call wire format and lifecycle)
- docs/codebase-map/architecture/conversation-turns.md
"""

import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from pydantic_ai.messages import ToolCallPart, ToolReturnPart

from tunacode.constants import (
    ERROR_TOOL_ARGS_MISSING,
    ERROR_TOOL_CALL_ID_MISSING,
    EXECUTE_TOOLS,
    READ_ONLY_TOOLS,
    WRITE_TOOLS,
    ToolName,
)
from tunacode.core.agents.agent_components.orchestrator.tool_dispatcher import (
    _extract_fallback_tool_calls,
    consume_tool_call_args,
    dispatch_tools,
    normalize_tool_args,
    record_tool_call_args,
)
from tunacode.core.agents.agent_components.response_state import ResponseState
from tunacode.core.agents.agent_components.tool_executor import execute_tools_parallel
from tunacode.core.agents.resume.sanitize import remove_dangling_tool_calls
from tunacode.core.state import SessionState, StateManager
from tunacode.exceptions import StateError
from tunacode.types import AgentState, ToolArgs, ToolCallId

# Mark all tests in this module as hypothesis property tests
pytestmark = pytest.mark.hypothesis

# =============================================================================
# Test Constants
# =============================================================================


MIN_TOOL_CALL_ID_HEX_LEN = 8
MAX_TOOL_CALL_ID_HEX_LEN = 32
MIN_ARG_KEY_LEN = 1
MAX_ARG_KEY_LEN = 20
MAX_ARG_TEXT_LEN = 50
MIN_ARG_INT_VALUE = -1000
MAX_ARG_INT_VALUE = 1000
MAX_ARGS_ITEMS = 5
MAX_TOOL_RETURN_CONTENT_LEN = 500
MIN_TOOL_CALL_PARTS = 1
MAX_TOOL_CALL_PARTS = 10
MAX_TOOL_CALL_PARTS_SMALL = 5
MAX_EXAMPLES_STANDARD = 50
MAX_EXAMPLES_REDUCED = 30
MAX_EXAMPLES_SMALL = 20
MAX_PARALLEL_LIMIT = 2
MAX_RESULT_TEXT_LEN = 80
TEXT_PART_KIND = "text"
TOOL_CALL_TEXT_PREFIX = "assistant:"
TOOL_CALL_TEXT_SUFFIX = "end"
SUPPRESS_HEALTH_CHECKS = [HealthCheck.function_scoped_fixture, HealthCheck.too_slow]

READ_ONLY_TOOL_NAMES = [
    tool.value for tool in READ_ONLY_TOOLS if tool != ToolName.RESEARCH_CODEBASE
]
WRITE_EXECUTE_TOOL_NAMES = [tool.value for tool in WRITE_TOOLS + EXECUTE_TOOLS] + [
    ToolName.SUBMIT.value
]
RESEARCH_TOOL_NAME = ToolName.RESEARCH_CODEBASE.value
ALL_TOOL_NAMES = READ_ONLY_TOOL_NAMES + WRITE_EXECUTE_TOOL_NAMES + [RESEARCH_TOOL_NAME]

TOOL_CALL_FORMATS = ("qwen2_xml", "hermes", "code_fence", "raw_json")


# =============================================================================
# Hypothesis Strategies
# =============================================================================


@st.composite
def tool_call_id_strategy(draw: st.DrawFn) -> str:
    """Generate valid tool_call_id strings.

    Format: "call_" + UUID-like string (8-32 hex chars)
    """
    hex_chars = draw(
        st.text(
            min_size=MIN_TOOL_CALL_ID_HEX_LEN,
            max_size=MAX_TOOL_CALL_ID_HEX_LEN,
            alphabet="0123456789abcdef",
        )
    )
    return f"call_{hex_chars}"


@st.composite
def tool_args_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate valid tool args dictionaries.

    Args must be JSON-serializable and realistic for tool calls.
    """
    # Common tool argument patterns
    primitive_strategy = st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=MIN_ARG_INT_VALUE, max_value=MAX_ARG_INT_VALUE),
        st.floats(allow_infinity=False, allow_nan=False),
        st.text(max_size=MAX_ARG_TEXT_LEN),
    )

    def args_dict(max_size: int = MAX_ARGS_ITEMS) -> dict[str, Any]:
        return st.dictionaries(
            keys=st.text(
                min_size=MIN_ARG_KEY_LEN,
                max_size=MAX_ARG_KEY_LEN,
                alphabet="abcdefghijklmnopqrstuvwxyz_",
            ),
            values=primitive_strategy,
            min_size=0,
            max_size=max_size,
        )

    return draw(args_dict())


@st.composite
def tool_call_part_strategy(draw: st.DrawFn) -> ToolCallPart:
    """Generate ToolCallPart instances with realistic data."""
    tool_name = draw(st.sampled_from(["read_file", "grep", "bash", "write_file", "glob"]))
    args = draw(tool_args_strategy())
    tool_call_id = draw(tool_call_id_strategy())

    return ToolCallPart(tool_name=tool_name, args=args, tool_call_id=tool_call_id)


@st.composite
def tool_return_part_strategy(draw: st.DrawFn) -> ToolReturnPart:
    """Generate ToolReturnPart instances with realistic data."""
    tool_call_id = draw(tool_call_id_strategy())
    tool_name = draw(st.sampled_from(["read_file", "grep", "bash", "write_file", "glob"]))
    content = draw(st.text(max_size=MAX_TOOL_RETURN_CONTENT_LEN))

    return ToolReturnPart(tool_call_id=tool_call_id, content=content, tool_name=tool_name)


@st.composite
def tool_call_part_for_dispatch_strategy(draw: st.DrawFn) -> ToolCallPart:
    """Generate ToolCallPart instances spanning tool categories."""
    tool_name = draw(st.sampled_from(ALL_TOOL_NAMES))
    args = draw(tool_args_strategy())
    tool_call_id = draw(tool_call_id_strategy())
    return ToolCallPart(tool_name=tool_name, args=args, tool_call_id=tool_call_id)


@st.composite
def tool_call_text_strategy(draw: st.DrawFn) -> tuple[str, dict[str, Any], str]:
    """Generate fallback tool call text and its expected args."""
    tool_name = draw(st.sampled_from(ALL_TOOL_NAMES))
    tool_args = draw(tool_args_strategy())
    format_name = draw(st.sampled_from(TOOL_CALL_FORMATS))
    tool_text = build_tool_call_text(format_name, tool_name, tool_args)
    return tool_text, tool_args, tool_name


@st.composite
def result_part_strategy(draw: st.DrawFn) -> "ResultPart":
    """Generate parts with expected results for parallel execution."""
    tool_name = draw(st.sampled_from(ALL_TOOL_NAMES))
    expected_result = draw(st.text(max_size=MAX_RESULT_TEXT_LEN))
    return ResultPart(tool_name=tool_name, expected_result=expected_result)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def state_manager() -> StateManager:
    """Create a StateManager with fresh SessionState for each test."""
    return StateManager()


@pytest.fixture
def session_state() -> SessionState:
    """Create a fresh SessionState for each test."""
    return SessionState()


# =============================================================================
# Helper Data Structures
# =============================================================================


@dataclass(frozen=True, slots=True)
class TextPart:
    """Minimal text part for fallback parsing."""

    part_kind: str
    content: str


@dataclass(frozen=True, slots=True)
class ResultPart:
    """Tool call part with embedded expected result."""

    tool_name: str
    expected_result: str


@dataclass(frozen=True, slots=True)
class DummyNode:
    """Placeholder node for tool execution tests."""

    label: str = "node"


def build_tool_call_text(tool_format: str, tool_name: str, args: dict[str, Any]) -> str:
    """Build tool call text for fallback parsing."""
    payload = {"name": tool_name, "arguments": args}
    payload_json = json.dumps(payload)
    args_json = json.dumps(args)

    if tool_format == "qwen2_xml":
        return f"<tool_call>{payload_json}</tool_call>"
    if tool_format == "hermes":
        return f"<function={tool_name}>{args_json}</function>"
    if tool_format == "code_fence":
        return f"```json\n{payload_json}\n```"
    if tool_format == "raw_json":
        return f"{TOOL_CALL_TEXT_PREFIX}\n{payload_json}\n{TOOL_CALL_TEXT_SUFFIX}"

    raise AssertionError(f"Unexpected tool format: {tool_format}")


# =============================================================================
# Property Tests: Args Storage/Consumption Contract
# =============================================================================


@given(part=tool_call_part_strategy())
@settings(
    max_examples=MAX_EXAMPLES_STANDARD,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_record_tool_call_args_stores_correctly(
    part: ToolCallPart, state_manager: StateManager
) -> None:
    """record_tool_call_args should store args keyed by tool_call_id."""
    # Act
    recorded_args = await record_tool_call_args(part, state_manager)

    # Assert
    assert part.tool_call_id in state_manager.session.tool_call_args_by_id
    stored_args = state_manager.session.tool_call_args_by_id[part.tool_call_id]
    assert stored_args == recorded_args


@given(part=tool_call_part_strategy())
@settings(
    max_examples=MAX_EXAMPLES_STANDARD,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_record_tool_call_args_returns_parsed_args(
    part: ToolCallPart, state_manager: StateManager
) -> None:
    """record_tool_call_args should return parsed args matching input."""
    result = await record_tool_call_args(part, state_manager)

    assert isinstance(result, dict)
    # The parsed args should have the same keys as the raw args
    assert set(result.keys()) == set(part.args.keys())


@given(part=tool_call_part_strategy())
@settings(
    max_examples=MAX_EXAMPLES_STANDARD,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_consume_tool_call_args_retrieves_and_removes(
    part: ToolCallPart, state_manager: StateManager
) -> None:
    """consume_tool_call_args should retrieve and delete stored args."""
    # Arrange: First record the args
    recorded_args = await record_tool_call_args(part, state_manager)
    tool_call_id = part.tool_call_id

    # Act: Consume the args
    consumed_args = consume_tool_call_args(part, state_manager)

    # Assert: Should return the same args that were recorded
    assert consumed_args == recorded_args

    # Assert: Should be removed from storage
    assert tool_call_id not in state_manager.session.tool_call_args_by_id


@given(part=tool_call_part_strategy())
@settings(
    max_examples=MAX_EXAMPLES_STANDARD,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_consume_is_idempotent_fails_on_second_call(
    part: ToolCallPart, state_manager: StateManager
) -> None:
    """Second consume call for same tool_call_id should fail gracefully."""
    # Arrange: Record and consume once
    await record_tool_call_args(part, state_manager)
    consume_tool_call_args(part, state_manager)

    # Act/Assert: Second consume should raise StateError
    with pytest.raises(StateError) as exc_info:
        consume_tool_call_args(part, state_manager)

    assert ERROR_TOOL_ARGS_MISSING.format(tool_call_id=part.tool_call_id) in str(exc_info.value)


# =============================================================================
# Property Tests: Round-trip Invariant
# =============================================================================


@given(part=tool_call_part_strategy())
@settings(
    max_examples=MAX_EXAMPLES_STANDARD,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_round_trip_preserves_args(part: ToolCallPart, state_manager: StateManager) -> None:
    """Round-trip: record → consume should return original args."""
    # Arrange
    original_args = dict(part.args)

    # Act: Record then consume
    await record_tool_call_args(part, state_manager)
    consumed_args = consume_tool_call_args(part, state_manager)

    # Assert: Consumed args should match original
    assert consumed_args == original_args


@given(
    parts=st.lists(
        tool_call_part_strategy(),
        min_size=MIN_TOOL_CALL_PARTS,
        max_size=MAX_TOOL_CALL_PARTS,
    )
)
@settings(
    max_examples=MAX_EXAMPLES_REDUCED,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_multiple_tool_calls_maintain_distinct_args(
    parts: list[ToolCallPart], state_manager: StateManager
) -> None:
    """Multiple tool calls should maintain distinct args by tool_call_id."""
    # Assume all tool_call_ids are unique (pydantic-ai guarantee)
    tool_call_ids = [p.tool_call_id for p in parts]
    assume(len(set(tool_call_ids)) == len(tool_call_ids))

    # Act: Record all args
    recorded_args = {}
    for part in parts:
        args = await record_tool_call_args(part, state_manager)
        recorded_args[part.tool_call_id] = args

    # Assert: All stored, all retrievable in any order
    assert len(state_manager.session.tool_call_args_by_id) == len(parts)

    for part in parts:
        consumed = consume_tool_call_args(part, state_manager)
        assert consumed == recorded_args[part.tool_call_id]

    # Assert: All consumed, dict empty
    assert len(state_manager.session.tool_call_args_by_id) == 0


# =============================================================================
# Property Tests: Tool Call Pairing Invariant
# =============================================================================


@given(call_part=tool_call_part_strategy())
@settings(max_examples=MAX_EXAMPLES_SMALL)
def test_tool_call_part_has_required_fields(call_part: ToolCallPart) -> None:
    """ToolCallPart must have tool_name, args, and tool_call_id."""
    assert hasattr(call_part, "tool_name")
    assert hasattr(call_part, "args")
    assert hasattr(call_part, "tool_call_id")
    assert isinstance(call_part.tool_name, str)
    assert isinstance(call_part.args, dict)
    assert isinstance(call_part.tool_call_id, str)


@given(return_part=tool_return_part_strategy())
@settings(max_examples=MAX_EXAMPLES_STANDARD)
def test_tool_return_part_has_required_fields(return_part: ToolReturnPart) -> None:
    """ToolReturnPart must have tool_call_id, content, and tool_name (but NOT args)."""
    assert hasattr(return_part, "tool_call_id")
    assert hasattr(return_part, "content")
    assert hasattr(return_part, "tool_name")
    assert not hasattr(return_part, "args") or getattr(return_part, "args", None) is None


@given(
    call_parts=st.lists(
        tool_call_part_strategy(),
        min_size=MIN_TOOL_CALL_PARTS,
        max_size=MAX_TOOL_CALL_PARTS_SMALL,
    ),
    return_parts=st.lists(
        tool_return_part_strategy(),
        min_size=MIN_TOOL_CALL_PARTS,
        max_size=MAX_TOOL_CALL_PARTS_SMALL,
    ),
)
@settings(
    max_examples=MAX_EXAMPLES_REDUCED,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_pairing_invariant_requires_matching_ids(
    call_parts: list[ToolCallPart],
    return_parts: list[ToolReturnPart],
    state_manager: StateManager,
) -> None:
    """ToolReturnPart.tool_call_id must reference a stored ToolCallPart."""
    # Record all call args
    for part in call_parts:
        await record_tool_call_args(part, state_manager)

    # For each return part, check if it references a known call
    for return_part in return_parts:
        if return_part.tool_call_id in state_manager.session.tool_call_args_by_id:
            # Should succeed
            consume_tool_call_args(return_part, state_manager)
        else:
            # Should fail - unknown tool_call_id
            with pytest.raises(StateError) as exc_info:
                consume_tool_call_args(return_part, state_manager)
            # Check for the error message without the format placeholder
            assert "Tool args missing for tool_call_id" in str(exc_info.value)


# =============================================================================
# Edge Case Unit Tests
# =============================================================================


def test_missing_tool_call_id_raises_state_error(state_manager: StateManager) -> None:
    """consume_tool_call_args should raise StateError when tool_call_id is None."""

    # Arrange: Create a part without tool_call_id
    @dataclass
    class MockPart:
        tool_call_id: str | None = None
        content: str = "test"

    part = MockPart(tool_call_id=None)

    # Act/Assert
    with pytest.raises(StateError) as exc_info:
        consume_tool_call_args(part, state_manager)

    assert ERROR_TOOL_CALL_ID_MISSING in str(exc_info.value)


def test_missing_args_in_cache_raises_state_error(state_manager: StateManager) -> None:
    """consume_tool_call_args should raise StateError when args not cached."""
    # Arrange: Create a return part without prior recording
    return_part = ToolReturnPart(
        tool_call_id="call_unknown123", content="test", tool_name="read_file"
    )

    # Act/Assert
    with pytest.raises(StateError) as exc_info:
        consume_tool_call_args(return_part, state_manager)

    assert ERROR_TOOL_ARGS_MISSING.format(tool_call_id="call_unknown123") in str(exc_info.value)


async def test_duplicate_tool_call_id_overwrites_previous(state_manager: StateManager) -> None:
    """Duplicate tool_call_id should overwrite previous args (current behavior)."""
    # Arrange
    tool_call_id = "call_abc123"
    first_args = {"path": "/tmp/first.txt"}
    second_args = {"path": "/tmp/second.txt"}

    first_part = ToolCallPart(tool_name="read_file", args=first_args, tool_call_id=tool_call_id)
    second_part = ToolCallPart(tool_name="read_file", args=second_args, tool_call_id=tool_call_id)

    # Act: Record same tool_call_id twice
    await record_tool_call_args(first_part, state_manager)
    await record_tool_call_args(second_part, state_manager)

    # Assert: Second args should have overwritten first
    stored = state_manager.session.tool_call_args_by_id[tool_call_id]
    assert stored == second_args


# =============================================================================
# Property Tests: remove_dangling_tool_calls
# =============================================================================


@dataclass
class MockMessage:
    """Mock message with tool_calls for testing."""

    tool_calls: list[ToolCallPart] = field(default_factory=list)
    parts: list[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.tool_calls:
            return

        existing_call_ids = {getattr(part, "tool_call_id", None) for part in self.parts}
        for call in self.tool_calls:
            tool_call_id = getattr(call, "tool_call_id", None)
            if tool_call_id in existing_call_ids:
                continue
            self.parts.append(call)
            existing_call_ids.add(tool_call_id)


def _extract_tool_call_ids(message: Any) -> list[str]:
    """Extract tool_call_ids from a message for testing."""
    tool_call_ids = []
    if hasattr(message, "tool_calls"):
        for call in message.tool_calls:
            if hasattr(call, "tool_call_id"):
                tool_call_ids.append(call.tool_call_id)
    return tool_call_ids


@given(
    call_parts=st.lists(
        tool_call_part_strategy(),
        min_size=0,
        max_size=MAX_TOOL_CALL_PARTS_SMALL,
    ),
)
@settings(
    max_examples=MAX_EXAMPLES_STANDARD,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
def test_remove_dangling_removes_trailing_tool_calls(
    call_parts: list[ToolCallPart], session_state: SessionState
) -> None:
    """remove_dangling_tool_calls should remove dangling tool call messages."""
    # Arrange: Create messages with trailing tool calls
    messages = []
    tool_call_args_by_id: dict[ToolCallId, ToolArgs] = {}

    for part in call_parts:
        msg = MockMessage(tool_calls=[part])
        messages.append(msg)
        tool_call_args_by_id[part.tool_call_id] = part.args

    # Add a non-tool-call message at start (should not be removed)
    messages.insert(0, MockMessage(tool_calls=[], parts=[]))

    initial_count = len(messages)

    # Act
    removed = remove_dangling_tool_calls(messages, tool_call_args_by_id)

    # Assert: If there were tool calls, they should be removed
    if call_parts:
        assert removed is True
        # Only non-tool-call message should remain
        assert len(messages) == 1
        # Tool call args should be cleared
        assert len(tool_call_args_by_id) == 0
    else:
        assert removed is False
        assert len(messages) == initial_count


def test_remove_dangling_removes_non_trailing_tool_calls(session_state: SessionState) -> None:
    """remove_dangling_tool_calls should remove tool calls anywhere in history."""
    # Arrange: Dangling tool call followed by a non-tool message
    tool_call = ToolCallPart(tool_name="read_file", args={"path": "test"}, tool_call_id="call_1")
    non_tool_msg = MockMessage(tool_calls=[], parts=[])
    dangling_tool_msg = MockMessage(tool_calls=[tool_call])

    messages = [dangling_tool_msg, non_tool_msg]
    tool_call_args_by_id = {tool_call.tool_call_id: tool_call.args}

    # Act
    remove_dangling_tool_calls(messages, tool_call_args_by_id)

    # Assert: Dangling message removed, non-tool message preserved
    assert len(messages) == 1
    assert messages[0] is non_tool_msg


def test_remove_dangling_with_empty_messages(session_state: SessionState) -> None:
    """remove_dangling_tool_calls should handle empty message list."""
    messages: list[Any] = []
    tool_call_args_by_id: dict[ToolCallId, ToolArgs] = {}

    # Act
    removed = remove_dangling_tool_calls(messages, tool_call_args_by_id)

    # Assert
    assert removed is False
    assert len(messages) == 0


def test_cancelled_error_triggers_cleanup(session_state: SessionState) -> None:
    """CancelledError should trigger remove_dangling_tool_calls like UserAbortError.

    This test validates that the cleanup logic invoked in the except block at main.py:409
    works correctly when triggered by asyncio.CancelledError (timeout scenario).

    The exception handler catches both UserAbortError and CancelledError:
        except (UserAbortError, asyncio.CancelledError):
            cleanup_applied = remove_dangling_tool_calls(messages, tool_call_args_by_id)

    Related: PR #246 (UserAbortError)
    See: memory-bank/research/2026-01-19_14-30-00_dangling_tool_calls_timeout_gap.md
    """
    # Arrange: Simulate state mid-tool-execution when CancelledError fires
    tool_call = ToolCallPart(
        tool_name="bash", args={"command": "sleep 60"}, tool_call_id="call_timeout123"
    )
    dangling_message = MockMessage(tool_calls=[tool_call])
    messages: list[Any] = [dangling_message]
    tool_call_args_by_id: dict[ToolCallId, ToolArgs] = {tool_call.tool_call_id: tool_call.args}

    # Act: Simulate the cleanup that happens in except (UserAbortError, CancelledError) block
    # This is exactly what main.py:409-416 does
    cleanup_applied = remove_dangling_tool_calls(messages, tool_call_args_by_id)

    # Assert: State is now valid for next API request
    assert cleanup_applied is True
    assert len(messages) == 0, "Dangling tool call message should be removed"
    assert len(tool_call_args_by_id) == 0, "Cached tool args should be cleared"


def test_remove_dangling_clears_corresponding_args(session_state: SessionState) -> None:
    """remove_dangling_tool_calls should clear args for removed tool calls."""
    # Arrange
    call_1 = ToolCallPart(tool_name="read_file", args={"path": "file1"}, tool_call_id="call_1")
    call_2 = ToolCallPart(tool_name="grep", args={"pattern": "test"}, tool_call_id="call_2")

    messages = [
        MockMessage(tool_calls=[call_1]),
        MockMessage(tool_calls=[call_2]),
    ]
    tool_call_args_by_id = {
        call_1.tool_call_id: call_1.args,
        call_2.tool_call_id: call_2.args,
    }

    # Act
    remove_dangling_tool_calls(messages, tool_call_args_by_id)

    # Assert: All args cleared
    assert len(tool_call_args_by_id) == 0
    assert len(messages) == 0


def test_remove_dangling_keeps_matched_tool_calls(session_state: SessionState) -> None:
    """remove_dangling_tool_calls should not remove matched tool calls."""
    tool_call = ToolCallPart(tool_name="read_file", args={"path": "file1"}, tool_call_id="call_ok")
    tool_return = ToolReturnPart(
        tool_call_id=tool_call.tool_call_id,
        content="ok",
        tool_name=tool_call.tool_name,
    )

    call_message = MockMessage(tool_calls=[tool_call])
    return_message = MockMessage(parts=[tool_return])
    messages = [call_message, return_message]
    tool_call_args_by_id = {tool_call.tool_call_id: tool_call.args}

    removed = remove_dangling_tool_calls(messages, tool_call_args_by_id)

    assert removed is False
    assert messages == [call_message, return_message]
    assert tool_call_args_by_id == {tool_call.tool_call_id: tool_call.args}


def test_remove_dangling_removes_only_unmatched_calls(session_state: SessionState) -> None:
    """remove_dangling_tool_calls should remove only unmatched tool calls."""
    matched_call = ToolCallPart(
        tool_name="read_file", args={"path": "file1"}, tool_call_id="call_matched"
    )
    unmatched_call = ToolCallPart(
        tool_name="grep", args={"pattern": "test"}, tool_call_id="call_unmatched"
    )
    tool_return = ToolReturnPart(
        tool_call_id=matched_call.tool_call_id,
        content="ok",
        tool_name=matched_call.tool_name,
    )

    matched_message = MockMessage(tool_calls=[matched_call])
    return_message = MockMessage(parts=[tool_return])
    unmatched_message = MockMessage(tool_calls=[unmatched_call])
    messages = [matched_message, return_message, unmatched_message]
    tool_call_args_by_id = {
        matched_call.tool_call_id: matched_call.args,
        unmatched_call.tool_call_id: unmatched_call.args,
    }

    removed = remove_dangling_tool_calls(messages, tool_call_args_by_id)

    assert removed is True
    assert messages == [matched_message, return_message]
    assert tool_call_args_by_id == {matched_call.tool_call_id: matched_call.args}


# =============================================================================
# Property Tests: Argument Normalization
# =============================================================================


@given(raw_args=tool_args_strategy())
@settings(
    max_examples=MAX_EXAMPLES_STANDARD,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_normalize_tool_args_accepts_dict(raw_args: dict[str, Any]) -> None:
    """normalize_tool_args should preserve dictionary inputs."""
    normalized_args = await normalize_tool_args(raw_args)

    assert normalized_args == raw_args


@given(raw_args=tool_args_strategy())
@settings(
    max_examples=MAX_EXAMPLES_STANDARD,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_normalize_tool_args_parses_json_string(raw_args: dict[str, Any]) -> None:
    """normalize_tool_args should parse JSON strings into dictionaries."""
    raw_args_json = json.dumps(raw_args)
    normalized_args = await normalize_tool_args(raw_args_json)

    assert normalized_args == raw_args


# =============================================================================
# Property Tests: Fallback Parsing
# =============================================================================


@given(tool_call=tool_call_text_strategy())
@settings(
    max_examples=MAX_EXAMPLES_REDUCED,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_extract_fallback_tool_calls_records_args(
    tool_call: tuple[str, dict[str, Any], str], state_manager: StateManager
) -> None:
    """Fallback extraction should parse and cache tool args."""
    response_state = ResponseState()
    response_state.transition_to(AgentState.ASSISTANT)
    tool_text, expected_args, expected_tool_name = tool_call
    text_part = TextPart(part_kind=TEXT_PART_KIND, content=tool_text)
    parts = [text_part]

    results = await _extract_fallback_tool_calls(parts, state_manager, response_state)

    assert len(results) == 1
    result_part, result_args = results[0]
    tool_call_id = result_part.tool_call_id
    cached_args = state_manager.session.tool_call_args_by_id[tool_call_id]

    assert result_args == expected_args
    assert cached_args == expected_args
    assert result_part.tool_name == expected_tool_name
    assert response_state.current_state == AgentState.TOOL_EXECUTION


# =============================================================================
# Property Tests: Tool Dispatch Lifecycle
# =============================================================================


@given(
    parts=st.lists(
        tool_call_part_for_dispatch_strategy(),
        min_size=MIN_TOOL_CALL_PARTS,
        max_size=MAX_TOOL_CALL_PARTS_SMALL,
    )
)
@settings(
    max_examples=MAX_EXAMPLES_REDUCED,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_dispatch_tools_batches_by_category(
    parts: list[ToolCallPart], monkeypatch: pytest.MonkeyPatch, state_manager: StateManager
) -> None:
    """dispatch_tools should batch read-only and research tools separately."""
    state_manager.session.tool_calls = []
    state_manager.session.tool_call_args_by_id = {}
    state_manager.session.batch_counter = 0
    response_state = ResponseState()
    response_state.transition_to(AgentState.ASSISTANT)
    node = DummyNode()
    recorded_batches: list[list[str]] = []
    tool_callback = AsyncMock()
    tool_names = [part.tool_name for part in parts]

    async def fake_execute_tools_parallel(
        tool_calls: list[tuple[Any, Any]], callback: Any
    ) -> list[Any]:
        batch_tool_names = [getattr(part, "tool_name", "") for part, _ in tool_calls]
        recorded_batches.append(batch_tool_names)
        for part, task_node in tool_calls:
            await callback(part, task_node)
        return [None for _ in tool_calls]

    monkeypatch.setattr(
        "tunacode.core.agents.agent_components.tool_executor.execute_tools_parallel",
        fake_execute_tools_parallel,
    )

    dispatch_result = await dispatch_tools(
        parts=parts,
        node=node,
        state_manager=state_manager,
        tool_callback=tool_callback,
        _tool_result_callback=None,
        tool_start_callback=None,
        response_state=response_state,
    )

    expected_read_only = [name for name in tool_names if name in READ_ONLY_TOOL_NAMES]
    expected_research = [name for name in tool_names if name == RESEARCH_TOOL_NAME]
    expected_parallel = expected_research + expected_read_only
    parallel_batches = [name for batch in recorded_batches for name in batch]

    assert dispatch_result.has_tool_calls is True
    assert dispatch_result.used_fallback is False
    assert parallel_batches == expected_parallel
    assert tool_callback.call_count == len(parts)
    assert len(state_manager.session.tool_calls) == len(parts)
    assert response_state.current_state == AgentState.RESPONSE

    # NOTE: submit tool no longer sets task_completed - pydantic-ai loop ends naturally
    # if ToolName.SUBMIT.value in tool_names:
    #     assert response_state.task_completed is True

    for part in parts:
        if part.tool_name in expected_parallel:
            continue
        assert part.tool_name in WRITE_EXECUTE_TOOL_NAMES


@given(tool_call=tool_call_text_strategy())
@settings(
    max_examples=MAX_EXAMPLES_REDUCED,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_dispatch_tools_uses_fallback_for_text_only_calls(
    tool_call: tuple[str, dict[str, Any], str],
    monkeypatch: pytest.MonkeyPatch,
    state_manager: StateManager,
) -> None:
    """dispatch_tools should use fallback parsing when no tool-call parts exist."""
    state_manager.session.tool_calls = []
    state_manager.session.tool_call_args_by_id = {}
    state_manager.session.batch_counter = 0
    response_state = ResponseState()
    response_state.transition_to(AgentState.ASSISTANT)
    node = DummyNode()
    tool_callback = AsyncMock()
    recorded_batches: list[list[str]] = []
    tool_text, _expected_args, expected_tool_name = tool_call
    text_part = TextPart(part_kind=TEXT_PART_KIND, content=tool_text)

    async def fake_execute_tools_parallel(
        tool_calls: list[tuple[Any, Any]], callback: Any
    ) -> list[Any]:
        batch_tool_names = [getattr(part, "tool_name", "") for part, _ in tool_calls]
        recorded_batches.append(batch_tool_names)
        for part, task_node in tool_calls:
            await callback(part, task_node)
        return [None for _ in tool_calls]

    monkeypatch.setattr(
        "tunacode.core.agents.agent_components.tool_executor.execute_tools_parallel",
        fake_execute_tools_parallel,
    )

    dispatch_result = await dispatch_tools(
        parts=[text_part],
        node=node,
        state_manager=state_manager,
        tool_callback=tool_callback,
        _tool_result_callback=None,
        tool_start_callback=None,
        response_state=response_state,
    )

    assert dispatch_result.used_fallback is True
    assert dispatch_result.has_tool_calls is True
    assert len(state_manager.session.tool_calls) == 1
    assert response_state.current_state == AgentState.RESPONSE

    is_parallel_tool = (
        expected_tool_name in READ_ONLY_TOOL_NAMES or expected_tool_name == RESEARCH_TOOL_NAME
    )
    if is_parallel_tool:
        assert len(recorded_batches) == 1
        return

    assert len(recorded_batches) == 0


# =============================================================================
# Property Tests: Parallel Execution Ordering
# =============================================================================


@given(
    parts=st.lists(
        result_part_strategy(),
        min_size=MIN_TOOL_CALL_PARTS,
        max_size=MAX_TOOL_CALL_PARTS_SMALL,
    )
)
@settings(
    max_examples=MAX_EXAMPLES_REDUCED,
    suppress_health_check=SUPPRESS_HEALTH_CHECKS,
)
async def test_execute_tools_parallel_preserves_order(
    parts: list[ResultPart], monkeypatch: pytest.MonkeyPatch
) -> None:
    """execute_tools_parallel should preserve input order."""
    node = DummyNode()
    tool_calls = [(part, node) for part in parts]
    expected_results = [part.expected_result for part in parts]
    monkeypatch.setenv("TUNACODE_MAX_PARALLEL", str(MAX_PARALLEL_LIMIT))

    async def callback(part: ResultPart, _node: DummyNode) -> str:
        return part.expected_result

    results = await execute_tools_parallel(tool_calls, callback)  # type: ignore[arg-type]

    assert results == expected_results
