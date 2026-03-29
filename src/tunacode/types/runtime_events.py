"""Shared runtime event contract for TunaCode request execution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeAlias

from tinyagent.agent_types import (
    AgentMessage,
    AgentToolResult,
    AssistantMessageEvent,
    ToolResultMessage,
)

from tunacode.types.base import ToolArgs


@dataclass(slots=True)
class AgentStartRuntimeEvent:
    type: str = "agent_start"


@dataclass(slots=True)
class AgentEndRuntimeEvent:
    messages: list[AgentMessage] = field(default_factory=list)
    type: str = "agent_end"


@dataclass(slots=True)
class TurnStartRuntimeEvent:
    type: str = "turn_start"


@dataclass(slots=True)
class TurnEndRuntimeEvent:
    message: AgentMessage | None = None
    tool_results: list[ToolResultMessage] = field(default_factory=list)
    type: str = "turn_end"


@dataclass(slots=True)
class MessageStartRuntimeEvent:
    message: AgentMessage | None = None
    type: str = "message_start"


@dataclass(slots=True)
class MessageUpdateRuntimeEvent:
    message: AgentMessage | None = None
    assistant_message_event: AssistantMessageEvent | None = None
    type: str = "message_update"


@dataclass(slots=True)
class MessageEndRuntimeEvent:
    message: AgentMessage | None = None
    type: str = "message_end"


@dataclass(slots=True)
class ToolExecutionStartRuntimeEvent:
    tool_call_id: str
    tool_name: str
    args: ToolArgs
    type: str = "tool_execution_start"


@dataclass(slots=True)
class ToolExecutionUpdateRuntimeEvent:
    tool_call_id: str
    tool_name: str
    args: ToolArgs
    partial_result: AgentToolResult | None = None
    type: str = "tool_execution_update"


@dataclass(slots=True)
class ToolExecutionEndRuntimeEvent:
    tool_call_id: str
    tool_name: str
    args: ToolArgs
    result: AgentToolResult | None = None
    is_error: bool = False
    duration_ms: float | None = None
    type: str = "tool_execution_end"


@dataclass(slots=True)
class NoticeRuntimeEvent:
    notice: str
    type: str = "notice"


@dataclass(slots=True)
class CompactionStateChangedRuntimeEvent:
    active: bool
    type: str = "compaction_state_changed"


RuntimeEvent: TypeAlias = (
    AgentStartRuntimeEvent
    | AgentEndRuntimeEvent
    | TurnStartRuntimeEvent
    | TurnEndRuntimeEvent
    | MessageStartRuntimeEvent
    | MessageUpdateRuntimeEvent
    | MessageEndRuntimeEvent
    | ToolExecutionStartRuntimeEvent
    | ToolExecutionUpdateRuntimeEvent
    | ToolExecutionEndRuntimeEvent
    | NoticeRuntimeEvent
    | CompactionStateChangedRuntimeEvent
)

RuntimeEventSink: TypeAlias = Callable[[RuntimeEvent], Awaitable[None] | None]
