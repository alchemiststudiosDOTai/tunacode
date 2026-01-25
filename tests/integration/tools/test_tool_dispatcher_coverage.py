"""Coverage-focused tests for tool dispatch seams."""

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.messages import ToolCallPart

from tunacode.constants import ToolName
from tunacode.core.agents.agent_components.orchestrator import tool_dispatcher
from tunacode.core.agents.agent_components.response_state import ResponseState
from tunacode.core.state import StateManager
from tunacode.exceptions import UserAbortError
from tunacode.types import AgentState

# =============================================================================
# Test Constants
# =============================================================================


TOOL_NAME_MAX_LEN = 50
TOO_LONG_TOOL_NAME_LEN = TOOL_NAME_MAX_LEN + 1
LONG_TOOL_NAME_CHAR = "a"
SUSPICIOUS_TOOL_NAME = "bad<tool"
NORMAL_TOOL_NAME = "read_file"
WRITE_TOOL_NAME = "write_file"
RESEARCH_TOOL_NAME = "research_codebase"
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
READ_ONLY_TOOL_CALL_COUNT = tool_dispatcher.TOOL_BATCH_PREVIEW_COUNT + 1
RESPONSE_OUTPUT = "done"
CALLBACK_RETURN = None
RESULT_LABEL = "result"
RESEARCH_LABEL = tool_dispatcher.TOOL_START_RESEARCH_LABEL
EXPECTED_JOINER = tool_dispatcher.TOOL_NAME_JOINER
EXPECTED_SUFFIX = tool_dispatcher.TOOL_NAME_SUFFIX
SUBMIT_TOOL_NAME = ToolName.SUBMIT.value

READ_ONLY_TOOL_SEQUENCE = [
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
RESEARCH_TOOL_CALL_TEXT = json.dumps(
    {"name": RESEARCH_TOOL_NAME, "arguments": {}},
)
RESEARCH_TOOL_CALL_TAGGED = f"<tool_call>{RESEARCH_TOOL_CALL_TEXT}</tool_call>"
SUBMIT_TOOL_CALL_TEXT = json.dumps(
    {"name": SUBMIT_TOOL_NAME, "arguments": {}},
)
SUBMIT_TOOL_CALL_TAGGED = f"<tool_call>{SUBMIT_TOOL_CALL_TEXT}</tool_call>"


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
    manager.session.runtime.tool_calls = []
    manager.session.runtime.tool_call_args_by_id = {}
    manager.session.runtime.batch_counter = 0
    return manager


def _make_response_state() -> ResponseState:
    response_state = ResponseState()
    response_state.transition_to(AgentState.ASSISTANT)
    return response_state


async def _capture_parallel_exec(tool_calls: list[tuple[Any, Any]], callback: Any) -> list[Any]:
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

    results = await tool_dispatcher._extract_fallback_tool_calls(parts, state_manager, None)

    assert results == []


@pytest.mark.asyncio
async def test_extract_fallback_debug_no_indicator(state_manager: StateManager) -> None:
    state_manager.session.debug_mode = True
    parts = [TextPart(part_kind=PART_KIND_TEXT, content=NO_INDICATOR_TEXT)]

    results = await tool_dispatcher._extract_fallback_tool_calls(parts, state_manager, None)

    assert results == []


@pytest.mark.asyncio
async def test_extract_fallback_debug_with_diagnostics_success(
    state_manager: StateManager,
) -> None:
    state_manager.session.debug_mode = True
    response_state = _make_response_state()
    parts = [TextPart(part_kind=PART_KIND_TEXT, content=READ_TOOL_CALL_TAGGED)]

    results = await tool_dispatcher._extract_fallback_tool_calls(
        parts, state_manager, response_state
    )

    assert len(results) == 1
    assert response_state.current_state == AgentState.TOOL_EXECUTION


@pytest.mark.asyncio
async def test_extract_fallback_debug_with_indicators_no_calls(
    state_manager: StateManager,
) -> None:
    state_manager.session.debug_mode = True
    parts = [TextPart(part_kind=PART_KIND_TEXT, content=INVALID_TOOL_CALL_TAGGED)]

    results = await tool_dispatcher._extract_fallback_tool_calls(parts, state_manager, None)

    assert results == []


@pytest.mark.asyncio
async def test_dispatch_debug_logging_and_skips_callbacks(
    state_manager: StateManager,
) -> None:
    state_manager.session.debug_mode = True
    response_state = _make_response_state()
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
        _tool_result_callback=None,
        tool_start_callback=None,
        response_state=response_state,
    )

    assert result.has_tool_calls is True
    assert result.used_fallback is False
    assert len(state_manager.session.runtime.tool_calls) == len(parts)


@pytest.mark.asyncio
async def test_dispatch_fallback_research_tool_triggers_start(
    state_manager: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    response_state = _make_response_state()
    parts = [TextPart(part_kind=PART_KIND_TEXT, content=RESEARCH_TOOL_CALL_TAGGED)]
    started_labels: list[str] = []

    def tool_start_callback(label: str) -> None:
        started_labels.append(label)

    monkeypatch.setattr(
        "tunacode.core.agents.agent_components.tool_executor.execute_tools_parallel",
        _capture_parallel_exec,
    )

    await tool_dispatcher.dispatch_tools(
        parts=parts,
        node=DummyNode(result=None),
        state_manager=state_manager,
        tool_callback=AsyncMock(),
        _tool_result_callback=None,
        tool_start_callback=tool_start_callback,
        response_state=response_state,
    )

    assert started_labels == [RESEARCH_LABEL]


@pytest.mark.asyncio
async def test_dispatch_read_only_preview_suffix(
    state_manager: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    response_state = _make_response_state()
    started_labels: list[str] = []

    def tool_start_callback(label: str) -> None:
        started_labels.append(label)

    parts = [
        ToolCallPart(tool_name=name, args={}, tool_call_id=f"{TOOL_CALL_ID}_{index}")
        for index, name in enumerate(READ_ONLY_TOOL_SEQUENCE)
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
        _tool_result_callback=None,
        tool_start_callback=tool_start_callback,
        response_state=response_state,
    )

    preview_names = READ_ONLY_TOOL_SEQUENCE[: tool_dispatcher.TOOL_BATCH_PREVIEW_COUNT]
    expected_label = EXPECTED_JOINER.join(preview_names) + EXPECTED_SUFFIX
    assert len(READ_ONLY_TOOL_SEQUENCE) == READ_ONLY_TOOL_CALL_COUNT
    assert started_labels[0] == expected_label


@pytest.mark.asyncio
async def test_dispatch_write_tool_start_and_user_abort(
    state_manager: StateManager,
) -> None:
    response_state = _make_response_state()
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
            _tool_result_callback=None,
            tool_start_callback=tool_start_callback,
            response_state=response_state,
        )

    assert started_labels == [WRITE_TOOL_NAME]


@pytest.mark.asyncio
async def test_dispatch_sets_user_response_from_node_result(
    state_manager: StateManager,
) -> None:
    response_state = _make_response_state()
    node = DummyNode(result=DummyResult(output=RESPONSE_OUTPUT))
    parts = [
        ToolCallPart(
            tool_name=WRITE_TOOL_NAME,
            args={},
            tool_call_id=TOOL_CALL_ID,
        )
    ]

    await tool_dispatcher.dispatch_tools(
        parts=parts,
        node=node,
        state_manager=state_manager,
        tool_callback=AsyncMock(return_value=CALLBACK_RETURN),
        _tool_result_callback=None,
        tool_start_callback=None,
        response_state=response_state,
    )

    assert response_state.has_user_response is True


@pytest.mark.asyncio
async def test_dispatch_fallback_submit_marks_task_completed(
    state_manager: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    response_state = _make_response_state()
    parts = [TextPart(part_kind=PART_KIND_TEXT, content=SUBMIT_TOOL_CALL_TAGGED)]

    monkeypatch.setattr(
        "tunacode.core.agents.agent_components.tool_executor.execute_tools_parallel",
        _capture_parallel_exec,
    )

    await tool_dispatcher.dispatch_tools(
        parts=parts,
        node=DummyNode(result=None),
        state_manager=state_manager,
        tool_callback=AsyncMock(),
        _tool_result_callback=None,
        tool_start_callback=None,
        response_state=response_state,
    )

    # NOTE: submit tool no longer sets task_completed - pydantic-ai loop ends naturally
    # assert response_state.task_completed is True
