# Research - node_processor.py Mapping

**Date:** 2026-01-12
**Owner:** agent
**Phase:** Research
**Git Commit:** 642830f

## Goal

Map out `node_processor.py` as it exists today - documenting its current structure, responsibilities, and dependencies before rewrite.

## Overview

`node_processor.py` is a 486-line module with **two exported functions** that have accumulated multiple responsibilities over time. It's the central node processing engine but has become a "kitchen sink" for response handling.

**Location:** `src/tunacode/core/agents/agent_components/node_processor.py`

## Findings

### Single Caller

Only ONE file calls `_process_node`:

| File | Line | Usage |
|------|------|-------|
| `src/tunacode/core/agents/main.py` | 403 | `empty_response, empty_reason = await ac._process_node(...)` |

Uses private access (`# noqa: SLF001`).

### Functions Defined

| Function | Lines | LOC | Purpose |
|----------|-------|-----|---------|
| `_normalize_tool_args` | 29-33 | 5 | Parse raw args via `parse_args()` |
| `_record_tool_call_args` | 36-42 | 7 | Store args by tool_call_id |
| `_consume_tool_call_args` | 45-52 | 8 | Pop args by tool_call_id |
| `_has_tool_calls` | 55-56 | 2 | Check if parts have TOOL_CALL |
| `_extract_fallback_tool_calls` | 62-127 | 66 | Parse tools from text (Qwen2/Hermes) |
| `_update_token_usage` | 130-156 | 27 | Track prompt/completion tokens + cost |
| `_process_node` | 158-339 | 182 | **MAIN** - Process single node |
| `_process_tool_calls` | 342-485 | 144 | Process all tool calls in node |

**Total:** 441 lines of logic (486 - imports/constants/whitespace)

### State Mutations

`_process_node` and `_process_tool_calls` mutate **7 different state locations**:

```
state_manager.session.messages              # Appends request, thought, model_response
state_manager.session.tool_call_args_by_id  # Write: record args, Read: consume args
state_manager.session.last_call_usage       # prompt_tokens, completion_tokens, cost
state_manager.session.session_total_usage   # Accumulates totals
state_manager.session.tool_calls            # Appends tool metadata
state_manager.session.batch_counter         # Increments for read-only batches
state_manager.session.total_tokens          # Via update_token_count()
```

### State Machine Transitions

Controls `ResponseState` through 7 transition points:

```
Line 184-185:  USER_INPUT → ASSISTANT      (node start)
Line 109-110:  ASSISTANT → TOOL_EXECUTION  (fallback tools)
Line 380-381:  ASSISTANT → TOOL_EXECUTION  (structured tools)
Line 286-288:  ASSISTANT → RESPONSE        (completion marker)
Line 322-326:  ASSISTANT → RESPONSE        (no tools, done)
Line 470-475:  TOOL_EXECUTION → RESPONSE   (tools done)
```

### Callbacks Accepted

| Parameter | Type | Purpose |
|-----------|------|---------|
| `tool_callback` | `Callable[[Any, Any], Awaitable[None]]` | Execute tool |
| `streaming_callback` | `Callable[[str], Awaitable[None]]` | Stream tokens |
| `tool_result_callback` | `Callable[..., None]` | Display tool result |
| `tool_start_callback` | `Callable[[str], None]` | Show tool starting |

### Dependencies (Same Directory)

| File | Import | Purpose |
|------|--------|---------|
| `response_state.py` | `ResponseState` | State machine wrapper |
| `task_completion.py` | `check_task_completion` | Detect completion markers |
| `tool_buffer.py` | `ToolBuffer` | Batch read-only tools |
| `truncation_checker.py` | `check_for_truncation` | Detect truncated responses |
| `tool_executor.py` | `execute_tools_parallel` | Run tools in parallel |

### External Dependencies

```python
from tunacode.constants import ERROR_TOOL_ARGS_MISSING, ERROR_TOOL_CALL_ID_MISSING, UI_COLORS, READ_ONLY_TOOLS
from tunacode.core.logging import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import StateError, UserAbortError
from tunacode.types import AgentState, ToolArgs, ToolCallId
from tunacode.utils.ui import DotDict
from tunacode.utils.parsing.command_parser import parse_args
from tunacode.utils.parsing.tool_parser import has_potential_tool_call, parse_tool_calls_from_text
from tunacode.configuration.pricing import calculate_cost, get_model_pricing
from pydantic_ai.messages import ToolCallPart
```

## Key Patterns / Solutions Found

### Smart Batching (Lines 354-476)

```
Phase 1: Collect and categorize all tools
Phase 2: Execute research_codebase first (single)
Phase 3: Execute ALL read-only tools in ONE parallel batch
Phase 4: Execute write/execute tools sequentially
```

### Premature Completion Detection (Lines 245-280)

Checks for "intention phrases" to prevent early completion:
- `let me`, `i'll check`, `going to`, `about to`, `let me search`...

Also checks action verb endings:
- `checking`, `searching`, `looking`, `finding`, `reading`, `analyzing`

### Fallback Tool Parsing (Lines 62-127)

When no structured `part_kind == "tool-call"` found, parses text content for embedded tool calls (Qwen2/Hermes format). Creates synthetic `ToolCallPart` objects.

### Return Values

`_process_node` returns `tuple[bool, str | None]`:
- `(False, None)` - Normal response
- `(True, "empty")` - Empty response, no tools
- `(True, "truncated")` - Response appears truncated
- `(True, "intention_without_action")` - Said "let me" but no tool call

## Knowledge Gaps

1. **Why private function?** `_process_node` is exported but prefixed with `_`
2. **ToolBuffer unused?** Passed in but smart batching collects its own lists
3. **Streaming callback unused?** Passed through but not called in this module
4. **Why both ResponseState AND manual flags?** Dual tracking seems redundant

## Responsibilities (Too Many)

This module handles **8 distinct concerns**:

1. **Message History** - Append request/thought/response to session
2. **Token Tracking** - Update usage statistics and cost
3. **Tool Args Registry** - Record and consume tool_call_id → args mapping
4. **Completion Detection** - Check for task completion markers
5. **Truncation Detection** - Check for incomplete responses
6. **State Transitions** - Manage ResponseState machine
7. **Tool Batching** - Categorize and batch tool calls
8. **Tool Execution** - Dispatch tools (parallel/sequential)

**Recommendation:** Split into focused modules per concern.

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        _process_node()                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Transition USER_INPUT → ASSISTANT                           │
│                     ↓                                           │
│  2. Append node.request to messages                             │
│                     ↓                                           │
│  3. Display TOOL_RETURN results (from prior iteration)          │
│                     ↓                                           │
│  4. Append node.thought to messages (if present)                │
│                     ↓                                           │
│  5. Append node.model_response to messages                      │
│                     ↓                                           │
│  6. _update_token_usage() → cost + token tracking               │
│                     ↓                                           │
│  7. session.update_token_count()                                │
│                     ↓                                           │
│  8. Scan for completion markers (check_task_completion)         │
│          ↓                              ↓                       │
│     [marker found]              [no marker]                     │
│          ↓                              ↓                       │
│     Set completion             Continue to tools                │
│          ↓                              ↓                       │
│  9. check_for_truncation()                                      │
│                     ↓                                           │
│  10. _process_tool_calls() ─────────────────────────────┐       │
│                                                         │       │
└─────────────────────────────────────────────────────────│───────┘
                                                          │
┌─────────────────────────────────────────────────────────▼───────┐
│                     _process_tool_calls()                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: Collect all tool calls from response parts            │
│           Categorize: research / read-only / write-execute      │
│                     ↓                                           │
│  Phase 1.5: If no structured calls, try fallback parsing        │
│                     ↓                                           │
│  Phase 2: Execute research_codebase (if any)                    │
│                     ↓                                           │
│  Phase 3: Execute ALL read-only tools in ONE parallel batch     │
│           batch_counter++                                       │
│                     ↓                                           │
│  Phase 4: Execute write/execute tools sequentially              │
│                     ↓                                           │
│  Record all tool calls to session.tool_calls                    │
│                     ↓                                           │
│  Transition TOOL_EXECUTION → RESPONSE                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## References

- `src/tunacode/core/agents/agent_components/node_processor.py` - This file
- `src/tunacode/core/agents/main.py:403` - Only caller
- `src/tunacode/core/agents/agent_components/__init__.py:17` - Export
- `docs/codebase-map/modules/core-agents.md` - Documentation
