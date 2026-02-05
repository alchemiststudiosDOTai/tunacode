"""Coverage-focused tests for tool dispatch seams."""

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.messages import ToolCallPart

from tunacode.exceptions import UserAbortError

from tunacode.core.agents.agent_components.orchestrator import tool_dispatcher
from tunacode.core.agents.agent_components.response_state import ResponseState
from tunacode.core.session import StateManager
from tunacode.core.types import AgentState

# =============================================================================
# Test Constants
# =============================================================================


TOOL_NAME_MAX_LEN = 50
TOO_LONG_TOOL_NAME_LEN = TOOL_NAME_MAX_LEN + 1
LONG_TOOL_NAME_CHAR = "a"
SUSPICIOUS_TOOL_NAME = "bad<tool"
NORMAL_TOOL_NAME = "read_file"
WRITE_TOOL_NAME = "write_file"
GREP_TOOL_NAME = "grep"
GLOB_TOOL_NAME = "glob"
LIST_DIR_TOOL_NAME = "list_dir"
PART_KIND_TEXT = tool_dispatcher.PART_KIND_TEXT
PART_KIND_TOOL_CALL = tool_dispatcher.PART_KIND_TOOL_CALL
TOOL_CALL_ID = "call_dispatcher_1"
TOOL_CALL_ID_SECOND = "call_dispatcher_2"
EMPTY_TEXT = ""
NO_INDICATOR_TEXT = "just text"
USER_ABORT_MESSAGE = "stop"
TOOL_CALL_COUNT = tool_dispatcher.TOOL_BATCH_PREVIEW_COUNT + 1
RESPONSE_OUTPUT = "done"
CALLBACK_RETURN = None
RESULT_LABEL = "result"
EXPECTED_JOINER = tool_dispatcher.TOOL_NAME_JOINER
EXPECTED_SUFFIX = tool_dispatcher.TOOL_NAME_SUFFIX

TOOL_SEQUENCE = [
    NORMAL_TOOL_NAME,
    GREP_TOOL_NAME,
    GLOB_TOOL_NAME,
    LIST_DIR_TOOL_NAME,
]

READ_TOOL_CALL_TEXT = json.dumps(
    {"name": NORMAL_TOOL_NAME, "arguments": {}},
)
READ_TOOL_CALL_TAGGED = f"<tool_call>{READ_TOOL_CALL_TEXT}</tool_call>"
INVALID_TOOL_CALL_TAGGED = "<tool_call>{}</tool_call>"


# =============================================================================
# Helpers
# =============================================================================


@dataclass(frozen=True, slots=True)
class TextPart:
    part_kind: str
    content: str


@dataclass(frozen=True, slots=True)
class DummyPart:
    part_kind: str


@dataclass(frozen=True, slots=True)
class DummyResult:
    output: str | None


@dataclass(frozen=True, slots=True)
class DummyNode:
    result: DummyResult | None
    label: str = RESULT_LABEL


@pytest.fixture
def state_manager() -> StateManager:
    manager = StateManager()
    manager.session.runtime.tool_registry.clear()
    manager.session.runtime.batch_counter = 0
    return manager


def _make_response_state() -> ResponseState:
    response_state = ResponseState()
    response_state.transition_to(AgentState.ASSISTANT)
    return response_state


async def _capture_parallel_exec(
    tool_calls: list[tuple[Any, Any]],
    callback: Any,
    tool_failure_callback: Any | None = None,
) -> list[Any]:
    for part, task_node in tool_calls:
        await callback(part, task_node)
    return [CALLBACK_RETURN for _ in tool_calls]


# =============================================================================
# Tests
# =============================================================================


def test_is_suspicious_tool_name_flags_invalid_cases() -> None:
    long_tool_name = LONG_TOOL_NAME_CHAR * TOO_LONG_TOOL_NAME_LEN
    empty_tool_name = EMPTY_TEXT

    assert tool_dispatcher._is_suspicious_tool_name(empty_tool_name) is True
    assert tool_dispatcher._is_suspicious_tool_name(long_tool_name) is True
    assert tool_dispatcher._is_suspicious_tool_name(SUSPICIOUS_TOOL_NAME) is True
    assert tool_dispatcher._is_suspicious_tool_name(NORMAL_TOOL_NAME) is False


def test_has_tool_calls_detects_structured_parts() -> None:
    text_part = DummyPart(part_kind=PART_KIND_TEXT)
    tool_part = ToolCallPart(
        tool_name=NORMAL_TOOL_NAME,
        args={},
        tool_call_id=TOOL_CALL_ID,
    )

    assert tool_dispatcher.has_tool_calls([text_part]) is False
    assert tool_dispatcher.has_tool_calls([text_part, tool_part]) is True


@pytest.mark.asyncio
async def test_extract_fallback_skips_non_text_parts(state_manager: StateManager) -> None:
    parts = [
        DummyPart(part_kind=PART_KIND_TOOL_CALL),
        TextPart(part_kind=PART_KIND_TEXT, content=EMPTY_TEXT),
    ]

    results = await tool_dispatcher._collect_fallback_tool_calls(parts, state_manager)

    assert results == []


@pytest.mark.asyncio
async def test_extract_fallback_debug_no_indicator(state_manager: StateManager) -> None:
    state_manager.session.debug_mode = True
    parts = [TextPart(part_kind=PART_KIND_TEXT, content=NO_INDICATOR_TEXT)]

    results = await tool_dispatcher._collect_fallback_tool_calls(parts, state_manager)

    assert results == []


@pytest.mark.asyncio
async def test_extract_fallback_debug_with_diagnostics_success(
    state_manager: StateManager,
) -> None:
    state_manager.session.debug_mode = True
    parts = [TextPart(part_kind=PART_KIND_TEXT, content=READ_TOOL_CALL_TAGGED)]

    results = await tool_dispatcher._collect_fallback_tool_calls(parts, state_manager)

    assert len(results) == 1


@pytest.mark.asyncio
async def test_extract_fallback_debug_with_indicators_no_calls(
    state_manager: StateManager,
) -> None:
    state_manager.session.debug_mode = True
    parts = [TextPart(part_kind=PART_KIND_TEXT, content=INVALID_TOOL_CALL_TAGGED)]

    results = await tool_dispatcher._collect_fallback_tool_calls(parts, state_manager)

    assert results == []


@pytest.mark.asyncio
async def test_dispatch_debug_logging_and_skips_callbacks(
    state_manager: StateManager,
) -> None:
    state_manager.session.debug_mode = True
    parts = [
        ToolCallPart(
            tool_name=SUSPICIOUS_TOOL_NAME,
            args={},
            tool_call_id=TOOL_CALL_ID,
        ),
        ToolCallPart(
            tool_name=NORMAL_TOOL_NAME,
            args={},
            tool_call_id=TOOL_CALL_ID_SECOND,
        ),
    ]

    result = await tool_dispatcher.dispatch_tools(
        parts=parts,
        node=DummyNode(result=None),
        state_manager=state_manager,
        tool_callback=None,
        tool_start_callback=None,
    )

    assert result.has_tool_calls is True
    assert result.used_fallback is False
    tool_registry = state_manager.session.runtime.tool_registry
    assert len(tool_registry.list_calls()) == len(parts)


@pytest.mark.asyncio
async def test_dispatch_preview_suffix(
    state_manager: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    started_labels: list[str] = []

    def tool_start_callback(label: str) -> None:
        started_labels.append(label)

    parts = [
        ToolCallPart(tool_name=name, args={}, tool_call_id=f"{TOOL_CALL_ID}_{index}")
        for index, name in enumerate(TOOL_SEQUENCE)
    ]

    monkeypatch.setattr(
        "tunacode.core.agents.agent_components.tool_executor.execute_tools_parallel",
        _capture_parallel_exec,
    )

    await tool_dispatcher.dispatch_tools(
        parts=parts,
        node=DummyNode(result=None),
        state_manager=state_manager,
        tool_callback=AsyncMock(),
        tool_start_callback=tool_start_callback,
    )

    preview_names = TOOL_SEQUENCE[: tool_dispatcher.TOOL_BATCH_PREVIEW_COUNT]
    expected_label = EXPECTED_JOINER.join(preview_names) + EXPECTED_SUFFIX
    assert len(TOOL_SEQUENCE) == TOOL_CALL_COUNT
    assert started_labels[0] == expected_label


@pytest.mark.asyncio
async def test_dispatch_write_tool_start_and_user_abort(
    state_manager: StateManager,
) -> None:
    started_labels: list[str] = []

    def tool_start_callback(label: str) -> None:
        started_labels.append(label)

    tool_callback = AsyncMock(side_effect=UserAbortError(USER_ABORT_MESSAGE))
    parts = [
        ToolCallPart(
            tool_name=WRITE_TOOL_NAME,
            args={},
            tool_call_id=TOOL_CALL_ID,
        )
    ]

    with pytest.raises(UserAbortError):
        await tool_dispatcher.dispatch_tools(
            parts=parts,
            node=DummyNode(result=None),
            state_manager=state_manager,
            tool_callback=tool_callback,
            tool_start_callback=tool_start_callback,
        )

    assert started_labels == [WRITE_TOOL_NAME]


@pytest.mark.asyncio
async def test_process_node_sets_user_response_from_node_result(
    state_manager: StateManager,
) -> None:
    """User response detection moved from dispatch_tools to process_node orchestrator."""
    from tunacode.core.agents.agent_components.orchestrator.orchestrator import process_node

    response_state = _make_response_state()

    @dataclass(frozen=True, slots=True)
    class DummyModelResponse:
        parts: list[Any]
        usage: None = None

    @dataclass(frozen=True, slots=True)
    class DummyNodeWithResponse:
        result: DummyResult | None
        model_response: DummyModelResponse | None = None
        request: None = None
        thought: None = None

    model_response = DummyModelResponse(
        parts=[
            ToolCallPart(
                tool_name=WRITE_TOOL_NAME,
                args={},
                tool_call_id=TOOL_CALL_ID,
            )
        ],
    )
    node = DummyNodeWithResponse(
        result=DummyResult(output=RESPONSE_OUTPUT),
        model_response=model_response,
    )

    await process_node(
        node=node,
        tool_callback=AsyncMock(return_value=CALLBACK_RETURN),
        state_manager=state_manager,
        response_state=response_state,
    )

    assert response_state.has_user_response is True
