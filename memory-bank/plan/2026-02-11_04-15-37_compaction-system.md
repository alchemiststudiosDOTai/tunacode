---
title: "Compaction System -- Plan"
phase: Plan
date: "2026-02-11T04:15:37Z"
owner: "claude"
parent_research: "memory-bank/research/2026-02-10_21-29-05_compaction-system-mapping.md"
git_commit_at_plan: "a454860b"
tags: [plan, compaction, context-management]
---

## Goal

Implement context compaction for TunaCode so that long-running sessions do not hit context window limits. When estimated token usage crosses a threshold, the system summarizes older messages and replaces them with a structured summary, keeping recent messages intact.

**Non-goals:**
- Branch summarization (TunaCode has no tree navigation)
- Multi-model compaction routing (uses same conversation model)
- Async/background compaction (synchronous, blocking)
- Post-response compaction trigger (dropped per council review)

## Scope & Assumptions

**In scope:**
- `CompactionRecord` dataclass for session-level metadata
- `ContextSummarizer` for retention window calculation, message serialization, LLM summarization
- `CompactionController` as single entry point (pre-request + overflow retry)
- `transform_context` hook wiring (delegates to controller, idempotent per-request)
- Session persistence of compaction state (new optional `compaction` field)
- `/compact` slash command for manual trigger
- Resource bar "Compacting..." indicator
- `ContextOverflowError` exception
- Fail-safe behavior (proceed uncompacted on summarization failure)

**Out of scope:**
- Changing the token estimation heuristic (chars/4 is acceptable)
- Modifying tinyagent source code
- Dashboard/metrics/monitoring
- Compaction configuration UI (hardcoded defaults for now)

**Assumptions:**
- tinyagent's `transform_context` hook works as documented (signature verified by subagent)
- `transform_context` fires per-turn (not per-request) -- idempotency guard required
- tinyagent swallows all exceptions in `stream()` and surfaces errors as `agent.state["error"]` -- overflow detection must pattern-match error strings, not catch Python exceptions
- Agent caching hash does NOT include `transform_context` -- callback must read state dynamically from session, not from a snapshot
- `ConversationState` uses `slots=True` -- compaction state lives on `SessionState` (not `ConversationState`)
- `_persist_agent_messages()` overwrites `conversation.messages` from agent state -- agent must receive compacted messages via `replace_messages()` so its internal state reflects compaction

## Deliverables (DoD)

1. **CompactionRecord + ContextSummarizer + prompts** -- Pure logic layer with no integration dependencies. Acceptance: retention window calculation returns correct boundary indices for known message sequences.
2. **CompactionController + session persistence** -- Orchestration layer. Acceptance: compaction state round-trips through save/load; controller respects threshold and idempotency guard.
3. **Agent loop integration** -- Pre-request check + overflow retry + transform_context wiring. Acceptance: automatic compaction triggers when token estimate exceeds threshold; overflow retry works when agent.state["error"] matches overflow pattern.
4. **UI integration** -- `/compact` command + resource bar indicator + system notices. Acceptance: `/compact` manually triggers compaction; resource bar shows "Compacting..." during operation; token count updates after compaction.
5. **One integration test** -- End-to-end test of compaction flow. Acceptance: test creates a message list exceeding threshold, triggers compaction, verifies message count reduced and summary present.

## Readiness (DoR)

- [x] Research doc complete with council review: `memory-bank/research/2026-02-10_21-29-05_compaction-system-mapping.md`
- [x] All design decisions locked (compaction model, state storage, trigger strategy, fail-safe behavior)
- [x] Key integration points verified by subagent analysis (agent_config.py, main.py, state.py, resource_bar.py, commands/__init__.py, agent_loop.py)
- [x] tinyagent `transform_context` signature confirmed: `Callable[[list[AgentMessage], asyncio.Event | None], Awaitable[list[AgentMessage]]]`
- [x] Git state clean (HEAD = a454860b, matches research doc commit, no drift)

## Milestones

- **M1: Foundation** -- CompactionRecord types, ContextSummarizer (retention window + serialization + LLM call), CompactionPrompts, ContextOverflowError
- **M2: Controller + Persistence** -- CompactionController (threshold, orchestration, idempotency, fail-safe), session save/load of compaction field
- **M3: Agent Integration** -- Wire transform_context, pre-request check in _run_impl, overflow retry via agent.state["error"] pattern matching
- **M4: UI** -- /compact command, resource bar indicator, system notices
- **M5: Test** -- One integration test exercising the full compaction flow

## Work Breakdown (Tasks)

### Task 1: Foundation Layer (M1, P1, no dependencies)

**Summary:** Create `src/tunacode/core/compaction/` package with types, summarizer, prompts, and add ContextOverflowError to exceptions.

**Files/Interfaces:**
- `src/tunacode/core/compaction/__init__.py` (new)
- `src/tunacode/core/compaction/types.py` (new) -- `CompactionRecord` dataclass
- `src/tunacode/core/compaction/summarizer.py` (new) -- `ContextSummarizer` class
- `src/tunacode/core/compaction/prompts.py` (new) -- `FRESH_SUMMARY_PROMPT`, `ITERATIVE_SUMMARY_PROMPT`
- `src/tunacode/exceptions.py` (edit) -- add `ContextOverflowError`

**Acceptance Tests:**
- `CompactionRecord` can be constructed, serialized to dict, deserialized from dict
- `ContextSummarizer.calculate_retention_boundary(messages, keep_recent_tokens)` returns correct index for a known message list
- `ContextSummarizer.serialize_messages(messages)` produces expected text format
- `ContextOverflowError` stores `estimated_tokens`, `max_tokens`, `model` and produces human-readable message with recovery commands

**Key implementation details:**
- Retention window walks backwards from newest message, accumulating estimated tokens via existing `estimate_message_tokens()`
- Valid boundaries: after UserMessage, after AssistantMessage with stop_reason != None
- Never split between tool_call content and ToolResultMessage
- Message serialization truncates tool results to 500 chars
- Summarizer makes one LLM call using the same model as the conversation (via tinyagent streaming provider)

### Task 2: Controller + Session Persistence (M2, P1, depends on Task 1)

**Summary:** Create CompactionController as single orchestration entry point. Add compaction field to session save/load.

**Files/Interfaces:**
- `src/tunacode/core/compaction/controller.py` (new) -- `CompactionController` class
- `src/tunacode/core/session/state.py` (edit) -- add `compaction` to save_session/load_session
- `src/tunacode/core/session/state.py` (edit) -- add `compaction: CompactionRecord | None = None` to SessionState

**Acceptance Tests:**
- `CompactionController.should_compact(messages, max_tokens, reserve_tokens)` returns True when tokens exceed threshold
- Controller tracks per-request compaction via `_compacted_this_request` flag to prevent double-compaction across transform_context turns
- Session with compaction data round-trips: save -> load -> compaction field preserved
- Old sessions without compaction field load with `compaction = None`
- `force_compact()` ignores threshold and always compacts

**Key implementation details:**
- Controller owns policy: `should_compact()` checks `estimate_messages_tokens(messages) > (max_tokens - reserve_tokens - keep_recent_tokens)`
- `check_and_compact()` is the primary entry point (pre-request)
- `force_compact()` is the overflow entry point (bypasses threshold)
- Idempotency: `_compacted_this_request: bool` flag, reset at start of each request
- Fail-safe: if summarization LLM call raises, log error, return original messages unchanged
- Session persistence: `session_data["compaction"] = record.to_dict() if record else None`

### Task 3: Agent Loop Integration (M3, P1, depends on Task 2)

**Summary:** Wire CompactionController into the agent loop via transform_context hook and _run_impl pre-request check. Add overflow retry.

**Files/Interfaces:**
- `src/tunacode/core/agents/agent_components/agent_config.py` (edit) -- wire `transform_context` in AgentOptions
- `src/tunacode/core/agents/main.py` (edit) -- pre-request check before agent.replace_messages(), overflow retry after _run_stream()

**Acceptance Tests:**
- `transform_context` is wired in AgentOptions construction (no longer None)
- Pre-request: when messages exceed threshold, compaction runs before `agent.replace_messages()`
- `baseline_message_count` is re-snapshotted after compaction so `_persist_agent_messages` slices correctly
- Overflow retry: when `agent.state["error"]` contains overflow pattern, `force_compact()` runs and stream retries once
- On summarization failure: original messages are used (fail-safe), no crash

**Key implementation details:**
- `transform_context` callback: closure capturing `state_manager`, delegates to `controller.check_and_compact()`, returns messages (possibly with injected summary UserMessage at front)
- The callback must be stateless regarding captures -- reads compaction state from `state_manager.session.compaction` dynamically (agent cache does not include transform_context in its hash)
- Pre-request insertion: between `_coerce_tinyagent_history()` and `agent.replace_messages()` in `_run_impl()`
- After compaction, re-snapshot `baseline_message_count = len(conversation.messages)`
- Overflow detection: pattern-match `agent.state.get("error", "")` for `"context_length_exceeded"` or `"maximum context length"` (OpenRouter patterns)
- `transform_context` injects summary as synthetic UserMessage at front of message list -- transient, never persisted

### Task 4: UI Integration (M4, P2, depends on Task 2)

**Summary:** Add /compact command, resource bar compaction indicator, and system notice pattern.

**Files/Interfaces:**
- `src/tunacode/ui/commands/compact.py` (new) -- `CompactCommand` class
- `src/tunacode/ui/commands/__init__.py` (edit) -- register CompactCommand in COMMANDS dict
- `src/tunacode/ui/widgets/resource_bar.py` (edit) -- add `_compacting` field and `update_compaction_status()` method
- `src/tunacode/ui/app.py` (edit) -- call resource_bar.update_compaction_status() during compaction

**Acceptance Tests:**
- `/compact` appears in autocomplete
- `/compact` triggers compaction via CompactionController
- Resource bar shows "Compacting..." segment when active, hides when done
- System notice "Compacting context..." appears in chat during operation
- Token count in resource bar updates after compaction completes
- Toast notification confirms completion

**Key implementation details:**
- CompactCommand follows ClearCommand pattern: mutate state, update resource bar, notify, save session
- Resource bar: add `self._compacting: bool = False`, method `update_compaction_status(active: bool)`, conditional segment in `_refresh_display()` after LSP block
- Notice callback: pass through to compaction layer for "Compacting..." in-chat feedback

### Task 5: Integration Test (M5, P2, depends on Tasks 1-3)

**Summary:** One end-to-end test that exercises the compaction flow.

**Files/Interfaces:**
- `tests/test_compaction.py` (new)

**Acceptance Tests:**
- Test creates a message list that exceeds the threshold
- Triggers compaction via CompactionController
- Verifies: message count reduced, CompactionRecord created with correct fields, summary contains expected structure markers (## Goal, ## Progress, etc.)
- Verifies: retention window keeps recent messages intact
- Verifies: round-trip serialization of CompactionRecord

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|---|---|---|---|---|
| OpenRouter overflow error format unknown | Overflow retry fails silently | Medium | Pattern-match multiple known formats; log unrecognized errors; `/compact` as manual fallback | First production overflow error |
| Summary quality degrades conversation | User loses critical context | Medium | Structured summary format with explicit sections; iterative updates preserve prior summary | User reports loss of context after compaction |
| Summarization LLM call slow (>5s) | User perceives hang | Low | "Compacting..." UI indicator; abort signal propagation; fail-safe on timeout | Measured latency > 5s in testing |
| transform_context double-fires in tool loop | Duplicate compaction corrupts state | High | Per-request idempotency flag in CompactionController | Any multi-tool-call request |
| Agent cache ignores transform_context changes | Stale callback used | Medium | Callback reads state dynamically from session ref, not from captured snapshot | Agent reuse across model switches |

## Test Strategy

One integration test (`tests/test_compaction.py`) covering:
- Retention window calculation with known message sequence
- CompactionController threshold + idempotency
- CompactionRecord serialization round-trip
- Message serialization format

If more tests are needed, they will be added in a follow-up.

## References

- Research doc: `memory-bank/research/2026-02-10_21-29-05_compaction-system-mapping.md`
- Pi-mono reference: `memory-bank/research/2026-02-07_18-06-58_compaction-system.md`
- Council review: synthesized in research doc (2026-02-10 section header)
- tinyagent transform_context: `tinyAgent/tinyagent/agent.py:241-244` (type), `tinyAgent/tinyagent/agent_loop.py:99-116` (call site)
- Agent config: `src/tunacode/core/agents/agent_components/agent_config.py:286-290`
- Agent loop: `src/tunacode/core/agents/main.py:304-328` (_run_impl), `main.py:362-373` (_persist_agent_messages)
- Session persistence: `src/tunacode/core/session/state.py:233-259` (save), `state.py:261-309` (load)
- Token counter: `src/tunacode/utils/messaging/token_counter.py`
- Commands: `src/tunacode/ui/commands/__init__.py:510-518`
- Resource bar: `src/tunacode/ui/widgets/resource_bar.py`
- Exceptions: `src/tunacode/exceptions.py`

## Tickets Created

| Ticket ID | Title | Priority | Status | Milestone |
|-----------|-------|----------|--------|-----------|
| tun-af61 | Implement compaction foundation layer (types, summarizer, prompts, exception) | P1 | open | M1 |
| tun-ce1a | Implement CompactionController and session persistence | P1 | open | M2 |
| tun-05de | Wire compaction into agent loop (transform_context + pre-request + overflow retry) | P1 | open | M3 |
| tun-a3de | Add /compact command, resource bar indicator, and system notices | P2 | open | M4 |
| tun-826c | Write compaction integration test | P2 | open | M5 |

## Dependencies

```
tun-af61 (foundation)
    |
    v
tun-ce1a (controller + persistence)
    |
    +-------+-------+
    v               v
tun-05de (agent)   tun-a3de (UI)
    |
    v
tun-826c (test)
```

## Ready to Start

- `tun-af61` -- no blockers, can begin immediately
