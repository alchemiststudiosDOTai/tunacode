"""Agent loop that works with AgentMessage throughout.

Transforms to Message[] only at the LLM call boundary.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeAlias, TypeVar, cast

from .agent_tool_execution import _extract_tool_calls, execute_tool_calls
from .agent_types import (
    AgentContext,
    AgentEndEvent,
    AgentEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentStartEvent,
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    EventStream,
    MaybeAwaitable,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    Model,
    SimpleStreamOptions,
    StreamFn,
    StreamResponse,
    ToolResultMessage,
    TurnEndEvent,
    TurnStartEvent,
)


async def stream_simple(
    model: Model,
    context: Context,
    options: SimpleStreamOptions,
) -> StreamResponse:
    """Placeholder stream function.

    Real implementations must be passed via AgentOptions.stream_fn / AgentLoopConfig.
    """

    raise NotImplementedError("stream_simple must be provided")


def create_agent_stream() -> EventStream:
    """Create an event stream for agent events."""

    def is_end_event(event: AgentEvent) -> bool:
        return hasattr(event, "type") and event.type == "agent_end"

    def get_result(event: AgentEvent) -> list[AgentMessage]:
        if hasattr(event, "type") and event.type == "agent_end" and hasattr(event, "messages"):
            return cast(list[AgentMessage], event.messages)
        return []

    return EventStream(is_end_event, get_result)


STREAM_UPDATE_EVENTS = {
    "text_start",
    "text_delta",
    "text_end",
    "thinking_start",
    "thinking_delta",
    "thinking_end",
    "tool_call_start",
    "tool_call_delta",
    "tool_call_end",
}


StreamEventHandler: TypeAlias = Callable[
    [AssistantMessageEvent], Awaitable[AssistantMessage | None]
]


@dataclass
class ResponseStreamState:
    partial_message: AssistantMessage | None = None
    added_partial: bool = False


T = TypeVar("T")


async def _maybe_await(value: MaybeAwaitable[T]) -> T:
    if isinstance(value, Awaitable):
        return await value
    return value


async def _build_llm_context(
    context: AgentContext,
    config: AgentLoopConfig,
    signal: asyncio.Event | None,
) -> Context:
    """Transform and convert messages, then build LLM context."""

    messages = context.messages
    if config.transform_context:
        messages = await config.transform_context(messages, signal)

    llm_messages = await _maybe_await(config.convert_to_llm(messages))

    return Context(
        system_prompt=context.system_prompt,
        messages=llm_messages,
        tools=context.tools,
    )


async def _resolve_api_key(config: AgentLoopConfig) -> str | None:
    """Resolve API key from config or key resolver."""

    if config.get_api_key:
        resolved = await _maybe_await(config.get_api_key(config.model.provider))
        if resolved:
            return resolved
    return config.api_key


def _create_stream_handlers(
    context: AgentContext,
    stream: EventStream,
    state: ResponseStreamState,
    response: StreamResponse,
) -> dict[str, StreamEventHandler]:
    """Create handlers for stream events."""

    async def handle_start(event: AssistantMessageEvent) -> AssistantMessage | None:
        partial_message = event.get("partial")
        if not partial_message:
            return None
        context.messages.append(partial_message)
        state.partial_message = partial_message
        state.added_partial = True
        stream.push(MessageStartEvent(message=partial_message))
        return None

    async def handle_update(event: AssistantMessageEvent) -> AssistantMessage | None:
        partial_message = event.get("partial")
        if not state.partial_message or partial_message is None:
            return None
        state.partial_message = partial_message
        context.messages[-1] = state.partial_message
        stream.push(
            MessageUpdateEvent(
                message=state.partial_message,
                assistant_message_event=event,
            )
        )
        return None

    async def handle_finish(event: AssistantMessageEvent) -> AssistantMessage | None:
        final_message = await response.result()
        if state.added_partial:
            context.messages[-1] = final_message
        else:
            context.messages.append(final_message)
        if not state.added_partial:
            stream.push(MessageStartEvent(message=final_message))
        stream.push(MessageEndEvent(message=final_message))
        return final_message

    handlers: dict[str, StreamEventHandler] = {
        "start": handle_start,
        "done": handle_finish,
        "error": handle_finish,
    }
    for event_type in STREAM_UPDATE_EVENTS:
        handlers[event_type] = handle_update

    return handlers


async def stream_assistant_response(
    context: AgentContext,
    config: AgentLoopConfig,
    signal: asyncio.Event | None,
    stream: EventStream,
    stream_fn: StreamFn | None = None,
) -> AssistantMessage:
    """Stream an assistant response from the LLM."""

    llm_context = await _build_llm_context(context, config, signal)
    resolved_api_key = await _resolve_api_key(config)

    options: SimpleStreamOptions = {
        "api_key": resolved_api_key,
        "signal": signal,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }

    stream_function: StreamFn = stream_fn or stream_simple
    response: StreamResponse = await stream_function(config.model, llm_context, options)

    state = ResponseStreamState()
    handlers = _create_stream_handlers(context, stream, state, response)

    async for event in response:
        event_type = event.get("type")
        if not event_type:
            continue
        handler = handlers.get(event_type)
        if not handler:
            continue
        update_message = await handler(event)
        if update_message:
            return update_message

    return await response.result()


@dataclass
class TurnProcessingResult:
    pending_messages: list[AgentMessage]
    has_more_tool_calls: bool
    first_turn: bool
    should_continue: bool


def _emit_pending_messages(
    pending_messages: list[AgentMessage],
    current_context: AgentContext,
    new_messages: list[AgentMessage],
    stream: EventStream,
) -> None:
    if not pending_messages:
        return
    for message in pending_messages:
        stream.push(MessageStartEvent(message=message))
        stream.push(MessageEndEvent(message=message))
        current_context.messages.append(message)
        new_messages.append(message)


async def _process_turn(
    current_context: AgentContext,
    new_messages: list[AgentMessage],
    pending_messages: list[AgentMessage],
    config: AgentLoopConfig,
    signal: asyncio.Event | None,
    stream: EventStream,
    first_turn: bool,
    stream_fn: StreamFn | None,
    get_steering_fn: Callable[[], Awaitable[list[AgentMessage]]] | None,
) -> TurnProcessingResult:
    if not first_turn:
        stream.push(TurnStartEvent())
    else:
        first_turn = False

    _emit_pending_messages(pending_messages, current_context, new_messages, stream)
    pending_messages = []

    message = await stream_assistant_response(
        current_context,
        config,
        signal,
        stream,
        stream_fn,
    )
    new_messages.append(message)

    stop_reason = message.get("stop_reason")
    if stop_reason in ("error", "aborted"):
        stream.push(TurnEndEvent(message=message, tool_results=[]))
        stream.push(AgentEndEvent(messages=new_messages))
        stream.end(new_messages)
        return TurnProcessingResult(
            pending_messages=[],
            has_more_tool_calls=False,
            first_turn=first_turn,
            should_continue=False,
        )

    tool_calls = _extract_tool_calls(message)
    has_more_tool_calls = len(tool_calls) > 0
    tool_results: list[ToolResultMessage] = []
    steering_after_tools: list[AgentMessage] | None = None

    if has_more_tool_calls:
        tool_execution = await execute_tool_calls(
            current_context.tools,
            message,
            signal,
            stream,
            config.get_steering_messages,
        )
        tool_results.extend(tool_execution["tool_results"])
        steering_after_tools = tool_execution.get("steering_messages")

        for result in tool_results:
            current_context.messages.append(result)
            new_messages.append(result)

    stream.push(TurnEndEvent(message=message, tool_results=tool_results))

    pending_messages = steering_after_tools or (await get_steering_fn() if get_steering_fn else [])

    return TurnProcessingResult(
        pending_messages=pending_messages,
        has_more_tool_calls=has_more_tool_calls,
        first_turn=first_turn,
        should_continue=True,
    )


async def run_loop(
    current_context: AgentContext,
    new_messages: list[AgentMessage],
    config: AgentLoopConfig,
    signal: asyncio.Event | None,
    stream: EventStream,
    stream_fn: StreamFn | None = None,
) -> None:
    """Main loop logic shared by agent_loop and agent_loop_continue."""

    first_turn = True

    # Check for steering messages at start (user may have typed while waiting)
    get_steering_fn = config.get_steering_messages
    pending_messages: list[AgentMessage] = await get_steering_fn() if get_steering_fn else []

    # Outer loop: continues when queued follow-up messages arrive after agent would stop
    while True:
        has_more_tool_calls = True

        # Inner loop: process tool calls and steering messages
        while has_more_tool_calls or pending_messages:
            turn_result = await _process_turn(
                current_context,
                new_messages,
                pending_messages,
                config,
                signal,
                stream,
                first_turn,
                stream_fn,
                get_steering_fn,
            )
            if not turn_result.should_continue:
                return

            pending_messages = turn_result.pending_messages
            has_more_tool_calls = turn_result.has_more_tool_calls
            first_turn = turn_result.first_turn

        # Agent would stop here. Check for follow-up messages.
        get_follow_up_fn = config.get_follow_up_messages
        follow_up_messages = await get_follow_up_fn() if get_follow_up_fn else []
        if follow_up_messages:
            # Set as pending so inner loop processes them
            pending_messages = follow_up_messages
            continue

        break

    stream.push(AgentEndEvent(messages=new_messages))
    stream.end(new_messages)


def agent_loop(
    prompts: list[AgentMessage],
    context: AgentContext,
    config: AgentLoopConfig,
    signal: asyncio.Event | None = None,
    stream_fn: StreamFn | None = None,
) -> EventStream:
    """Start an agent loop with one or more new prompt messages."""

    stream = create_agent_stream()

    async def run() -> None:
        new_messages: list[AgentMessage] = list(prompts)
        current_context = AgentContext(
            system_prompt=context.system_prompt,
            messages=list(context.messages) + list(prompts),
            tools=context.tools,
        )

        stream.push(AgentStartEvent())
        stream.push(TurnStartEvent())
        for prompt in prompts:
            stream.push(MessageStartEvent(message=prompt))
            stream.push(MessageEndEvent(message=prompt))

        await run_loop(current_context, new_messages, config, signal, stream, stream_fn)

    asyncio.create_task(run())

    return stream


def agent_loop_continue(
    context: AgentContext,
    config: AgentLoopConfig,
    signal: asyncio.Event | None = None,
    stream_fn: StreamFn | None = None,
) -> EventStream:
    """Continue an agent loop from the current context without adding a new message.

    Used for retries - context already has a user message or tool results.

    Important: the last message in context must convert to a `user` or `tool_result`
    message via `convert_to_llm`.
    """

    if len(context.messages) == 0:
        raise ValueError("Cannot continue: no messages in context")

    last_message = context.messages[-1]
    last_role = last_message.get("role")
    if last_role == "assistant":
        raise ValueError("Cannot continue from message role: assistant")

    stream = create_agent_stream()

    async def run() -> None:
        new_messages: list[AgentMessage] = []
        current_context = AgentContext(
            system_prompt=context.system_prompt,
            messages=list(context.messages),
            tools=context.tools,
        )

        stream.push(AgentStartEvent())
        stream.push(TurnStartEvent())

        await run_loop(current_context, new_messages, config, signal, stream, stream_fn)

    asyncio.create_task(run())

    return stream
