"""Helper writers for agent timing/debug NDJSON events."""

from __future__ import annotations

from tunacode.utils.agent_debug_log import write_agent_debug

from tunacode.core.types.state import StateManagerProtocol


def log_agent_init_cache_event(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    model: str,
    cache_hit: bool,
    registry_ms: float,
    skills_ms: float,
    full_build_ms: float,
) -> None:
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "H1,H4",
            "location": "agent_config.py:get_or_create_agent",
            "message": "agent_init_cache_hit" if cache_hit else "agent_init_cache_miss",
            "data": {
                "request_id": request_id,
                "cache_hit": cache_hit,
                "model": model,
                "registry_ms": round(registry_ms, 2),
                "skills_ms": round(skills_ms, 2),
                "full_build_ms": round(full_build_ms, 2),
            },
        },
    )


def log_pre_stream_phases(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    model: str,
    get_or_create_agent_ms: float,
    compaction_ms: float,
    replace_messages_ms: float,
    pre_stream_total_ms: float,
    hist_len_before_compact: int,
    compacted_history_len: int,
    user_message_chars: int,
) -> None:
    accounted_ms = get_or_create_agent_ms + compaction_ms + replace_messages_ms
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "H3,H5",
            "location": "main.py:_run_impl",
            "message": "pre_stream_phases_ms",
            "data": {
                "request_id": request_id,
                "model": model,
                "get_or_create_agent_ms": round(get_or_create_agent_ms, 2),
                "compaction_ms": round(compaction_ms, 2),
                "replace_messages_ms": round(replace_messages_ms, 2),
                "pre_stream_total_ms": round(pre_stream_total_ms, 2),
                "pre_stream_accounted_ms": round(accounted_ms, 2),
                "pre_stream_unaccounted_ms": round(pre_stream_total_ms - accounted_ms, 2),
                "hist_len_before_compact": hist_len_before_compact,
                "compacted_history_len": compacted_history_len,
                "user_message_chars": user_message_chars,
            },
        },
    )


def log_compaction_outcome(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    status: str,
    reason: str | None,
    msg_in: int,
    msg_out: int,
) -> None:
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "H2",
            "location": "main.py:_compact_history_for_request",
            "message": "compaction_outcome",
            "data": {
                "request_id": request_id,
                "status": status,
                "reason": reason,
                "msg_in": msg_in,
                "msg_out": msg_out,
            },
        },
    )


def log_turn_end(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    iteration: int,
    max_iterations: int,
    will_abort_max_iter: bool,
) -> None:
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "stream_turn",
            "location": "stream_events.py:_handle_stream_turn_end",
            "message": "turn_end",
            "data": {
                "request_id": request_id,
                "iteration": iteration,
                "max_iterations": max_iterations,
                "will_abort_max_iter": will_abort_max_iter,
            },
        },
    )


def log_assistant_message_end(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    usage_input: int,
    usage_output: int,
    usage_total_tokens: int,
) -> None:
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "stream_message_end",
            "location": "stream_events.py:_handle_stream_message_end",
            "message": "assistant_message_end",
            "data": {
                "request_id": request_id,
                "usage_input": usage_input,
                "usage_output": usage_output,
                "usage_total_tokens": usage_total_tokens,
            },
        },
    )


def log_tool_start(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    tool_name: str,
    tool_call_id: str,
    arg_keys: list[str],
) -> None:
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "stream_tool",
            "location": "stream_events.py:_handle_stream_tool_execution_start",
            "message": "tool_start",
            "data": {
                "request_id": request_id,
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "arg_keys": arg_keys,
            },
        },
    )


def log_tool_end(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    tool_name: str,
    tool_call_id: str,
    status: str,
    duration_ms: float | None,
    result_text_len: int,
) -> None:
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "stream_tool",
            "location": "stream_events.py:_handle_stream_tool_execution_end",
            "message": "tool_end",
            "data": {
                "request_id": request_id,
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "status": status,
                "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
                "result_text_len": result_text_len,
            },
        },
    )


def log_stream_begin(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    model: str,
    max_iterations: int,
    baseline_message_count: int,
    user_message_chars: int,
    thread_id: int,
) -> None:
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "stream_begin",
            "location": "stream_events.py:_run_stream",
            "message": "stream_begin",
            "data": {
                "request_id": request_id,
                "model": model,
                "max_iterations": max_iterations,
                "baseline_message_count": baseline_message_count,
                "user_message_chars": user_message_chars,
                "thread_id": thread_id,
            },
        },
    )


def log_stream_first_event(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    first_event_ms: float,
    first_event_name: str,
    model: str,
) -> None:
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "stream_first_event",
            "location": "stream_events.py:_run_stream",
            "message": "stream_first_event",
            "data": {
                "request_id": request_id,
                "first_event_ms": round(first_event_ms, 2),
                "first_event_name": first_event_name,
                "model": model,
            },
        },
    )


def log_stream_gap(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    gap_ms: float,
    after_event_name: str,
    event_index: int,
) -> None:
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "stream_gap",
            "location": "stream_events.py:_run_stream",
            "message": "stream_event_gap",
            "data": {
                "request_id": request_id,
                "gap_ms": round(gap_ms, 2),
                "after_event_name": after_event_name,
                "event_index": event_index,
            },
        },
    )


def log_stream_dispatch_slow(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    dispatch_ms: float,
    event_name: str,
    event_index: int,
) -> None:
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "stream_dispatch",
            "location": "stream_events.py:_run_stream",
            "message": "dispatch_slow",
            "data": {
                "request_id": request_id,
                "dispatch_ms": round(dispatch_ms, 2),
                "event_name": event_name,
                "event_index": event_index,
            },
        },
    )


def log_stream_end(
    state_manager: StateManagerProtocol,
    *,
    request_id: str,
    model: str,
    stream_total_ms: float,
    first_event_ms: float | None,
    event_count: int,
    text_delta_count: int,
    thinking_delta_count: int,
    agent_error: bool,
) -> None:
    write_agent_debug(
        state_manager,
        {
            "runId": "prefix",
            "hypothesisId": "stream_end",
            "location": "stream_events.py:_run_stream",
            "message": "stream_end",
            "data": {
                "request_id": request_id,
                "model": model,
                "stream_total_ms": round(stream_total_ms, 2),
                "first_event_ms": round(first_event_ms, 2) if first_event_ms is not None else None,
                "event_count": event_count,
                "text_delta_count": text_delta_count,
                "thinking_delta_count": thinking_delta_count,
                "agent_error": agent_error,
            },
        },
    )
