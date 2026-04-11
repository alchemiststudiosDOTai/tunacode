---
title: "agent_streaming.py research findings"
link: "agent-streaming-research"
type: research
ontological_relations:
  - relates_to: [[docs/modules/core/core.md]]
tags: [research, agent_streaming, core, agents]
uuid: "cf24ff24-9165-4a72-bec8-cd3ff3d11709"
created_at: "2026-04-11T07:14:33Z"
---

## Structure
- `src/tunacode/core/agents/agent_components/agent_streaming.py:57` defines `AgentStreamMixin`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:54` defines module constant `_MS_PER_S = 1000`.
- `src/tunacode/core/agents/main.py:37` imports `AgentStreamMixin` from `.agent_components.agent_streaming`.
- `src/tunacode/core/agents/main.py:50` defines `RequestOrchestrator(AgentStreamMixin)`.
- `src/tunacode/core/agents/main.py:140` calls `self._run_stream(...)` in normal request flow.
- `src/tunacode/core/agents/main.py:214` calls `self._run_stream(...)` in context-overflow retry flow.
- Directory context around the target file:
  - `src/tunacode/core/agents/main.py`
  - `src/tunacode/core/agents/helpers.py`
  - `src/tunacode/core/agents/agent_components/__init__.py`
  - `src/tunacode/core/agents/agent_components/agent_config.py`
  - `src/tunacode/core/agents/agent_components/agent_helpers.py`
  - `src/tunacode/core/agents/agent_components/agent_session_config.py`
  - `src/tunacode/core/agents/resume/sanitize.py`
  - `src/tunacode/core/agents/resume/sanitize_debug.py`

## Key Files
- `src/tunacode/core/agents/agent_components/agent_streaming.py:57` → `AgentStreamMixin` class.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:389` → `_run_stream(self, *, agent, max_iterations, baseline_message_count) -> Agent`.
- `src/tunacode/core/agents/helpers.py:36` → `_TinyAgentStreamState` and helper definitions imported by `agent_streaming.py`.
- `src/tunacode/core/agents/main.py:37` → import site for `AgentStreamMixin`.
- `src/tunacode/core/agents/main.py:50` → consumer class `RequestOrchestrator`.
- `src/tunacode/core/agents/__init__.py:5` → re-exports `process_request` from `main`; does not re-export `AgentStreamMixin`.
- `src/tunacode/ui/app.py:338` → imports `process_request` from `tunacode.core.agents.main`.
- `src/tunacode/ui/app.py:342` → executes `process_request` in `_process_request`.

## Patterns Found
- Event-dispatch pattern:
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:328` defines `_dispatch_stream_event(...) -> bool`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:338` dispatches `is_turn_end_event` to `_handle_stream_turn_end`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:346` dispatches `MessageUpdateEvent` to `_handle_stream_message_update`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:353` dispatches `is_message_end_event` to `_handle_stream_message_end`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:360` dispatches `is_tool_execution_start_event` to `_handle_stream_tool_execution_start`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:367` dispatches `ToolExecutionUpdateEvent` to `_handle_stream_tool_execution_update`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:374` dispatches `is_tool_execution_end_event` to `_handle_stream_tool_execution_end`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:381` dispatches `is_agent_end_event` to `_handle_stream_agent_end`.
- Stream-loop pattern:
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:421` iterates `agent.stream(self.message)`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:425` forwards each event to `_dispatch_stream_event`.
- Interrupted-cleanup pattern:
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:140` defines `_handle_interrupted_stream_cleanup(...)`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:154` calls `_persist_agent_messages`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:155` calls `_remove_in_flight_tool_registry_entries`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:156` calls `_append_interrupted_partial_message`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:436` calls `_handle_interrupted_stream_cleanup` from exception handling in `_run_stream`.
- Callback pattern:
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:240` may call `self.tool_start_callback`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:278` may call `self.tool_result_callback`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:307` may call `self.tool_result_callback`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:190` routes message updates into `_handle_message_update`.

## Dependencies
- Imports from `tinyagent.agent`:
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:10` imports `Agent`, `extract_text`.
- Imports from `tinyagent.agent_types`:
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:11` through `src/tunacode/core/agents/agent_components/agent_streaming.py:27` import event types and predicate helpers.
- Imports from TunaCode modules:
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:29` imports `AgentError` from `tunacode.exceptions`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:30` imports `estimate_message_tokens`, `estimate_messages_tokens` from `tunacode.utils.messaging`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:32` imports `log_usage_update` from `tunacode.core.debug.usage_trace`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:33` imports `LogManager`, `get_logger` from `tunacode.core.logging.manager`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:35` imports sibling package `agent_components` as `ac`.
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:36` through `src/tunacode/core/agents/agent_components/agent_streaming.py:42` import `_TinyAgentStreamState`, `canonicalize_tool_result`, `extract_tool_result_text`, `is_context_overflow_error`, and `parse_canonical_usage` from `..helpers`.
- TYPE_CHECKING-only imports:
  - `src/tunacode/core/agents/agent_components/agent_streaming.py:44` through `src/tunacode/core/agents/agent_components/agent_streaming.py:53` import `ModelName`, callback types, and `StateManagerProtocol`.
- Reverse dependencies:
  - `src/tunacode/core/agents/main.py:37` imports `AgentStreamMixin`.
  - `src/tunacode/core/agents/main.py:50` subclasses `AgentStreamMixin` via `RequestOrchestrator`.

## Symbol Index
- `src/tunacode/core/agents/agent_components/agent_streaming.py:54` `_MS_PER_S`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:57` `AgentStreamMixin`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:72` `_mark_tool_start_batch_state(self, state, *, tool_call_id)`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:80` `_clear_tool_batch_state_if_idle(self, state)`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:84` `_resolve_tool_duration_ms(self, state, *, tool_call_id)`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:95` `_persist_agent_messages(self, agent, baseline_message_count)`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:101` `_remove_in_flight_tool_registry_entries(self, logger)`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:116` `_append_interrupted_partial_message(self)`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:140` `_handle_interrupted_stream_cleanup(self, logger, *, agent=None, invalidate_cache=False)`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:164` `_handle_stream_turn_end(self, event_obj, *, agent, state, max_iterations, baseline_message_count) -> bool`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:181` `_handle_stream_message_update(self, event_obj, *, agent, state, baseline_message_count) -> bool`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:193` `_handle_stream_message_end(self, event_obj, *, agent, state, baseline_message_count) -> bool`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:218` `_handle_stream_tool_execution_start(self, event_obj, *, agent, state, baseline_message_count) -> bool`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:242` `_handle_stream_tool_execution_end(self, event_obj, *, agent, state, baseline_message_count) -> bool`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:287` `_handle_stream_tool_execution_update(self, event_obj, *, agent, state, baseline_message_count) -> bool`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:316` `_handle_stream_agent_end(self, event_obj, *, agent, state, baseline_message_count) -> bool`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:328` `_dispatch_stream_event(self, *, event, agent, state, max_iterations, baseline_message_count) -> bool`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:389` `_run_stream(self, *, agent, max_iterations, baseline_message_count) -> Agent`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:460` `_handle_message_update(self, event)`
