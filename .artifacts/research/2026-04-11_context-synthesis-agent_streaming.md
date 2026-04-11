---
title: "agent_streaming.py context-synthesis findings"
link: "agent_streaming-context-synthesis"
type: research
ontological_relations:
  - relates_to: [[agent_components-architecture]]
tags: [research, context-synthesis, agent_streaming]
uuid: "agent-streaming-context-synthesis"
created_at: "2026-04-11T00:00:00Z"
---

## Imports From `src/tunacode/core/agents/agent_components/agent_streaming.py`
- `src/tunacode/core/agents/agent_components/agent_streaming.py:10` imports `Agent`, `extract_text` from `tinyagent.agent`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:11-27` imports event/message types and predicate helpers from `tinyagent.agent_types`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:29` imports `AgentError` from `tunacode.exceptions`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:30` imports `estimate_message_tokens`, `estimate_messages_tokens` from `tunacode.utils.messaging`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:32` imports `log_usage_update` from `tunacode.core.debug.usage_trace`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:33` imports `LogManager`, `get_logger` from `tunacode.core.logging.manager`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:35` imports sibling package alias `agent_components` as `ac` from `tunacode.core.agents`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:36-42` imports helper symbols from `..helpers`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:44-53` `TYPE_CHECKING` block imports callback/type aliases from `tunacode.types` and `StateManagerProtocol` from `tunacode.core.types.state`.

## What imports this module
- `src/tunacode/core/agents/main.py:37` imports `AgentStreamMixin` from `.agent_components.agent_streaming`.
- `src/tunacode/core/agents/main.py:50` defines `RequestOrchestrator(AgentStreamMixin)`.

## Direct symbol usage of `AgentStreamMixin` in codebase
- `src/tunacode/core/agents/main.py:140` calls `await self._run_stream(...)` (method provided by `AgentStreamMixin`).
- `src/tunacode/core/agents/main.py:214` calls `await self._run_stream(...)` inside context overflow retry flow (method provided by `AgentStreamMixin`).
- `src/tunacode/core/agents/main.py:200-201` consumes `is_context_overflow_error` in retry logic, where `_run_stream` may raise `AgentError` after stream completion.

## Internal export surface in this module
- `src/tunacode/core/agents/agent_components/agent_streaming.py:57` defines `class AgentStreamMixin`.
- No other top-level class/function/classmethod exports are defined in this module besides `AgentStreamMixin` and private/protected methods.

## Internal call graph of key handlers
- `src/tunacode/core/agents/agent_components/agent_streaming.py:389-459` `_run_stream` iterates `async for event in agent.stream(self.message)` and routes each event to `_dispatch_stream_event`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:328-387` `_dispatch_stream_event` dispatches event types to:
  - `_handle_stream_turn_end` (`src/tunacode/core/agents/agent_components/agent_streaming.py:164-180`)
  - `_handle_stream_message_update` (`src/tunacode/core/agents/agent_components/agent_streaming.py:181-191`)
  - `_handle_stream_message_end` (`src/tunacode/core/agents/agent_components/agent_streaming.py:193-216`)
  - `_handle_stream_tool_execution_start` (`src/tunacode/core/agents/agent_components/agent_streaming.py:218-240`)
  - `_handle_stream_tool_execution_update` (`src/tunacode/core/agents/agent_components/agent_streaming.py:287-314`)
  - `_handle_stream_tool_execution_end` (`src/tunacode/core/agents/agent_components/agent_streaming.py:242-285`)
  - `_handle_stream_agent_end` (`src/tunacode/core/agents/agent_components/agent_streaming.py:316-326`)
- `src/tunacode/core/agents/agent_components/agent_streaming.py:151-153` `except` block calls `_handle_interrupted_stream_cleanup` on `CancelledError`/`Exception`.

## Notes
- Repository search for references to `src/tunacode/core/agents/agent_streaming` did not find imports outside `src/tunacode/core/agents/main.py`.
- `rg` matches in `src/tunacode/ui/renderers/agent_response.py:57` are for `render_agent_streaming` function name, not imports or references to this module.
