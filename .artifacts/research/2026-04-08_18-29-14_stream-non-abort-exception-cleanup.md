---
title: "stream non-abort exception cleanup research findings"
link: "stream-non-abort-exception-cleanup-research"
type: research
ontological_relations:
  - relates_to: [[docs/modules/core/core.md]]
tags: [research, stream-exceptions, agents]
uuid: "d9c4b273-53b0-4cb2-a973-d0d656cb9bde"
created_at: "2026-04-08T18:29:14-05:00"
---

## Structure
- `src/tunacode/core/agents/main.py` contains the request entrypoint, stream loop, stream event dispatch, tool lifecycle handlers, and abort cleanup.
- `src/tunacode/core/agents/helpers.py` defines `_TinyAgentStreamState` and helper functions used by `main.py`.
- `src/tunacode/core/types/state_structures.py` defines `RuntimeState`, which owns `tool_registry`.
- `src/tunacode/core/types/tool_registry.py` defines `ToolCallRegistry` methods for `register`, `start`, `complete`, `fail`, `remove`, and `remove_many`.
- `src/tunacode/core/agents/resume/sanitize.py` contains separate cleanup functions for resume-time message sanitization.
- `tests/unit/core/test_request_orchestrator_parallel_tools.py` contains current unit coverage for tool lifecycle and abort cleanup.
- `tests/unit/core/test_stream_phase_debug.py` contains current unit coverage for `_run_stream()` logging behavior.

## Key Files
- `src/tunacode/core/agents/main.py:L188` defines `RequestOrchestrator._run_impl()`.
- `src/tunacode/core/agents/main.py:L247` catches only `UserAbortError` and `asyncio.CancelledError` in `_run_impl()`.
- `src/tunacode/core/agents/main.py:L373` defines `_remove_in_flight_tool_registry_entries()`.
- `src/tunacode/core/agents/main.py:L388` defines `_forward_patch_dangling_tool_calls()`.
- `src/tunacode/core/agents/main.py:L481` defines `_handle_stream_tool_execution_start()`.
- `src/tunacode/core/agents/main.py:L505` defines `_handle_stream_tool_execution_end()`.
- `src/tunacode/core/agents/main.py:L652` defines `_run_stream()`.
- `src/tunacode/core/agents/main.py:L708` clears `self._active_stream_state` only when `stream_completed` is true.
- `src/tunacode/core/agents/main.py:L744` defines `_handle_abort_cleanup()`.
- `src/tunacode/core/agents/helpers.py:L35` defines `_TinyAgentStreamState`.
- `src/tunacode/core/types/state_structures.py:L57` defines `RuntimeState`.
- `src/tunacode/core/types/tool_registry.py:L33` defines `ToolCallRegistry`.
- `src/tunacode/core/agents/resume/sanitize.py:L396` defines `remove_dangling_tool_calls()`.
- `src/tunacode/core/agents/resume/sanitize.py:L444` defines `run_cleanup_loop()`.
- `tests/unit/core/test_request_orchestrator_parallel_tools.py:L72` starts tool lifecycle coverage for parallel batches.
- `tests/unit/core/test_request_orchestrator_parallel_tools.py:L194` starts abort cleanup coverage.
- `tests/unit/core/test_stream_phase_debug.py:L40` starts `_run_stream()` logging coverage.

## Patterns Found
- Request flow:
  - `src/tunacode/core/agents/main.py:L172-L180` `run()` wraps `_run_impl()` with `asyncio.wait_for()` when a timeout is configured.
  - `src/tunacode/core/agents/main.py:L235-L246` `_run_impl()` awaits `_run_stream()`, then `_retry_after_context_overflow_if_needed()`, then returns the agent.
  - `src/tunacode/core/agents/main.py:L247-L254` `_run_impl()` routes `UserAbortError` and `asyncio.CancelledError` through `_handle_abort_cleanup()`.
- Stream-state construction:
  - `src/tunacode/core/agents/helpers.py:L35-L41` `_TinyAgentStreamState` stores `runtime`, `tool_start_times`, `active_tool_call_ids`, `batch_tool_call_ids`, and `last_assistant_message`.
  - `src/tunacode/core/agents/main.py:L661-L667` `_run_stream()` creates `_TinyAgentStreamState` and stores it on `self._active_stream_state`.
- Tool-start mutation order:
  - `src/tunacode/core/agents/main.py:L493` records `state.tool_start_times[tool_call_id]`.
  - `src/tunacode/core/agents/main.py:L494` updates `state.active_tool_call_ids` and `state.batch_tool_call_ids` through `_mark_tool_start_batch_state()`.
  - `src/tunacode/core/agents/main.py:L495-L500` registers the tool call in `state.runtime.tool_registry` and marks it running.
  - `src/tunacode/core/agents/main.py:L501-L502` invokes `self.tool_start_callback(tool_name)` if present.
- Tool-end mutation order:
  - `src/tunacode/core/agents/main.py:L525-L532` updates `tool_registry` with `fail()` or `complete()`.
  - `src/tunacode/core/agents/main.py:L534-L535` removes the tool call from `state.active_tool_call_ids` and may clear `batch_tool_call_ids`.
  - `src/tunacode/core/agents/main.py:L540-L547` invokes `tool_result_callback()` after reading stored args from the registry.
- Stream finalization:
  - `src/tunacode/core/agents/main.py:L674-L710` `_run_stream()` tracks `stream_completed`; its `finally` block sets `self._active_stream_state = None` only when `stream_completed` is true.
  - `src/tunacode/core/agents/main.py:L720-L722` raises `AgentError` after the stream if `agent.state.error` is set and is not a context-overflow error.
- Abort cleanup path:
  - `src/tunacode/core/agents/main.py:L752-L757` `_handle_abort_cleanup()` calls `_forward_patch_dangling_tool_calls()` when `agent` and `baseline_message_count` are present.
  - `src/tunacode/core/agents/main.py:L759` calls `_remove_in_flight_tool_registry_entries()`.
  - `src/tunacode/core/agents/main.py:L760` appends a partial interrupted assistant message when `_debug_raw_stream_accum` is non-empty.
  - `src/tunacode/core/agents/main.py:L761` clears `self._active_stream_state`.
- Resume-time cleanup path:
  - `src/tunacode/core/agents/resume/sanitize.py:L396-L413` `remove_dangling_tool_calls()` removes dangling tool calls from assistant content and prunes the registry.
  - `src/tunacode/core/agents/resume/sanitize.py:L444-L485` `run_cleanup_loop()` iteratively removes dangling tool calls, empty responses, and consecutive requests, and calls `tool_registry.remove_many()` for dangling ids.

## Dependencies
- `src/tunacode/core/agents/main.py` imports:
  - `tinyagent.agent` and `tinyagent.agent_types` at `src/tunacode/core/agents/main.py:L11-L32`.
  - `tunacode.core.compaction.controller` at `src/tunacode/core/agents/main.py:L51-L56`.
  - `tunacode.core.compaction.types` at `src/tunacode/core/agents/main.py:L57`.
  - `tunacode.core.debug.usage_trace` at `src/tunacode/core/agents/main.py:L58`.
  - `tunacode.core.logging.manager` at `src/tunacode/core/agents/main.py:L59`.
  - `tunacode.core.types.state` at `src/tunacode/core/agents/main.py:L60`.
  - local `agent_components` at `src/tunacode/core/agents/main.py:L62-L63`.
  - local `helpers` at `src/tunacode/core/agents/main.py:L64-L73`.
- `src/tunacode/core/agents/helpers.py:L23` imports `RuntimeState` from `src/tunacode/core/types/state_structures.py`.
- `src/tunacode/core/types/state_structures.py:L65` stores `ToolCallRegistry` on `RuntimeState.tool_registry`.
- `src/tunacode/core/types/tool_registry.py:L39-L160` provides the registry methods used by `main.py`:
  - `register()` at `src/tunacode/core/types/tool_registry.py:L39-L59`
  - `start()` at `src/tunacode/core/types/tool_registry.py:L61-L70`
  - `complete()` at `src/tunacode/core/types/tool_registry.py:L72-L85`
  - `fail()` at `src/tunacode/core/types/tool_registry.py:L87-L102`
  - `get_args()` at `src/tunacode/core/types/tool_registry.py:L123-L128`
  - `remove_many()` at `src/tunacode/core/types/tool_registry.py:L154-L160`

## Test Coverage Located
- `tests/unit/core/test_request_orchestrator_parallel_tools.py:L72-L148` exercises `_handle_stream_tool_execution_start()` and `_handle_stream_tool_execution_end()` for two tool calls and checks registry state plus callbacks.
- `tests/unit/core/test_request_orchestrator_parallel_tools.py:L151-L191` exercises duration reporting for a single tool call.
- `tests/unit/core/test_request_orchestrator_parallel_tools.py:L194-L250` exercises `_handle_abort_cleanup()` for one dangling tool call and checks injected `ToolResultMessage`, interrupted assistant message, registry removal, and token recomputation.
- `tests/unit/core/test_request_orchestrator_parallel_tools.py:L253-L320` exercises `_handle_abort_cleanup()` for a prior completed turn plus one in-flight tool call.
- `tests/unit/core/test_request_orchestrator_parallel_tools.py:L323-L379` exercises `_handle_abort_cleanup()` with one completed tool result and one unresolved tool call.
- `tests/unit/core/test_request_orchestrator_parallel_tools.py:L405-L420` and later functions exercise `_patch_dangling_tool_calls()`.
- `tests/unit/core/test_stream_phase_debug.py:L40-L90` exercises `_run_stream()` event-gap logging.
- Repository search for `tool_start_callback`, `_run_impl(`, `_run_stream(`, `_handle_abort_cleanup(`, `CancelledError`, `UserAbortError`, `callback blew up`, `raise RuntimeError`, and `tool_result_callback` within `tests/` returned matches in:
  - `tests/unit/core/test_request_orchestrator_parallel_tools.py`
  - `tests/unit/core/test_stream_phase_debug.py`
  - unrelated UI/system callback tests outside the core orchestrator path
- The same search returned no test file containing the literal string `callback blew up`.

## History Located
- `git blame` on `src/tunacode/core/agents/main.py:L235-L254` shows:
  - `tunahorse1` authored the `try:` line and the `raise` line in commit `ab49b841e` dated `2026-01-31`.
  - `larock22` authored `_run_stream()` and `_retry_after_context_overflow_if_needed()` call lines in commit `9c9036065` dated `2026-02-11`.
  - `larock22` authored `max_iterations` argument lines in commit `59ba22ee2` dated `2026-03-17`.
  - `tuna` authored the `_handle_abort_cleanup(...)` call block in commit `cfbe7daf6` dated `2026-03-16`.
  - `tunahorse1` authored the `except (UserAbortError, asyncio.CancelledError):` line in commit `72784d0da` dated `2026-03-16`.
- `git blame` on `src/tunacode/core/agents/main.py:L481-L503` shows:
  - `tuna` authored the function definition and `tool_start_callback` invocation lines in commit `3f8dea1a0` dated `2026-02-08`.
  - `larock22` authored `event_obj`, `agent`, `tool_call_id`, `tool_name`, and `args` lines across commits `e93fff65f`, `59ba22ee2`, and `126f4f5fc` dated `2026-03-04` and `2026-03-17`.
  - `sneaek tater` authored the `_mark_tool_start_batch_state(...)` line in commit `c46e1c2db` dated `2026-02-23`.
  - `tunahorse1` authored the `tool_registry.register(...)` block in commit `72784d0da` dated `2026-03-16`.

## Symbol Index
- `src/tunacode/core/agents/main.py:L101` → `_patch_dangling_tool_calls(messages: list[AgentMessage]) -> int`
- `src/tunacode/core/agents/main.py:L145` → `RequestOrchestrator`
- `src/tunacode/core/agents/main.py:L766` → `get_agent_tool()`
- `src/tunacode/core/agents/main.py:L771` → `process_request(...)`
- `src/tunacode/core/agents/helpers.py:L35` → `_TinyAgentStreamState`
- `src/tunacode/core/types/state_structures.py:L57` → `RuntimeState`
- `src/tunacode/core/types/tool_registry.py:L33` → `ToolCallRegistry`
- `src/tunacode/core/agents/resume/sanitize.py:L391` → `find_dangling_tool_call_ids(...)`
- `src/tunacode/core/agents/resume/sanitize.py:L396` → `remove_dangling_tool_calls(...)`
- `src/tunacode/core/agents/resume/sanitize.py:L444` → `run_cleanup_loop(...)`

## Script Outputs Recorded
- `structure-map.sh` on `src/tunacode/core/agents` listed:
  - `src/tunacode/core/agents/__init__.py`
  - `src/tunacode/core/agents/agent_components/__init__.py`
  - `src/tunacode/core/agents/agent_components/agent_config.py`
  - `src/tunacode/core/agents/agent_components/agent_helpers.py`
  - `src/tunacode/core/agents/agent_components/agent_session_config.py`
  - `src/tunacode/core/agents/helpers.py`
  - `src/tunacode/core/agents/main.py`
  - `src/tunacode/core/agents/resume/__init__.py`
  - `src/tunacode/core/agents/resume/sanitize.py`
  - `src/tunacode/core/agents/resume/sanitize_debug.py`
- `dependency-graph.sh ./ --file src/tunacode/core/agents/main.py` listed imports from `tinyagent`, `tunacode.constants`, `tunacode.exceptions`, `tunacode.types`, `tunacode.utils.messaging`, `tunacode.core.compaction`, `tunacode.core.debug.usage_trace`, `tunacode.core.logging.manager`, `tunacode.core.types.state`, local `agent_components`, and local `helpers`.
- `symbol-index.sh src/tunacode/core/agents` reported Python public symbols including `_TinyAgentStreamState`, `AgentSettings`, `SessionConfig`, `SkillsPromptState`, `EmptyResponseStateView`, and multiple resume-time data classes.
- `ast-scan.sh functions src/tunacode/core/agents` produced only the header line `=== Function Definitions ===` in this run.
