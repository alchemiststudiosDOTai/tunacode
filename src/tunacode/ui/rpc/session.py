"""Long-lived RPC session for TunaCode JSONL execution."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

from tunacode.types import ModelName
from tunacode.types.runtime_events import AgentEndRuntimeEvent, MessageEndRuntimeEvent, RuntimeEvent

from tunacode.core.agents.agent_components.agent_config import invalidate_agent_cache
from tunacode.core.agents.main import process_request
from tunacode.core.compaction.controller import (
    apply_compaction_messages,
    get_or_create_compaction_controller,
)
from tunacode.core.compaction.types import (
    COMPACTION_STATUS_COMPACTED,
    COMPACTION_STATUS_FAILED,
)
from tunacode.core.session import StateManager
from tunacode.core.ui_api.configuration import get_model_context_window
from tunacode.core.ui_api.messaging import estimate_messages_tokens

from tunacode.ui.rpc.adapter import runtime_event_to_wire, serialize_messages
from tunacode.ui.rpc.protocol import (
    RPC_CODE_BUSY,
    RPC_CODE_NOT_STREAMING,
    AbortCommand,
    CompactCommand,
    GetMessagesCommand,
    GetStateCommand,
    PromptCommand,
    RpcCommand,
    RpcProtocolError,
    SetModelCommand,
    success_response,
)
from tunacode.ui.rpc.transport import JsonRpcTransport
from tunacode.ui.session_metadata import initialize_session_metadata


class RpcSession:
    """Own the session state and active request lifecycle for RPC mode."""

    def __init__(
        self,
        *,
        state_manager: StateManager,
        transport: JsonRpcTransport,
        request_runner: Callable[..., Awaitable[object]] = process_request,
    ) -> None:
        self._state_manager = state_manager
        self._transport = transport
        self._request_runner = request_runner
        self._active_request_task: asyncio.Task[None] | None = None
        self._request_cleanup_tasks: set[asyncio.Task[None]] = set()
        self._is_streaming = False
        self._is_compacting = False
        self._pending_message_count = 0
        initialize_session_metadata(self._state_manager)

    @property
    def state_manager(self) -> StateManager:
        return self._state_manager

    async def handle_command(self, command: RpcCommand) -> dict[str, Any]:
        """Dispatch one parsed RPC command."""
        if isinstance(command, PromptCommand):
            return await self._handle_prompt(command)
        if isinstance(command, AbortCommand):
            return await self._handle_abort(command)
        if isinstance(command, GetStateCommand):
            return success_response(command, **self._state_payload())
        if isinstance(command, GetMessagesCommand):
            return success_response(
                command,
                messages=serialize_messages(self._state_manager.session.conversation.messages),
            )
        if isinstance(command, SetModelCommand):
            return await self._handle_set_model(command)
        if isinstance(command, CompactCommand):
            return await self._handle_compact(command)
        raise RpcProtocolError(
            code="invalid_command",
            message="Unsupported command.",
            command=command.command,
            request_id=command.request_id,
        )

    async def close(self) -> None:
        """Cancel any active work and wait for cleanup to finish."""
        active_task = self._active_request_task
        if active_task is not None:
            active_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await active_task
        if self._request_cleanup_tasks:
            await asyncio.gather(*self._request_cleanup_tasks, return_exceptions=True)

    async def _handle_prompt(self, command: PromptCommand) -> dict[str, Any]:
        if self._is_streaming:
            raise RpcProtocolError(
                code=RPC_CODE_BUSY,
                message="Cannot start a new prompt while another request is active.",
                command=command.command,
                request_id=command.request_id,
            )

        self._pending_message_count = 0
        self._is_streaming = True
        task = asyncio.create_task(self._run_prompt(command.prompt), name="rpc_prompt")
        self._active_request_task = task
        task.add_done_callback(self._schedule_request_cleanup)
        return success_response(command)

    async def _handle_abort(self, command: AbortCommand) -> dict[str, Any]:
        active_task = self._active_request_task
        if active_task is None or active_task.done():
            raise RpcProtocolError(
                code=RPC_CODE_NOT_STREAMING,
                message="No active request to abort.",
                command=command.command,
                request_id=command.request_id,
            )

        active_task.cancel()
        return success_response(command)

    async def _handle_set_model(self, command: SetModelCommand) -> dict[str, Any]:
        if self._is_streaming:
            raise RpcProtocolError(
                code=RPC_CODE_BUSY,
                message="Cannot change models while a request is active.",
                command=command.command,
                request_id=command.request_id,
            )

        session = self._state_manager.session
        old_model = session.current_model
        session.current_model = command.model
        session.conversation.max_tokens = get_model_context_window(command.model)
        invalidate_agent_cache(old_model, self._state_manager)
        invalidate_agent_cache(command.model, self._state_manager)
        await self._state_manager.save_session()
        return success_response(command, model=command.model)

    async def _handle_compact(self, command: CompactCommand) -> dict[str, Any]:
        if self._is_streaming:
            raise RpcProtocolError(
                code=RPC_CODE_BUSY,
                message="Cannot compact while a request is active.",
                command=command.command,
                request_id=command.request_id,
            )

        session = self._state_manager.session
        history = list(session.conversation.messages)
        if not history:
            return success_response(
                command,
                status="skipped",
                reason="no_messages",
                removedCount=0,
                reclaimedTokens=0,
            )

        controller = get_or_create_compaction_controller(self._state_manager)
        controller.reset_request_state()
        controller.set_status_callback(self._set_compacting)
        tokens_before = estimate_messages_tokens(history)
        try:
            self._set_compacting(True)
            outcome = await controller.force_compact(
                history,
                max_tokens=session.conversation.max_tokens,
                signal=None,
            )
        finally:
            controller.set_status_callback(None)
            self._set_compacting(False)

        compacted_history = apply_compaction_messages(self._state_manager, outcome.messages)
        await self._state_manager.save_session()

        if outcome.status == COMPACTION_STATUS_FAILED:
            return success_response(
                command,
                status="failed",
                reason=outcome.reason,
                detail=outcome.detail,
                removedCount=0,
                reclaimedTokens=0,
            )

        if outcome.status != COMPACTION_STATUS_COMPACTED:
            return success_response(
                command,
                status="skipped",
                reason=outcome.reason,
                removedCount=0,
                reclaimedTokens=0,
            )

        tokens_after = estimate_messages_tokens(compacted_history)
        return success_response(
            command,
            status="compacted",
            reason=outcome.reason,
            removedCount=max(0, len(history) - len(compacted_history)),
            reclaimedTokens=max(0, tokens_before - tokens_after),
        )

    async def _run_prompt(self, prompt: str) -> None:
        try:
            await self._request_runner(
                message=prompt,
                model=ModelName(self._state_manager.session.current_model),
                state_manager=self._state_manager,
                runtime_event_sink=self._handle_runtime_event,
                streaming_callback=None,
                thinking_callback=None,
                tool_result_callback=None,
                tool_start_callback=None,
                notice_callback=None,
                compaction_status_callback=None,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._transport.write_diagnostic(f"RPC prompt failed: {exc}")
        finally:
            self._is_streaming = False

    async def _handle_runtime_event(self, event: RuntimeEvent) -> None:
        if isinstance(event, MessageEndRuntimeEvent) and event.message is not None:
            self._pending_message_count += 1
        if isinstance(event, AgentEndRuntimeEvent):
            self._pending_message_count = len(event.messages)

        wire_event = runtime_event_to_wire(event)
        if wire_event is not None:
            await self._transport.write(wire_event)

    def _schedule_request_cleanup(self, task: asyncio.Task[None]) -> None:
        cleanup_task = asyncio.create_task(self._finalize_request(task), name="rpc_prompt_cleanup")
        self._request_cleanup_tasks.add(cleanup_task)
        cleanup_task.add_done_callback(self._request_cleanup_tasks.discard)

    async def _finalize_request(self, task: asyncio.Task[None]) -> None:
        try:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        finally:
            self._active_request_task = None
            self._pending_message_count = 0
            await self._state_manager.save_session()

    def _state_payload(self) -> dict[str, Any]:
        session = self._state_manager.session
        return {
            "sessionId": session.session_id,
            "currentModel": session.current_model,
            "isStreaming": self._is_streaming,
            "isCompacting": self._is_compacting,
            "messageCount": len(session.conversation.messages),
            "pendingMessageCount": self._pending_message_count,
        }

    def _set_compacting(self, active: bool) -> None:
        self._is_compacting = active
