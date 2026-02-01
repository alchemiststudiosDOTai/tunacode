---
title: Pydantic Removal Contract
link: pydantic-removal-contract
type: doc
path: docs/refactoring/pydantic-removal-contract.md
depth: 2
seams: [A, M, S, D]
ontological_relations:
  - relates_to: [[message-flow-map]]
  - affects: [[request-loop]]
  - affects: [[message-serialization]]
  - affects: [[tool-call-lifecycle]]
tags:
  - pydantic-ai
  - request-loop
  - serialization
  - tools
created_at: 2026-01-31T21:25:27-06:00
updated_at: 2026-01-31T21:25:27-06:00
uuid: 216ac580-5ee8-4882-a73e-39ac1f3794ae
---

# Pydantic Removal Contract

## Summary
This document defines the minimal internal contracts that must remain stable while replacing pydantic-ai: request loop responsibilities, canonical message shapes, tool lifecycle handling, persistence format, and orchestration IDs. It is the checklist for removing pydantic-ai without losing state, history, or tool behavior.

## Context
pydantic-ai currently owns the request loop and its message types. A prior runtime removal attempt failed because the agent loop expects `ModelRequest`/`ModelResponse` objects; when history was stored as wire dicts, `_clean_message_history` dropped prior turns and context vanished. Streaming is no longer used, so it is explicitly out of scope for this contract.

## Changes
- Mapped request loop responsibilities and node expectations that must be preserved.
- Documented canonical message and tool call shapes, including serialization formats.
- Enumerated orchestration IDs and invariants that must survive persistence and loop replacement.
- Captured retry/usage/tool lifecycle semantics that are currently pydantic-shaped.

## Contract Surface Map

| Surface | Files | Contract Summary |
| --- | --- | --- |
| Request loop | `src/tunacode/core/agents/main.py` | Request lifecycle, cleanup, iteration, abort handling, message persistence. |
| Node processing | `src/tunacode/core/agents/agent_components/orchestrator/` | Response parsing, tool dispatch, usage updates, empty response detection. |
| Canonical types | `src/tunacode/types/canonical.py` | Authoritative message + part definitions and tool call record shape. |
| Message adapter | `src/tunacode/utils/messaging/adapter.py` | Conversion to/from canonical forms; parts are single source of truth. |
| Persistence | `src/tunacode/core/state.py` | Session file schema and message serialization/deserialization. |
| Tool lifecycle | `src/tunacode/core/types/tool_registry.py`, `tools/decorators.py`, `agent_components/tool_executor.py` | Tool call tracking, retries, and error contracts. |
| Provider + tools | `src/tunacode/core/agents/agent_components/agent_config.py` | Provider selection + tool schema registration. |
| UI dependencies | `src/tunacode/ui/app.py`, `src/tunacode/ui/headless/output.py` | Current UI assumes `ModelResponse` for latest assistant message. |

## Request Loop Contract (Core Orchestrator)

**Owner:** `RequestOrchestrator` in `src/tunacode/core/agents/main.py`.

**Required sequence (must be preserved or replaced 1:1):**

1. **Context + ID**
   - Generate `request_id` (`uuid4` prefix length 8) and assign to `session.runtime.request_id`.
2. **Runtime reset**
   - Clear runtime counters (`current_iteration`, `iteration_count`, `batch_counter`).
   - Clear `runtime.tool_registry`.
   - Reset `consecutive_empty_responses`.
   - Reset `task.original_query` unless already set.
3. **History preparation**
   - Prune old tool outputs via `prune_old_tool_outputs` (mutates `ToolReturnPart.content`).
   - Run `run_cleanup_loop` to remove dangling tool calls, empty responses, and consecutive requests.
   - If history ends with a request, drop it before adding a new request.
   - Run `sanitize_history_for_resume` (strip system prompts, clear `run_id`).
4. **Iterative loop**
   - `agent.iter(message, message_history=sanitized_history)`.
   - For each node:
     - Update iteration counters.
     - Process node via `process_node(...)` (usage updates, tool dispatch, thought capture).
     - Empty response detection + intervention (`EmptyResponseHandler`).
     - Break when `response_state.task_completed` is true.
5. **Finalize**
   - Flush buffered tool tasks (`_finalize_buffered_tasks`).
   - Persist authoritative run messages (`agent_run.all_messages()` plus external additions).
6. **Abort/timeout handling**
   - On abort: append an `[INTERRUPTED]` `ModelResponse` containing partial stream text.
   - Clean dangling tool calls, empty responses, consecutive requests.
   - Invalidate agent cache after abort or timeout.

**Critical side effects:**
- `session.conversation.messages` must be updated with authoritative run history.
- `session.update_token_count()` must run after message mutations.

## Node Shape Contract (Process Node)

`process_node()` expects a node object with the following attributes:

| Attribute | Used By | Purpose |
| --- | --- | --- |
| `node.request` | `_emit_tool_returns` | Extracts `ToolReturnPart` parts; updates tool registry + UI callbacks. |
| `node.model_response` | `dispatch_tools` + usage tracker | Reads `parts` for tool calls; reads `usage` for token/cost. |
| `node.thought` | `record_thought` | Captures assistant reasoning into session thoughts. |
| `node.result.output` | request loop | Indicates visible response to set `response_state.has_user_response`. |

Any replacement loop must either keep this shape or adapt `process_node` to the new shape.

## Canonical Message Contract

**Authoritative types:** `CanonicalMessage`, `TextPart`, `ToolCallPart`, `ToolReturnPart`, `RetryPromptPart`, `SystemPromptPart`, `ThoughtPart` in `src/tunacode/types/canonical.py`.

**Rules:**
- `parts` is the single source of truth. **Never** rely on a separate `tool_calls` list.
- `tool_call_id` is required on tool call/return parts.
- Order of `parts` must be preserved.
- Legacy dict messages (`{"content": ...}` and `{"thought": ...}`) remain loadable until session migration is complete.

**Wire format for persistence (current default):**
```json
{
  "kind": "request|response",
  "parts": [
    {"part_kind": "text", "content": "..."},
    {"part_kind": "tool-call", "tool_call_id": "tc_1", "tool_name": "bash", "args": {"command": "ls"}},
    {"part_kind": "tool-return", "tool_call_id": "tc_1", "content": "..."}
  ]
}
```

**Sanitization rules (resume safety):**
- Strip `system-prompt` parts.
- Clear `run_id` attribute when present (pydantic-specific guard).

## Tool Call Lifecycle Contract

**Registry:** `ToolCallRegistry` (runtime) is the single source of truth for tool call status.

**Lifecycle steps:**
1. **Register** on tool call parsing (`record_tool_call_args`).
2. **Start** when tool execution begins (`_mark_tool_calls_running`).
3. **Complete** when a tool return part is emitted (`_emit_tool_returns`).
4. **Fail/Cancel** on error or abort (`_record_tool_failure`).

**Execution semantics:**
- `execute_tools_parallel` retries up to `TOOL_MAX_RETRIES`.
- `ToolRetryError` is converted to `pydantic_ai.ModelRetry` by decorators; retry signaling is part of the tool contract.
- `NON_RETRYABLE_ERRORS` include `ModelRetry`, `ToolExecutionError`, `UserAbortError`.

**Fallback parsing:**
- If no structured tool calls exist, `_extract_fallback_tool_calls` parses text parts and builds tool calls. This requires a `ToolCallPart`-compatible shape (`tool_call_id`, `tool_name`, `args`).

## Persistence Contract

**Session file keys (must remain stable):**
- `version`, `session_id`, `project_id`, `created_at`, `last_modified`, `working_directory`
- `current_model`, `total_tokens`, `session_total_usage`
- `thoughts`, `messages`

**Current serializer:** `StateManager._serialize_messages()` uses `pydantic.TypeAdapter(ModelMessage)`.

**Removal requirement:** new serializer must preserve:
- `kind`, `parts`, `part_kind`, `tool_call_id`, `tool_name`, `args`, `content`
- Legacy dict forms (`content`, `thought`) for backward compatibility

## Usage Tracking Contract

`update_usage()` expects a response `usage` object with attributes:
- `request_tokens`, `response_tokens`, `cached_tokens`

Providers must expose equivalent fields or be normalized to this shape.

## Orchestration IDs & Invariants

| ID | Stored In | Used By | Notes |
| --- | --- | --- | --- |
| `session_id` | `SessionState.session_id` | Persistence | Part of session filename. |
| `request_id` | `RuntimeState.request_id` | Logging | Per-request correlation. |
| `tool_call_id` | `ToolCallPart` + `ToolReturnPart` + registry | Tool lifecycle | Required for pairing calls/returns. |
| `run_id` | Message attribute (pydantic) | Resume sanitization | Cleared before reuse; new loop may drop it. |
| `batch_counter` | `RuntimeState.batch_counter` | Logs/UI | Increments per tool batch. |

**Invariants:**
- No dangling tool calls before sending a request.
- No consecutive request messages in history.
- System prompt parts are never persisted in history.
- Tool registry and message parts must reference the same `tool_call_id` values.

## Out of Scope
- **Streaming protocol** (`agent_components/streaming.py`) is not used and is excluded from this contract.

## Verification Checklist

- History survives round-trip serialization with identical `parts` and `tool_call_id` values.
- Session load preserves `thoughts`, `messages`, and `session_total_usage`.
- Tool registry records complete/fail/cancel updates in sync with tool return parts.
- Request loop still prunes and sanitizes history before a run.
- Abort path appends an `[INTERRUPTED]` response and cleans dangling tool calls.
- UI can still extract the latest assistant response without depending on `ModelResponse`.

## Behavioral Impact

**What readers gain:**
- A single, testable contract for replacing pydantic-ai without losing orchestration state.

**What doesn’t change:**
- Existing user-visible behavior (tool calls, history, persistence) remains the baseline.

## Related Cards
- [[message-flow-map]]
