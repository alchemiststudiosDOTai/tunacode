---
title: Message History Sanitization
link: core-sanitize
type: module
path: src/tunacode/core/agents/resume/sanitize.py
depth: 0
seams: [S] state, [D] data
---

# Message History Sanitization

> **Status**: Working but scheduled for rewrite. This document maps the current implementation.

## Where

```
src/tunacode/core/agents/resume/sanitize.py
```

## What

Functions to clean up corrupt or inconsistent message history that can occur from abort scenarios, preventing API errors on subsequent requests.

**Key cleanup operations:**
- Remove dangling tool calls (no matching tool return)
- Remove empty responses (abort during response generation)
- Remove consecutive requests (abort before model responds)
- Strip system prompts (pydantic-ai injects these automatically)

## Why

When a user aborts mid-operation, message history can end up in invalid states:

| Abort Scenario | Resulting Corruption | Fix |
|---------------|---------------------|-----|
| During tool execution | Tool call without return | `remove_dangling_tool_calls()` |
| During response generation | Empty response message | `remove_empty_responses()` |
| Before model responds | Consecutive request messages | `remove_consecutive_requests()` |
| Session resume | Duplicate system prompts | `sanitize_history_for_resume()` |

Without cleanup, the next API request fails with format errors.

---

## Module Map

```
sanitize.py
├── Constants
│   ├── PART_KIND_TOOL_CALL = "tool-call"
│   ├── PART_KIND_SYSTEM_PROMPT = "system-prompt"
│   ├── MESSAGE_KIND_REQUEST = "request"
│   ├── MESSAGE_KIND_RESPONSE = "response"
│   └── MAX_CLEANUP_ITERATIONS = 10
│
├── Mutation Helpers (internal)
│   ├── _set_message_parts()
│   ├── _set_message_tool_calls()
│   ├── _normalize_list()
│   └── _get_message_tool_calls()
│
├── Dangling Tool Call Handling
│   ├── find_dangling_tool_call_ids()      → delegates to adapter
│   ├── _filter_dangling_tool_calls_from_parts()
│   ├── _filter_dangling_tool_calls_from_tool_calls()
│   ├── _strip_dangling_tool_calls_from_message()
│   └── remove_dangling_tool_calls()       → PUBLIC
│
├── Message Cleanup
│   ├── remove_consecutive_requests()      → PUBLIC
│   └── remove_empty_responses()           → PUBLIC
│
├── System Prompt Stripping
│   ├── _strip_system_prompt_parts()
│   └── sanitize_history_for_resume()      → PUBLIC
│
└── Orchestrator
    └── run_cleanup_loop()                 → PUBLIC (main entry point)
```

---

## Public API

### `run_cleanup_loop(messages, tool_call_args_by_id)`

**Main entry point.** Runs iterative cleanup until message history stabilizes.

```python
def run_cleanup_loop(
    messages: list[Any],
    tool_call_args_by_id: dict[ToolCallId, ToolArgs],
) -> tuple[bool, set[ToolCallId]]
```

**Why iterative?** Each cleanup pass can expose new issues:
- Removing dangling tool calls may create consecutive requests
- Removing consecutive requests may orphan tool returns

**Returns:** `(any_cleanup_applied, final_dangling_tool_call_ids)`

**Mutates:** Both `messages` and `tool_call_args_by_id` in place.

---

### `remove_dangling_tool_calls(messages, tool_call_args_by_id, dangling_ids=None)`

Removes tool calls that never received tool returns.

```python
def remove_dangling_tool_calls(
    messages: list[Any],
    tool_call_args_by_id: dict[ToolCallId, ToolArgs],
    dangling_tool_call_ids: set[ToolCallId] | None = None,
) -> bool
```

**Key insight:** Filters ANY part with `tool_call_id` matching a dangling ID, not just `tool-call` parts. This handles:
- `tool-call` parts (original invocation)
- `tool-return` parts (result)
- `retry-prompt` parts (pydantic-ai error response)

**Returns:** `True` if any cleanup was performed.

---

### `remove_empty_responses(messages)`

Removes response messages with zero parts.

```python
def remove_empty_responses(messages: list[Any]) -> bool
```

Empty responses occur when abort happens after model starts responding but before any content is generated.

---

### `remove_consecutive_requests(messages)`

Removes consecutive request messages, keeping only the last in each run.

```python
def remove_consecutive_requests(messages: list[Any]) -> bool
```

The API expects alternating request/response messages. Consecutive requests occur when abort happens before model responds.

---

### `sanitize_history_for_resume(messages)`

Sanitizes message history for session resume compatibility.

```python
def sanitize_history_for_resume(messages: list[Any]) -> list[Any]
```

**Operations:**
1. Removes `run_id` (binds messages to previous sessions)
2. Strips `system-prompt` parts (pydantic-ai injects these automatically)
3. Removes empty messages resulting from stripping

**Returns:** New sanitized list (does not mutate input).

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Abort / Error                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Corrupt Message History                       │
│  - Dangling tool calls (tool-call without tool-return)          │
│  - Empty responses (parts=[])                                   │
│  - Consecutive requests (request, request, request)             │
│  - Orphaned retry-prompt parts                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    run_cleanup_loop()                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Iteration 1..N (max 10)                                   │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │ 1. find_dangling_tool_call_ids()                     │  │ │
│  │  │ 2. remove_dangling_tool_calls()                      │  │ │
│  │  │ 3. remove_empty_responses()                          │  │ │
│  │  │ 4. remove_consecutive_requests()                     │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │  Loop until no changes                                     │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Valid Message History                         │
│  - Every tool-call has a tool-return                            │
│  - No empty responses                                           │
│  - Alternating request/response                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## pydantic-ai Part Types

The module handles multiple pydantic-ai message part kinds:

| Part Kind | Description | Has `tool_call_id` |
|-----------|-------------|-------------------|
| `text` | Plain text content | No |
| `user-prompt` | User input | No |
| `system-prompt` | System instructions | No |
| `tool-call` | Tool invocation | Yes |
| `tool-return` | Successful tool result | Yes |
| `retry-prompt` | Error response for failed tools | Yes |

**Critical:** All parts with `tool_call_id` must be pruned together when a tool call is dangling.

---

## Message Format Handling

The module handles two message formats:

### 1. pydantic-ai Objects (runtime)

```python
# ModelRequest / ModelResponse objects
msg.kind        # "request" or "response"
msg.parts       # list of part objects
msg.run_id      # session binding (remove on resume)
part.part_kind  # "tool-call", "text", etc.
part.tool_call_id  # for tool-related parts
```

**Mutation:** Uses `dataclasses.replace()` to create new immutable objects.

### 2. Dict Messages (serialized sessions)

```python
# From JSON session files
msg["kind"]
msg["parts"]
msg["tool_calls"]  # legacy, computed from parts in pydantic-ai
```

**Mutation:** Direct dict mutation.

---

## Dependencies

```python
from tunacode.core.logging import get_logger
from tunacode.types import ToolArgs, ToolCallId
from tunacode.utils.messaging import (
    _get_attr,           # Polymorphic attribute access
    _get_parts,          # Extract parts from any message format
    find_dangling_tool_calls,  # Detection (adapter handles polymorphism)
)
```

**Design:** Detection delegates to `adapter.find_dangling_tool_calls()`. Mutation stays in `sanitize.py`.

---

## Usage Example

```python
from tunacode.core.agents.resume.sanitize import (
    run_cleanup_loop,
    sanitize_history_for_resume,
)

# On session resume
messages = sanitize_history_for_resume(loaded_messages)

# On abort/error during agent loop
cleanup_applied, dangling_ids = run_cleanup_loop(
    messages,
    tool_call_args_by_id,
)
if cleanup_applied:
    logger.lifecycle("Cleaned up corrupt message history")
```

---

## Known Issues / Future Work

1. **Rewrite planned:** Current implementation handles multiple concerns. Future refactor should separate:
   - Detection (read-only analysis)
   - Mutation (history modification)
   - Orchestration (cleanup loop)

2. **Message format polymorphism:** The module handles both pydantic-ai objects and dicts. The adapter layer should eventually eliminate this dual handling.

3. **Iteration limit:** `MAX_CLEANUP_ITERATIONS = 10` is a safety valve. If cleanup doesn't stabilize, there may be a deeper invariant violation.

---

## Related

- [[adapter.py]] - Message format conversion and detection
- [[core-state.md]] - SessionState that holds message history
- [[core-agents.md]] - Agent loop that calls cleanup on abort
- PR #246 - Original dangling tool calls fix
- Delta: `orphaned-retry-prompt-dangling-cleanup` - retry-prompt fix
