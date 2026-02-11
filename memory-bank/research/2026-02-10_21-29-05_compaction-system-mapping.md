# Research -- Compaction System Mapping for TunaCode

**Date:** 2026-02-10
**Owner:** claude
**Phase:** Research
**git_commit:** a454860be6cd2c8c3d1a1a35f9fb9beb7edc5685

## Goal

Map the current tunacode codebase against the pi-mono compaction system architecture (documented in `memory-bank/research/2026-02-07_18-06-58_compaction-system.md`) to identify what exists, what is missing, and what needs to be built to implement context compaction.

## Summary

TunaCode has **no compaction system**. Messages grow unboundedly, token estimation is cosmetic (display only), and context overflow errors are unhandled. However, the architecture has clean integration points: tinyagent exposes a `transform_context` hook designed exactly for compaction, and tunacode already has token estimation, session persistence, and a command system ready to host compaction.

---

## Findings

### Current Architecture vs Pi-Mono Compaction Features

| Pi-Mono Feature | TunaCode Status | Gap |
|---|---|---|
| Dual-trigger compaction (overflow + threshold) | MISSING | No overflow detection, no threshold check |
| Intelligent cut point detection | MISSING | No cut point algorithm |
| Split turn handling | MISSING | No turn-aware splitting |
| Cumulative file tracking | PARTIAL | `ConversationState.files_in_context` exists but not used for compaction |
| Structured summary format | MISSING | No summarization prompts |
| Message serialization (for summarizer) | MISSING | No serialize-to-text for summarization |
| Iterative summary updates | MISSING | No update-vs-fresh summarization distinction |
| Branch summarization | N/A | TunaCode has no tree navigation |
| Extension hooks | PARTIAL | tinyagent has `transform_context` hook, unused |
| Token estimation (chars/4) | EXISTS | `utils/messaging/token_counter.py` -- identical heuristic |
| Cancellable compaction | MISSING | No abort controller for compaction |
| UI compaction indicator | MISSING | No compaction status in TUI |
| Overflow auto-retry | MISSING | No overflow error detection or recovery |

---

### Key Files That Already Exist

| File | Role in Compaction | Line References |
|---|---|---|
| [`src/tunacode/utils/messaging/token_counter.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/utils/messaging/token_counter.py) | Token estimation (chars/4 heuristic) -- ready to use for threshold checks |
| [`src/tunacode/core/agents/main.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/core/agents/main.py) | Agent loop -- `_run_impl()` is the insertion point for pre-request compaction. `_persist_agent_messages()` (L362-373) is where post-response compaction could trigger. |
| [`src/tunacode/core/agents/agent_components/agent_config.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/core/agents/agent_components/agent_config.py) | Agent construction -- `AgentOptions` (L286-290) does NOT set `transform_context`. This is where the hook would be wired. |
| [`src/tunacode/core/types/state_structures.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/core/types/state_structures.py) | `ConversationState` -- holds `messages`, `max_tokens`, `total_tokens`, `files_in_context`. `total_tokens` field exists but is never written to (always 0). |
| [`src/tunacode/core/session/state.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/core/session/state.py) | Session persistence -- `save_session()` (L233-259), `load_session()` (L261-309). Sessions are JSON files at `~/.local/share/tunacode/sessions/`. |
| [`src/tunacode/core/agents/resume/sanitize.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/core/agents/resume/sanitize.py) | Message sanitization -- handles dangling tool calls, empty responses, consecutive requests. Structural repair only, no size reduction. |
| [`src/tunacode/ui/commands/__init__.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/ui/commands/__init__.py) | Command system -- `/help`, `/clear`, `/debug`, `/model`, `/theme`, `/resume`, `/update`. Ready for `/compact` command. |
| [`src/tunacode/ui/widgets/resource_bar.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/ui/widgets/resource_bar.py) | Token usage display -- already shows estimated tokens vs max_tokens. Could show compaction status. |
| [`src/tunacode/ui/app.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/ui/app.py) | Main TUI app -- `_update_resource_bar()` (L371-382) estimates tokens for display. `_show_system_notice()` (L311) is the pattern for system messages. |
| [`src/tunacode/configuration/limits.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/configuration/limits.py) | Token limits config -- context window sizes per model. |
| [`src/tunacode/configuration/models_registry.json`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/configuration/models_registry.json) | Model registry -- context window sizes for all supported models. |
| [`src/tunacode/exceptions.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/exceptions.py) | Exception hierarchy -- no `ContextOverflowError` exists. |

### Deleted Files (Ghost .pyc Only)

These files once existed but were removed during the pydantic-ai migration. They may have contained early compaction logic:

- `core/agents/resume/summary.py` -- summarization logic (deleted)
- `core/agents/resume/prune.py` -- pruning logic (deleted)
- `core/agents/agent_components/truncation_checker.py` -- truncation checking (deleted)
- `core/agents/history_preparer.py` -- history preparation (deleted)
- `core/agents/agent_components/message_handler.py` -- message handling (deleted)

---

## Key Patterns / Solutions Found

### 1. TinyAgent `transform_context` Hook -- The Primary Integration Point

TinyAgent exposes `transform_context` in `AgentOptions` -- an async callback that receives the full message list before each LLM call and returns a (potentially modified) list. This is the designed injection point for compaction.

**Location:** `/home/tuna/tunacode/tinyAgent/tinyagent/agent.py` (AgentOptions dataclass)
**Called at:** `/home/tuna/tunacode/tinyAgent/tinyagent/agent_loop.py:107`

```python
if config.transform_context:
    messages = await config.transform_context(messages, signal)
```

TunaCode constructs `AgentOptions` at `src/tunacode/core/agents/agent_components/agent_config.py:286-290` but does NOT set `transform_context`. Wiring a compaction function here would intercept every LLM call with zero changes to tinyagent.

### 2. Message Flow: How Messages Accumulate

```
User types message
    |
    v
app.py -> process_request(message)
    |
    v
RequestOrchestrator._run_impl()
    |
    +-- conversation.messages -> agent.replace_messages(history)  [L312-316]
    +-- agent.stream(user_message)
    |       |  (inside tinyagent agent_loop.py)
    |       +-- Appends UserMessage
    |       +-- Calls LLM -> Appends AssistantMessage
    |       +-- If tool calls: Appends ToolResultMessages
    |       +-- Loops until no more tool calls
    |
    +-- _persist_agent_messages() [L362-373]
    |     conversation.messages = agent.state["messages"] + external
    |
    v
state_manager.save_session()  [JSON to disk]
```

Each user request can generate many messages (user + assistant + N tool calls + N tool results + follow-up assistant). Growth is bounded per-request only by `max_iterations` (default 15), but accumulates unboundedly across requests.

### 3. Token Estimation Infrastructure

`src/tunacode/utils/messaging/token_counter.py`:
- `estimate_tokens(text: str) -> int` -- `len(text) // 4`
- `estimate_message_tokens(message) -> int` -- converts to CanonicalMessage, counts all content
- `estimate_messages_tokens(messages) -> int` -- sums across all messages

Identical to pi-mono's chars/4 heuristic. Used only in `app.py:_update_resource_bar()`.

### 4. Context Window Configuration

`ConversationState.max_tokens` is set from the model registry's context window (default 200,000). The resource bar displays `estimated_tokens / max_tokens`. No code compares these values for enforcement.

### 5. Message Types (TinyAgent Format)

Three message roles in tinyagent:
- `UserMessage` -- `role: "user"`, content: text/image
- `AssistantMessage` -- `role: "assistant"`, content: text/thinking/tool_call, has `usage` and `stop_reason`
- `ToolResultMessage` -- `role: "tool_result"`, has `tool_call_id`, `tool_name`, `content`, `is_error`

Valid cut points for compaction: after `UserMessage` or after `AssistantMessage` (without pending tool calls). Never cut between a tool_call and its tool_result.

### 6. Session Persistence Format

Sessions are JSON files at `~/.local/share/tunacode/sessions/{project_id}_{session_id}.json`:
```json
{
  "version": 1,
  "session_id": "...",
  "project_id": "...",
  "created_at": "...",
  "last_modified": "...",
  "working_directory": "...",
  "current_model": "...",
  "session_total_usage": {...},
  "thoughts": [...],
  "messages": [...]
}
```

Compaction state will be stored as a new top-level `"compaction"` field (see Architecture section). Old sessions without this field default to `None` -- no migration needed.

---

## Architecture for Compaction Implementation

> **Council Review (2026-02-10):** Reviewed by Codex (structural integrity), Gemini (conceptual clarity), and Qwen (pragmatic longevity). All recommendations accepted. Decisions locked below.

### Design Decisions (Locked)

| Decision | Choice | Rationale |
|---|---|---|
| Compaction model | Same as conversation model | Simplicity; one model to reason about |
| State storage | Session-level metadata, NOT message list | Clean boundary between conversation history and compaction bookkeeping |
| Trigger strategy | CompactionController (pre-request + overflow retry) | Single entry point avoids double-compaction; post-response trigger dropped |
| LLM-facing format | Standard `UserMessage` injected by `transform_context` | No `convert_to_llm` override needed; no custom roles in the message stream |
| Fail-safe on summarization failure | Proceed with uncompacted context | Never silently swallow; log failure; if overflow also fails, surface error to user |
| File tracking | Owned by `ConversationState.files_in_context` | Not embedded in compaction types; passed as snapshot to summarizer |

### Trigger Architecture: CompactionController

A single `CompactionController` owns the policy: "should we compact?" It is invoked from two sites only:

1. **Pre-request (primary):** Called from `_run_impl()` before `agent.stream()`. Estimates tokens, compacts if above threshold, shows "Compacting..." in UI.
2. **Overflow retry (fallback):** Catches context overflow API errors, triggers compaction via the same controller, retries the request once.

The `transform_context` hook delegates to the controller. It does NOT independently decide to compact. This prevents double-compaction and state divergence.

```
User types message
    |
    v
RequestOrchestrator._run_impl()
    |
    +-- CompactionController.check_and_compact(conversation)
    |     |
    |     +-- estimate_tokens(messages)
    |     +-- if above threshold:
    |     |     +-- calculate retention window
    |     |     +-- serialize compactable messages
    |     |     +-- call summarizer LLM (same model)
    |     |     +-- store CompactionRecord in session metadata
    |     |     +-- replace old messages with summary UserMessage
    |     |     +-- show "Compacting..." UI status
    |     +-- if summarization fails:
    |           +-- log error, proceed with full context (fail-safe)
    |
    +-- conversation.messages -> agent.replace_messages(history)
    +-- agent.stream(user_message)
    |       |
    |       +-- transform_context hook:
    |       |     delegates to CompactionController (no-op if already compacted)
    |       +-- LLM call
    |       +-- tool calls / results loop
    |
    +-- if ContextOverflowError:
    |     +-- CompactionController.force_compact(conversation)
    |     +-- retry agent.stream() once
    |
    +-- _persist_agent_messages()
    v
state_manager.save_session()
```

### Compaction State: Session-Level Metadata (NOT Message List)

Compaction bookkeeping lives in a `CompactionRecord` persisted as a top-level field in the session JSON. The message list stays pure -- only `user`, `assistant`, `tool_result` roles.

**Session format after compaction:**
```json
{
  "version": 1,
  "session_id": "...",
  "messages": [
    {"role": "user", "content": [{"type": "text", "text": "...summary injected at runtime..."}]},
    {"role": "user", "content": [{"type": "text", "text": "Now update the tests"}]},
    {"role": "assistant", "content": [{"type": "text", "text": "I'll update..."}]}
  ],
  "compaction": {
    "summary": "## Goal\nUser is refactoring auth module...",
    "compacted_message_count": 47,
    "tokens_before": 150000,
    "tokens_after": 25000,
    "compaction_count": 1,
    "previous_summary": null,
    "last_compacted_at": "2026-02-10T21:30:00Z"
  }
}
```

**How the summary reaches the LLM:**

1. `CompactionRecord` is stored in session metadata (not in messages)
2. `transform_context` reads the record and **injects a synthetic `UserMessage`** containing the summary text at the front of the message list
3. This injected message is transient -- never persisted back to the message list
4. The LLM sees: `[summary UserMessage] + [recent real messages]`
5. No `convert_to_llm` override needed. No custom roles. Standard message types only.

**Migration:** Old sessions without a `"compaction"` field get `None` default. No migration logic needed.

**Iterative updates:** On subsequent compactions, the existing record's `summary` becomes `previous_summary`. The summarizer receives both the old summary and new messages to produce an updated summary. File tracking comes from `ConversationState.files_in_context`, not from the compaction record.

### Components to Build

| Component | Location | Description |
|---|---|---|
| `CompactionRecord` | `src/tunacode/core/compaction/types.py` | Dataclass for compaction metadata stored in session (summary, counts, timestamps) |
| `CompactionController` | `src/tunacode/core/compaction/controller.py` | Single entry point: threshold check, retention window calc, orchestrates summarization, fail-safe logic |
| `ContextSummarizer` | `src/tunacode/core/compaction/summarizer.py` | Pure logic: retention window calculation, message serialization, LLM summarization call |
| `CompactionPrompts` | `src/tunacode/core/compaction/prompts.py` | Summarization and iterative update prompts |
| `ContextOverflowError` | `src/tunacode/exceptions.py` | New exception for overflow detection |
| `CompactCommand` | `src/tunacode/ui/commands/compact.py` | `/compact` slash command for manual trigger |
| `transform_context` wiring | `src/tunacode/core/agents/agent_components/agent_config.py` | Wire `transform_context` to delegate to CompactionController |
| Controller integration | `src/tunacode/core/agents/main.py` | Pre-request check + overflow retry via CompactionController |
| Session persistence | `src/tunacode/core/session/state.py` | Add optional `compaction` field to session save/load |
| UI indicators | `src/tunacode/ui/app.py`, `resource_bar.py` | "Compacting..." status, compaction notice display |

### Configuration Parameters

| Parameter | Default | Description |
|---|---|---|
| `reserve_tokens` | 16,384 | Space reserved for LLM response |
| `keep_recent_tokens` | 20,000 | Recent context to keep unsummarized |
| `auto_compact` | `true` | Whether to auto-compact on threshold |
| `compact_on_overflow` | `true` | Whether to compact + retry on overflow |

Note: `compaction_model` removed -- always uses the current conversation model.

### Retention Window Calculation

The algorithm determines what to **keep**, not where to cut. Walk backwards from the newest message, accumulating estimated tokens. Stop when accumulated >= `keep_recent_tokens`. Snap to the nearest valid boundary.

Valid boundaries:
- After a `UserMessage`
- After an `AssistantMessage` with `stop_reason != None` (completed response)

Never split:
- Between a tool_call (in AssistantMessage.content) and its ToolResultMessage
- At an aborted message (`stop_reason == "aborted"`)

Everything before the retention window boundary is serialized and summarized. Everything after it is kept as-is.

### Message Serialization for Summarizer

Convert messages outside the retention window to text format for the summarizer LLM:

```
[User]: What they said
[Assistant]: Response text
[Tool Call]: tool_name(arg1="val1", arg2="val2")
[Tool Result]: Output text (truncated to 500 chars)
[Assistant]: Follow-up response
```

Tool results should be truncated aggressively -- the summarizer only needs the gist, not the full output.

### Structured Summary Format (Adapted for TunaCode)

```markdown
## Goal
[What the user is trying to accomplish]

## Constraints & Preferences
- [Requirements gathered from conversation]

## Progress
### Done
- [x] Completed actions with file paths
### In Progress
- [ ] Current work

## Key Decisions
- **[Decision]**: [Rationale]

## Next Steps
1. [What should happen next]

## Files Touched
### Read
- path/to/file.py
### Modified
- path/to/changed.py

## Critical Context
- [Data the assistant needs to continue effectively]
```

### Fail-Safe Behavior

When summarization fails (LLM error, timeout, rate limit):

1. **Log the failure** with full error context
2. **Proceed with uncompacted context** -- send the full message list to the LLM
3. If the LLM call also fails with overflow: surface `ContextOverflowError` to the user via `_show_system_notice()` with message: "Context too large. Compaction failed. Use /compact to retry manually."
4. Never silently swallow a compaction failure
5. Never retry summarization automatically -- one attempt per trigger

When the user cancels (abort signal during `transform_context`):

1. Abort the summarization LLM call
2. Proceed with uncompacted context (fail-safe)
3. Do not surface an error -- the user chose to cancel

---

## Knowledge Gaps

- **tinyagent `transform_context` behavior under abort**: Does the abort signal in `transform_context(messages, signal)` properly cancel an in-flight compaction LLM call? Need to verify signal propagation.
- **OpenRouter error format for context overflow**: Need to verify the exact error response format from OpenRouter when context is exceeded (likely `context_length_exceeded` in the error type or code field).
- **Performance of chars/4 for compaction threshold**: The heuristic overestimates by ~20-30%. For compaction threshold, this is acceptable (triggers early rather than late), but actual token counts from `usage` would be more precise.

## References

- Pi-mono compaction reference: [`memory-bank/research/2026-02-07_18-06-58_compaction-system.md`](memory-bank/research/2026-02-07_18-06-58_compaction-system.md)
- Token counter: [`src/tunacode/utils/messaging/token_counter.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/utils/messaging/token_counter.py)
- Agent loop: [`src/tunacode/core/agents/main.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/core/agents/main.py)
- Agent config (transform_context wiring): [`src/tunacode/core/agents/agent_components/agent_config.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/core/agents/agent_components/agent_config.py)
- Session state: [`src/tunacode/core/session/state.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/core/session/state.py)
- Conversation state: [`src/tunacode/core/types/state_structures.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/core/types/state_structures.py)
- TinyAgent agent loop: [`tinyAgent/tinyagent/agent_loop.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/tinyAgent/tinyagent/agent_loop.py)
- TinyAgent agent: [`tinyAgent/tinyagent/agent.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/tinyAgent/tinyagent/agent.py)
- Resume sanitizer: [`src/tunacode/core/agents/resume/sanitize.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/core/agents/resume/sanitize.py)
- UI commands: [`src/tunacode/ui/commands/__init__.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/ui/commands/__init__.py)
- Exceptions: [`src/tunacode/exceptions.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/exceptions.py)
- Resource bar: [`src/tunacode/ui/widgets/resource_bar.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/ui/widgets/resource_bar.py)
- App: [`src/tunacode/ui/app.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/a454860b/src/tunacode/ui/app.py)
