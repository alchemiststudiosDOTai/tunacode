"""tinyagent host-side turn control callbacks."""

from __future__ import annotations

from collections.abc import Callable

from tinyagent.agent_types import AgentContext, AgentMessage, AssistantMessage, ToolResultMessage

from tunacode.core.logging.manager import get_logger
from tunacode.core.types.state import SessionStateProtocol

from .agent_session_config import _coerce_max_iterations


def build_should_stop_after_turn(
    session: SessionStateProtocol,
) -> Callable[
    [AssistantMessage, list[ToolResultMessage], AgentContext, list[AgentMessage]],
    bool,
]:
    def _should_stop_after_turn(
        message: AssistantMessage,
        tool_results: list[ToolResultMessage],
        context: AgentContext,
        new_messages: list[AgentMessage],
    ) -> bool:
        _ = (message, tool_results, context, new_messages)
        runtime = session.runtime
        runtime.iteration_count += 1
        runtime.current_iteration = runtime.iteration_count
        max_iterations = _coerce_max_iterations(session)
        if runtime.iteration_count <= max_iterations:
            return False
        get_logger().warning(f"Max iterations exceeded ({max_iterations}); ending agent loop")
        return True

    return _should_stop_after_turn
