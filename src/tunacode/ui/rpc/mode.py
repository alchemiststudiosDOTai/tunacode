"""CLI entry for TunaCode RPC mode."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from tinyagent.agent_types import (
    AgentToolResult,
    AssistantMessage,
    AssistantMessageEvent,
    TextContent,
    ToolResultMessage,
    UserMessage,
)

from tunacode.types.runtime_events import (
    AgentEndRuntimeEvent,
    AgentStartRuntimeEvent,
    MessageEndRuntimeEvent,
    MessageStartRuntimeEvent,
    MessageUpdateRuntimeEvent,
    ToolExecutionEndRuntimeEvent,
    ToolExecutionStartRuntimeEvent,
    ToolExecutionUpdateRuntimeEvent,
    TurnEndRuntimeEvent,
    TurnStartRuntimeEvent,
)

from tunacode.core.session import StateManager

from tunacode.ui.rpc.protocol import RpcProtocolError, error_response, parse_command
from tunacode.ui.rpc.session import RpcSession
from tunacode.ui.rpc.transport import JsonRpcTransport

RPC_TEST_MODE_ENV_VAR = "TUNACODE_RPC_TEST_MODE"


async def run_rpc_mode(
    *,
    state_manager: StateManager,
    transport: JsonRpcTransport | None = None,
) -> None:
    """Run the RPC command loop until stdin EOF."""
    resolved_transport = JsonRpcTransport() if transport is None else transport
    request_runner = build_rpc_request_runner()
    session = RpcSession(
        state_manager=state_manager,
        transport=resolved_transport,
        request_runner=request_runner,
    )
    try:
        while True:
            try:
                payload = await resolved_transport.read_payload()
            except Exception as exc:
                await resolved_transport.write(
                    error_response(
                        RpcProtocolError(
                            code="invalid_json",
                            message=f"Invalid JSON payload: {exc}",
                        )
                    )
                )
                continue

            if payload is None:
                break

            try:
                command = parse_command(payload)
                response = await session.handle_command(command)
            except RpcProtocolError as exc:
                response = error_response(exc)

            await resolved_transport.write(response)
    finally:
        await session.close()


def validate_rpc_cwd(cwd: str | None) -> Path | None:
    """Validate the CLI --cwd option for RPC mode."""
    if cwd is None:
        return None

    path = Path(cwd).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Working directory does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Working directory is not a directory: {path}")
    return path


def apply_rpc_cwd(cwd: Path | None) -> None:
    """Change the process working directory for RPC mode when requested."""
    if cwd is None:
        return
    os.chdir(cwd)


def build_rpc_request_runner() -> Any:
    if os.environ.get(RPC_TEST_MODE_ENV_VAR):
        return _run_test_request
    from tunacode.core.agents.main import process_request

    return process_request


async def _run_test_request(
    *,
    message: str,
    state_manager: StateManager,
    runtime_event_sink: Any,
    **_: object,
) -> None:
    user_message = UserMessage(content=[TextContent(text=message)])
    await runtime_event_sink(AgentStartRuntimeEvent())
    await runtime_event_sink(TurnStartRuntimeEvent())
    await runtime_event_sink(MessageStartRuntimeEvent(message=user_message))
    await runtime_event_sink(MessageEndRuntimeEvent(message=user_message))

    if message == "slow":
        await asyncio.sleep(0.2)

    if message == "tool":
        tool_result = AgentToolResult(content=[TextContent(text="/tmp")], details={})
        await runtime_event_sink(
            ToolExecutionStartRuntimeEvent(
                tool_call_id="call_1",
                tool_name="bash",
                args={"command": "pwd"},
            )
        )
        await asyncio.sleep(0.05)
        await runtime_event_sink(
            ToolExecutionUpdateRuntimeEvent(
                tool_call_id="call_1",
                tool_name="bash",
                args={"command": "pwd"},
                partial_result=tool_result,
            )
        )
        await asyncio.sleep(0.05)
        await runtime_event_sink(
            ToolExecutionEndRuntimeEvent(
                tool_call_id="call_1",
                tool_name="bash",
                args={"command": "pwd"},
                result=tool_result,
                is_error=False,
                duration_ms=100.0,
            )
        )
        tool_message = ToolResultMessage(
            tool_call_id="call_1",
            tool_name="bash",
            content=[TextContent(text="/tmp")],
        )
        response_text = "tool complete"
        assistant_message = AssistantMessage(
            content=[TextContent(text=response_text)],
            stop_reason="complete",
        )
        state_manager.session.conversation.messages.extend(
            [user_message, tool_message, assistant_message]
        )
        await runtime_event_sink(MessageStartRuntimeEvent(message=assistant_message))
        await runtime_event_sink(
            MessageUpdateRuntimeEvent(
                message=assistant_message,
                assistant_message_event=AssistantMessageEvent(
                    type="text_delta",
                    delta=response_text,
                ),
            )
        )
        await runtime_event_sink(MessageEndRuntimeEvent(message=assistant_message))
        await runtime_event_sink(
            TurnEndRuntimeEvent(message=assistant_message, tool_results=[tool_message])
        )
        await runtime_event_sink(
            AgentEndRuntimeEvent(messages=[user_message, tool_message, assistant_message])
        )
        return

    response_text = f"echo:{message}"
    assistant_message = AssistantMessage(
        content=[TextContent(text=response_text)],
        stop_reason="complete",
    )
    await runtime_event_sink(MessageStartRuntimeEvent(message=assistant_message))
    for chunk in ["echo:", message]:
        await asyncio.sleep(0.05)
        await runtime_event_sink(
            MessageUpdateRuntimeEvent(
                message=assistant_message,
                assistant_message_event=AssistantMessageEvent(
                    type="text_delta",
                    delta=chunk,
                ),
            ),
        )
    if message == "slow":
        await asyncio.sleep(5)
    await runtime_event_sink(MessageEndRuntimeEvent(message=assistant_message))
    await runtime_event_sink(TurnEndRuntimeEvent(message=assistant_message, tool_results=[]))
    state_manager.session.conversation.messages.extend([user_message, assistant_message])
    await runtime_event_sink(AgentEndRuntimeEvent(messages=[user_message, assistant_message]))
