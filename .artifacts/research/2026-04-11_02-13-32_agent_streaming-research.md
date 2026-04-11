---
title: "agent_streaming.py research findings"
link: "agent-streaming-research"
type: research
ontological_relations:
  - relates_to: [[agent_main]]
tags: [research, agent_streaming]
uuid: "E81095E1-A74C-4FEE-9A56-A0F717939EA1"
created_at: "2026-04-11T07:13:34Z"
---

## Structure
- File belongs to `src/tunacode/core/agents/agent_components/agent_streaming.py`.
- File purpose: streaming event loop mixin and event-handler dispatch for tinyagent orchestrator flow.
- Contains one concrete class and one module constant.

## Key Files
- `src/tunacode/core/agents/agent_components/agent_streaming.py:54` defines `_MS_PER_S`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:57` defines class `AgentStreamMixin`.
- `src/tunacode/core/agents/main.py:50` defines `RequestOrchestrator` inheriting `AgentStreamMixin`.
- `src/tunacode/core/agents/main.py:140` and `src/tunacode/core/agents/main.py:214` call `self._run_stream(...)`.

## Top-level symbols
- Class `AgentStreamMixin` and constants are at module scope in `src/tunacode/core/agents/agent_streaming.py:57-57` and `54-54`.
- Methods in `AgentStreamMixin`:
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:72` `_mark_tool_start_batch_state(self, state, *, tool_call_id)`
  - `src/tunacode/core/agents/agent_streaming.py:80` `_clear_tool_batch_state_if_idle(self, state)`
  - `src/tunacode/core/agents/agent_streaming.py:84` `_resolve_tool_duration_ms(self, state, *, tool_call_id) -> float | None`
  - `src/tunacode/core/agents/agent_streaming.py:95` `_persist_agent_messages(self, agent, baseline_message_count)`
  - `src/tunacode/core/agents/agent_streaming.py:101` `_remove_in_flight_tool_registry_entries(self, logger)`
  - `src/tunacode/core/agents/agent_streaming.py:116` `_append_interrupted_partial_message(self)`
  - `src/tunacode/core/agents/agent_streaming.py:140` `_handle_interrupted_stream_cleanup(self, logger, *, agent=None, invalidate_cache=False)`
  - `src/tunacode/core/agents/agent_streaming.py:164` `_handle_stream_turn_end(self, event_obj, *, agent, state, max_iterations, baseline_message_count) -> bool`
  - `src/tunacode/core/agents/agent_streaming.py:181` `_handle_stream_message_update(self, event_obj, *, agent, state, baseline_message_count) -> bool`
  - `src/tunacode/core/agents/agent_streaming.py:193` `_handle_stream_message_end(self, event_obj, *, agent, state, baseline_message_count) -> bool`
  - `src/tunacode/core/agents/agent_streaming.py:218` `_handle_stream_tool_execution_start(self, event_obj, *, agent, state, baseline_message_count) -> bool`
  - `src/tunacode/core/agents/agent_streaming.py:242` `_handle_stream_tool_execution_end(self, event_obj, *, agent, state, baseline_message_count) -> bool`
  - `src/tunacode/core/agents/agent_streaming.py:287` `_handle_stream_tool_execution_update(self, event_obj, *, agent, state, baseline_message_count) -> bool`
  - `src/tunacode/core/agents/agent_streaming.py:316` `_handle_stream_agent_end(self, event_obj, *, agent, state, baseline_message_count) -> bool`
  - `src/tunacode/core/agents/agent_streaming.py:328` `_dispatch_stream_event(self, *, event, agent, state, max_iterations, baseline_message_count) -> bool`
  - `src/tunacode/core/agents/agent_streaming.py:389` `_run_stream(self, *, agent, max_iterations, baseline_message_count) -> Agent`
  - `src/tunacode/core/agents/agent_streaming.py:460` `_handle_message_update(self, event)`

## Internal call flow
- `_run_stream` starts at `389-458`:
  - initializes `_TinyAgentStreamState` (`406-412`) and sets `self._active_stream_state` (`413`).
  - iterates `async for event in agent.stream(self.message)` (`421`).
  - dispatches each event through `_dispatch_stream_event` (`425-431`).
  - breaks when handler returns `True` (`432-433`).
  - on success sets `stream_completed=True` (`434`) and clears `self._active_stream_state` in finally (`443-445`).
  - on `CancelledError` or `Exception`, calls `_handle_interrupted_stream_cleanup` (`436-440`) and re-raises.
  - post-loop, computes duration logs and raises `AgentError` if `_agent_error_text(agent)` returns non-context-overflow text (`454-456`).

- `_dispatch_stream_event` at `328-387` branches by event type and delegates:
  - `is_turn_end_event(event)` -> `_handle_stream_turn_end` (`337-344`)
  - `isinstance(event, MessageUpdateEvent)` -> `_handle_stream_message_update` (`345-351`)
  - `is_message_end_event(event)` -> `_handle_stream_message_end` (`352-358`)
  - `is_tool_execution_start_event(event)` -> `_handle_stream_tool_execution_start` (`359-365`)
  - `isinstance(event, ToolExecutionUpdateEvent)` -> `_handle_stream_tool_execution_update` (`366-372`)
  - `is_tool_execution_end_event(event)` -> `_handle_stream_tool_execution_end` (`373-379`)
  - `is_agent_end_event(event)` -> `_handle_stream_agent_end` (`380-386`)

- `_handle_stream_message_end` (`193-216`) updates `state.last_assistant_message`, parses usage via `parse_canonical_usage`, updates `session.usage`, then calls `log_usage_update` (`209-215`).
- `_handle_stream_tool_execution_start` (`218-240`) stores start time in `state.tool_start_times`, updates batch state (`_mark_tool_start_batch_state`), registers and starts tool call in `state.runtime.tool_registry`, then calls `self.tool_start_callback` when present.
- `_handle_stream_tool_execution_update` (`287-314`) resolves callback args from event or tool registry, then calls `self.tool_result_callback` with status `"running"`.
- `_handle_stream_tool_execution_end` (`242-285`) computes `duration_ms` via `_resolve_tool_duration_ms`, builds canonical result and text, updates tool registry `fail/complete`, updates active/batch sets, and calls `self.tool_result_callback` with status `"completed"` or `"failed"`.
- `_handle_stream_turn_end` (`164-180`) increments runtime iteration counters and aborts plus raises `RuntimeError` when `iteration_count > max_iterations`.
- `_handle_message_update` (`460-476`) appends text deltas to `session._debug_raw_stream_accum` for `text_delta` and invokes `streaming_callback`; invokes `thinking_callback` for `thinking_delta`.
- `_handle_interrupted_stream_cleanup` (`140-163`) optionally persists messages via `_persist_agent_messages`, removes in-flight tool registry entries, appends interrupted partial message, clears `self._active_stream_state`, and conditionally invalidates cache using `ac.invalidate_agent_cache`.

## Dependency relationships
- Imports from tinyagent in module scope:
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:10` imports `Agent`, `extract_text`.
  - `src/tunacode/core/agents/agent_streaming.py:11-27` imports event model types and predicate helpers from `tinyagent.agent_types`.
- Imports from tunacode:
  - `AgentError` from `tunacode.exceptions` (`29`).
  - token estimation helpers from `tunacode.utils.messaging` (`30`).
  - `log_usage_update` from `tunacode.core.debug.usage_trace` (`32`).
  - `LogManager`, `get_logger` from `tunacode.core.logging.manager` (`33`).
  - module alias `ac` from `..` (`35`) and helper functions from `..helpers` (`36-42`).
- Internal references:
  - `ac.invalidate_agent_cache` invoked in `_handle_interrupted_stream_cleanup` (`161-162`).
  - `self.state_manager`, `self._active_stream_state`, and callback attributes are methods on mixin consumers.
- Reverse dependency:
  - `src/tunacode/core/agents/main.py:37` imports `AgentStreamMixin`.
  - `src/tunacode/core/agents/main.py:50` subclasses it in `RequestOrchestrator`.
  - `src/tunacode/core/agents/main.py:140` and `src/tunacode/core/agents/main.py:214` call `self._run_stream(...)`.
