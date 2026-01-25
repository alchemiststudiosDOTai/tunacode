# Message Flow Behavioral Map

This document traces message handling from entry to exit, documenting the single source of truth pattern.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MESSAGE FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌───────────────┐    ┌────────────────┐    ┌──────────┐  │
│  │ pydantic │ -> │   adapter.py  │ -> │ CanonicalTypes │ -> │  tunacode │  │
│  │   -ai    │    │ to_canonical()│    │                │    │   core    │  │
│  └──────────┘    └───────────────┘    └────────────────┘    └──────────┘  │
│       ▲                                      │                     │       │
│       │              ┌───────────────┐       │                     │       │
│       └──────────────│ from_canonic │<──────┘                     │       │
│                      │    al()      │                              │       │
│                      └───────────────┘                             ▼       │
│                                                            ┌──────────┐    │
│                                                            │   UI     │    │
│                                                            └──────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Single Source of Truth: `parts`

**Key insight**: There is only ONE source of truth for message content - the `parts` list.

```
pydantic-ai ModelResponse
├── parts: list[Part]           <-- SINGLE SOURCE OF TRUTH
│   ├── TextPart
│   ├── ToolCallPart            <-- Tool calls live HERE
│   └── ToolReturnPart          <-- Tool returns live HERE
│
└── tool_calls (property)       <-- COMPUTED from parts, not separate data
```

The `tool_calls` property on pydantic-ai objects is a computed property that iterates `parts` and filters for `ToolCallPart`. It is NOT a separate data store.

## Entry Points

### 1. From pydantic-ai Agent

```python
# In core/agent_runner.py (conceptual)
async for node in agent.iter(prompt, message_history=messages):
    response: ModelResponse = node.response

    # Response contains parts with tool calls
    # parts: [TextPart("Let me read that"), ToolCallPart(id="tc_1", ...)]
```

### 2. From Serialized Session (JSON)

```python
# Session loading from JSON
{
    "kind": "response",
    "parts": [
        {"part_kind": "text", "content": "Let me help"},
        {"part_kind": "tool-call", "tool_call_id": "tc_1", "tool_name": "bash", "args": {...}}
    ]
}
```

### 3. From Legacy Dict Formats

```python
# Old format (still supported)
{"content": "Hello world"}
{"thought": "I should think about this"}
```

## Conversion Flow

### Forward: pydantic-ai → Canonical

```
to_canonical(message)
     │
     ▼
┌────────────────────────────────────────────┐
│ 1. Check for legacy formats (thought, content)  │
│    - {"thought": ...} → ThoughtPart             │
│    - {"content": ...} → TextPart                │
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 2. Determine role from message kind            │
│    - "request" → MessageRole.USER              │
│    - "response" → MessageRole.ASSISTANT        │
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 3. Extract parts (SINGLE SOURCE OF TRUTH)      │
│    - _get_parts(message) returns parts list    │
│    - Each part converted by _convert_part()    │
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 4. Convert each part to canonical              │
│    - "text" → TextPart                         │
│    - "user-prompt" → TextPart                  │
│    - "tool-call" → ToolCallPart                │
│    - "tool-return" → ToolReturnPart            │
│    - "system-prompt" → SystemPromptPart        │
└────────────────────────────────────────────┘
     │
     ▼
  CanonicalMessage(role, parts=tuple(...))
```

### Backward: Canonical → pydantic-ai

```
from_canonical(canonical_message)
     │
     ▼
┌────────────────────────────────────────────┐
│ 1. Determine kind from role                    │
│    - USER/SYSTEM → "request"                   │
│    - ASSISTANT → "response"                    │
└────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────┐
│ 2. Convert each canonical part to dict         │
│    - TextPart → {"part_kind": "text", ...}     │
│    - ToolCallPart → {"part_kind": "tool-call"} │
│    - etc.                                      │
└────────────────────────────────────────────┘
     │
     ▼
  {"kind": "request|response", "parts": [...]}
```

## Tool Call Lifecycle

### Detection

```python
get_tool_call_ids(message) -> set[str]
    │
    ▼
to_canonical(message)
    │
    ▼
message.get_tool_call_ids()
    │
    ▼
[part.tool_call_id for part in parts if isinstance(part, ToolCallPart)]
```

### Matching Returns

```python
get_tool_return_ids(message) -> set[str]
    │
    ▼
[part.tool_call_id for part in parts if isinstance(part, ToolReturnPart)]
```

### Dangling Detection

A "dangling" tool call is one that has no matching tool return.

```python
find_dangling_tool_calls(messages: list) -> set[str]
    │
    ▼
┌────────────────────────────────────────────┐
│ For each message:                              │
│   call_ids.update(get_tool_call_ids(msg))      │
│   return_ids.update(get_tool_return_ids(msg))  │
└────────────────────────────────────────────┘
    │
    ▼
return call_ids - return_ids  # IDs with no return
```

**When dangling occurs:**
- User aborts mid-tool-execution
- Network failure during tool call
- Session restored from interrupted state

**Resolution:**
```python
# In sanitize.py or abort handler
dangling = find_dangling_tool_calls(messages)
if dangling:
    # Inject synthetic tool returns
    for tool_call_id in dangling:
        messages.append({
            "kind": "request",
            "parts": [{
                "part_kind": "tool-return",
                "tool_call_id": tool_call_id,
                "content": "[Aborted by user]"
            }]
        })
```

## Content Extraction

```python
get_content(message) -> str
    │
    ├── if CanonicalMessage: message.get_text_content()
    │
    └── else: to_canonical(message).get_text_content()
           │
           ▼
    " ".join(
        part.content
        for part in parts
        if isinstance(part, (TextPart, ThoughtPart))
    )
```

## Invariants

These must always be true:

1. **Parts is the only source**: All tool call data comes from `parts`, never from computed properties
2. **Every tool call needs a return**: Before sending to API, all tool calls must have matching returns
3. **Immutable canonical types**: Once created, `CanonicalMessage` and parts are frozen
4. **Role consistency**: `kind="request"` → USER role, `kind="response"` → ASSISTANT role

## Files

| File | Purpose |
|------|---------|
| `src/tunacode/types/canonical.py` | Canonical type definitions |
| `src/tunacode/utils/messaging/adapter.py` | Bidirectional conversion |
| `tests/unit/types/test_adapter.py` | Adapter tests |
| `tests/unit/types/test_canonical.py` | Canonical type tests |

## Tool Call Registry (Chunk 5)

Tool call lifecycle state now lives in `session.runtime.tool_registry`, which stores
`CanonicalToolCall` entries keyed by `tool_call_id`. ReAct guidance and JSON export
consume the registry instead of a standalone `tool_calls` list.
