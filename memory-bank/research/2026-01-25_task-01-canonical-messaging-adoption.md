# Research – Task 01: Canonical Messaging Adoption

**Date:** 2026-01-25
**Owner:** Claude (research agent)
**Phase:** Research

## Goal

Identify all runtime message access patterns, understand the canonical adapter capabilities, and determine what changes are needed to adopt the canonical message model across production code paths.

## Executive Summary

**Critical Finding:** The canonical types (`CanonicalMessage`, `CanonicalPart`) and adapter layer exist with strong test coverage, but **runtime code still uses legacy accessors**. Only 3 production calls to `get_message_content()` need direct replacement, but **polymorphic patterns are scattered across the resume/ module** (prune.py, summary.py, sanitize.py) which contains 631 lines of complex message handling.

**Adoption Scope:**
| Category | Files | LOC (approx) | Priority |
|----------|-------|--------------|----------|
| **Direct legacy accessor calls** | 3 files | 3 calls | High (simple wins) |
| **Polymorphic patterns in resume/** | 3 files | 631 lines | Medium (significant refactor) |
| **Direct pydantic-ai type usage** | 15+ files | N/A | Low (mostly appropriate) |

---

## Additional Search

```bash
grep -ri "canonical\|adapter" .claude/ 2>/dev/null | grep -E "\.(md|py)$"
```

Results:
- `.claude/task/task_01_canonical_messaging_adoption.md` - Task definition
- `.claude/task/task_03_message_parity_harness.md` - Related parity task
- `.claude/task/task_04_canonical_sanitization.md` - Related sanitization task

---

## Findings

### 1. Legacy Accessor Calls (Simple Wins)

**`get_message_content()` from `message_utils.py` is called in 3 production locations:**

| File | Line | Context | Migration Path |
|------|------|---------|----------------|
| `src/tunacode/core/state.py` | 123 | `_calculate_token_count()` | Replace with `adapter.get_content()` |
| `src/tunacode/ui/app.py` | 355 | `_replay_session_messages()` | Replace with `adapter.get_content()` |
| `src/tunacode/ui/headless/output.py` | 50 | `render_message()` | Replace with `adapter.get_content()` |

**Import locations:**
- `src/tunacode/core/state.py:28` - `from tunacode.utils.messaging.message_utils import get_message_content`
- `src/tunacode/ui/app.py:352` - imported inside function
- `src/tunacode/ui/headless/output.py:7` - imported at module level

**Migration Strategy:**
```python
# Before
from tunacode.utils.messaging.message_utils import get_message_content
content = get_message_content(message)

# After
from tunacode.utils.messaging.adapter import get_content
content = get_content(message)
```

---

### 2. Polymorphic Patterns in Resume Module (Complex)

**Files with heavy polymorphic patterns:**

| File | Pattern | Line Examples |
|------|---------|---------------|
| `src/tunacode/core/agents/resume/sanitize.py` | `isinstance(dict)`, `getattr(part, "part_kind")` | 84, 104, 124, 161, 241, 323 |
| `src/tunacode/core/agents/resume/prune.py` | `hasattr(message, "parts")`, `is_tool_return_part()` | 55, 73, 92, 93, 118, 141, 158, 199 |
| `src/tunacode/core/agents/resume/summary.py` | `isinstance(dict)`, `hasattr(message, "parts")` | 75, 88, 89, 116, 120, 121, 164 |

**`sanitize.py` (631 lines) is the largest blocker:**
- Lines 58-94: Custom `_get_attr_value()`, `_get_message_parts()`, `_get_message_tool_calls()`
- Lines 116-178: Tool call ID collection with separate dict/object paths
- Lines 228-343: Dangling tool call removal with polymorphic handling
- **All of this could be replaced with canonical adapter functions**

**Example of polymorphic pattern in `sanitize.py:84-104`:**
```python
def _get_message_tool_calls(message: ModelMessage) -> list[ToolCallPart]:
    """Extract tool calls from a message, handling both dict and object formats."""
    if isinstance(message, dict):
        # Dict path
        if "parts" in message:
            parts = message["parts"]
        elif "tool_calls" in message:
            tool_calls = message["tool_calls"]
            return [tc for tc in tool_calls if isinstance(tc, ToolCallPart)]
        else:
            return []
    else:
        # Object path
        if hasattr(message, "parts"):
            parts = message.parts
        elif hasattr(message, "tool_calls"):
            tool_calls = message.tool_calls
            return [tc for tc in tool_calls if isinstance(tc, ToolCallPart)]
        else:
            return []
    # ... then filter by part_kind == "tool-call"
```

**Canonical equivalent (1 line):**
```python
from tunacode.utils.messaging.adapter import get_tool_call_ids
tool_call_ids = get_tool_call_ids(message)
```

---

### 3. Adapter Layer Capabilities

**Location:** `src/tunacode/utils/messaging/adapter.py` (315 lines)

| Function | Line | Purpose | Replaces |
|----------|------|---------|----------|
| `to_canonical()` | 136 | Convert any message format to `CanonicalMessage` | Polymorphic parsing |
| `from_canonical()` | 205 | Convert `CanonicalMessage` to dict for pydantic-ai | Serialization |
| `get_content()` | 261 | Extract text content from any message format | `get_message_content()` |
| `get_tool_call_ids()` | 276 | Extract tool call IDs from any message | Custom extraction logic |
| `get_tool_return_ids()` | 283 | Extract tool return IDs from any message | Custom extraction logic |
| `find_dangling_tool_calls()` | 290 | Detect orphaned tool calls | Manual diff logic |

**Accepted Input Formats:**
| Format | Detection | Example |
|--------|-----------|---------|
| Legacy dict with `thought` | `"thought" in message` | `{"thought": "..."}` |
| Legacy dict with `content` | `"content" in message and "parts" not in message` | `{"content": "text"}` |
| pydantic-ai object/dict with `parts` | `_get_parts(message)` | `{"kind": "request", "parts": [...]}` |
| Empty dict | Falls through | `{}` |

**Part Type Mapping:**
| pydantic-ai `part_kind` | Becomes |
|-------------------------|---------|
| `text`, `user-prompt` | `TextPart` |
| `tool-call` | `ToolCallPart` |
| `tool-return` | `ToolReturnPart` |
| `system-prompt` | `SystemPromptPart` |
| unrecognized | `None` (filtered, **silent data loss**) |

---

### 4. Tool Call Tracking (Split State)

**Current state:** Tool calls tracked in **THREE separate locations**

| Location | Purpose | File References |
|----------|---------|-----------------|
| `session.tool_calls: list[dict]` | Display metadata | `state.py:76`, `ui/main.py:214` |
| `session.tool_call_args_by_id: dict` | Temporary arg storage | `state.py:77`, `tool_dispatcher.py:70,79` |
| Message parts | Conversation history | Built into message structure |

**Canonical replacement exists but unused:**
- `CanonicalToolCall` type defined in `src/tunacode/types/canonical.py:133-158`
- Has lifecycle status enum: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
- `ToolCallRegistry` design exists in plan but NOT implemented

**Files that would need changes:**
- `src/tunacode/core/agents/main.py` - Lines 289, 290, 352, 373, 582
- `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py` - Lines 70, 79, 164, 289
- `src/tunacode/core/agents/resume/sanitize.py` - Lines 348, 383, 579, 589, 604
- `src/tunacode/ui/commands/__init__.py` - Lines 84, 85

---

### 5. Direct Pydantic-AI Type Usage

**15+ files import pydantic-ai types directly:**

**Appropriate usage (exceptions, streaming):**
- `ModelRetry` - Exception type for tool retry logic (12 tool files)
- `PartDeltaEvent`, `TextPartDelta` - Streaming events (`agent_components/streaming.py`)
- `StreamedRunResult` - Streaming result type (`tool_executor.py`)

**Potentially replaceable (message types):**
- `Agent`, `Tool` - Agent construction (`main.py`, `research_agent.py`, `agent_config.py`)
- `ModelRequest`, `ModelResponse` - Message type hints (`ui/app.py`, `ui/headless/output.py`)
- `ToolCallPart` - Tool call parts (`tool_dispatcher.py`, `notifier.py`)
- `ModelMessage` - Message union (`core/state.py`, `agent_components/message_handler.py`)

**Note:** The adapter pattern is about *runtime message access*, not *type annotations*. Importing pydantic-ai types for type hints is acceptable as long as runtime access goes through the adapter.

---

### 6. Session State Structure

**Current `SessionState` has 40+ fields (src/tunacode/core/state.py):**

```python
@dataclass
class SessionState:
    # Message/history fields
    messages: list[ModelMessage]
    react_scratchpad: dict[str, Any]  # Should be ReActScratchpad
    todos: list[dict[str, Any]]       # Should be list[TodoItem]
    recursive_context_stack: list[dict[str, Any]]  # Should be list[RecursiveContext]

    # Tool call tracking (split across 3 places)
    tool_calls: list[dict[str, Any]]  # Display metadata
    tool_call_args_by_id: dict        # Temporary arg storage

    # Usage tracking
    last_call_usage: dict  # Should be UsageMetrics
    session_total_usage: dict  # Should be UsageMetrics

    # ... 30+ more fields
```

**Canonical types exist but unused:**
- `ReActScratchpad` - `types/canonical.py:183-204`
- `TodoItem` - `types/canonical.py:221-248`
- `UsageMetrics` - `types/canonical.py:257-298`
- `RecursiveContext` - `types/canonical.py:307-318`

---

### 7. Historical Context (Known Issues)

**From `.claude/debug_history/` and `.claude/delta/`:**

| Issue | Date | Root Cause | Canonical Fix |
|-------|------|------------|---------------|
| Dangling tool calls (mid-history) | 2026-01-21 | New message hides dangling calls | `find_dangling_tool_calls()` |
| Messages not persisted on abort | 2026-01-17 | `_persist_run_messages()` not in exception handler | Exception-safe state |
| Duplicate system prompts | 2026-01-21 | pydantic-ai auto-injects system prompts | `SystemPromptPart` filtering |
| Read-only `tool_calls` mutation | 2026-01-15 | Attempted to set `ModelResponse.tool_calls` | Use parts, not tool_calls |

**Key insight:** Many historical issues stem from the polymorphic message handling. The canonical model would prevent these by design.

---

## Key Patterns / Solutions Found

### Pattern 1: Polymorphic Access via `hasattr()` and `isinstance()`

**Problem:** Code must check both dict and object formats
```python
# Current pattern in 15+ locations
if hasattr(message, "parts"):
    parts = message.parts
elif isinstance(message, dict) and "parts" in message:
    parts = message["parts"]
else:
    parts = []
```

**Solution:** Use adapter which handles both transparently
```python
from tunacode.utils.messaging.adapter import to_canonical
canonical = to_canonical(message)  # Works on any format
parts = canonical.parts  # Always tuple[CanonicalPart, ...]
```

---

### Pattern 2: Content Extraction with Recursive Fallbacks

**Problem:** `get_message_content()` has 29 lines with 8 branches
```python
# Current implementation (message_utils.py:6-34)
def get_message_content(message: Any) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        if "content" in message:
            content = message["content"]
            if isinstance(content, list):
                return " ".join(get_message_content(m) for m in content)
            return get_message_content(content)
        # ... more branches
```

**Solution:** Convert to canonical, then extract
```python
# New implementation (adapter.py:261-268)
def get_content(message: Any) -> str:
    if isinstance(message, CanonicalMessage):
        return message.get_text_content()
    return to_canonical(message).get_text_content()
```

---

### Pattern 3: Tool Call ID Extraction

**Problem:** Custom code scattered across multiple files
```python
# Current pattern in sanitize.py:116-178
def _collect_tool_call_ids(messages: list[ModelMessage]) -> set[str]:
    call_ids = set()
    for message in messages:
        if isinstance(message, dict):
            if "parts" in message:
                for part in message["parts"]:
                    if isinstance(part, dict) and part.get("part_kind") == "tool-call":
                        call_ids.add(part.get("tool_call_id"))
            elif "tool_calls" in message:
                for tc in message["tool_calls"]:
                    if hasattr(tc, "tool_call_id"):
                        call_ids.add(tc.tool_call_id)
        elif hasattr(message, "parts"):
            for part in message.parts:
                if getattr(part, "part_kind", None) == "tool-call":
                    call_ids.add(part.tool_call_id)
    return call_ids
```

**Solution:** Use adapter function
```python
from tunacode.utils.messaging.adapter import get_tool_call_ids
call_ids = get_tool_call_ids(messages)
```

---

### Pattern 4: Dangling Tool Call Detection

**Problem:** Manual diff logic in exception handlers
```python
# Current pattern in sanitize.py:262-328
def _remove_dangling_tool_calls(messages: list[ModelMessage]) -> list[ModelMessage]:
    call_ids = _collect_tool_call_ids(messages)  # 62 lines
    return_ids = _collect_tool_return_ids(messages)  # similar complexity
    dangling = call_ids - return_ids
    # ... filtering logic
```

**Solution:** Use adapter function
```python
from tunacode.utils.messaging.adapter import find_dangling_tool_calls
dangling = find_dangling_tool_calls(messages)
```

---

### Pattern 5: Part Type Checking

**Problem:** String comparison on `part_kind` attribute
```python
# Current pattern in prune.py:55-73
def is_tool_return_part(part: Any) -> bool:
    part_kind = getattr(part, "part_kind", None)
    return part_kind == "tool-return"

def is_user_prompt_part(part: Any) -> bool:
    part_kind = getattr(part, "part_kind", None)
    return part_kind == "user-prompt"
```

**Solution:** Use `isinstance()` with canonical types
```python
from tunacode.types.canonical import ToolReturnPart
is_tool_return = isinstance(part, ToolReturnPart)
```

---

## Knowledge Gaps

1. **Streaming compatibility:** How do frozen dataclasses work with incremental message building during streaming? The `agent_components/streaming.py` file shows direct access to `event.part.content` and `event.delta.content_delta`.

2. **Session file backward compatibility:** Adapter handles legacy formats, but has it been tested with real historical session files? No `tests/parity/test_message_parity.py` exists.

3. **Performance impact:** No benchmarks exist comparing canonical vs polymorphic code paths. Conversion overhead unknown.

4. **Unknown part kinds:** The adapter silently filters unrecognized `part_kind` values (line 106 in adapter.py returns `None`). Could this cause data loss?

5. **TOOL role semantics:** When converting `MessageRole.TOOL` back via `from_canonical()`, the kind is set to `"response"` (lines 242-246). Is this semantically correct for pydantic-ai?

---

## Recommended Adoption Strategy

### Phase A: Simple Wins (Low Risk)

1. **Replace 3 `get_message_content()` calls:**
   ```python
   # In state.py:123, app.py:355, headless/output.py:50
   - from tunacode.utils.messaging.message_utils import get_message_content
   + from tunacode.utils.messaging.adapter import get_content
   ```

2. **Add deprecation warning to `get_message_content()`:**
   ```python
   # In message_utils.py
   def get_message_content(message: Any) -> str:
       warnings.warn(
           "get_message_content() is deprecated. Use adapter.get_content() instead.",
           DeprecationWarning,
           stacklevel=2
       )
       # ... existing code
   ```

3. **Create parity tests with real sessions:**
   - Add `tests/parity/test_message_parity.py`
   - Load historical session files
   - Verify `to_canonical()` -> `from_canonical()` round-trip

---

### Phase B: Sanitize Refactor (Medium Risk)

4. **Port `sanitize.py` to use canonical adapter:**
   - Replace `_get_message_parts()` with `adapter.to_canonical()`
   - Replace `_collect_tool_call_ids()` with `adapter.get_tool_call_ids()`
   - Replace `_collect_tool_return_ids()` with `adapter.get_tool_return_ids()`
   - Replace dangling detection with `adapter.find_dangling_tool_calls()`
   - Expected: Reduce from 631 lines to ~100 lines

---

### Phase C: Resume Module Cleanup (Medium Risk)

5. **Port `prune.py` and `summary.py` to canonical:**
   - Replace `hasattr(message, "parts")` checks with `adapter.to_canonical()`
   - Replace `isinstance(message, dict)` with canonical type checks
   - Use `isinstance(part, ToolReturnPart)` instead of string comparison

---

### Phase D: Tool Call Registry (Higher Risk)

6. **Implement `ToolCallRegistry`:**
   - Create new class to own tool call lifecycle
   - Consolidate `session.tool_calls` and `session.tool_call_args_by_id`
   - Track status using `CanonicalToolCall` and `ToolCallStatus`

---

### Phase E: SessionState Decomposition (Higher Risk)

7. **Split `SessionState` into sub-states:**
   - `ConversationState` (messages, history)
   - `ReActState` (scratchpad, timeline)
   - `TaskState` (todos, recursive context)
   - `UsageState` (metrics, costs)

---

## Validation Gates

Before each phase, verify:

1. **Parity tests pass:** `to_canonical(msg)` → `from_canonical()` → original
2. **Round-trip tests pass:** Message content preserved
3. **Tool call linkage preserved:** No orphaned calls/returns
4. **Session files load:** Historical sessions deserialize correctly
5. **Tests still pass:** No regressions in existing test suite

---

## References

### Code Files

| File | Purpose | Lines |
|------|---------|-------|
| `src/tunacode/types/canonical.py` | Target types (frozen dataclasses) | 350 |
| `src/tunacode/utils/messaging/adapter.py` | Adapter implementation | 315 |
| `src/tunacode/utils/messaging/message_utils.py` | Legacy accessors (to be deprecated) | 34 |
| `src/tunacode/core/agents/resume/sanitize.py` | Polymorphic sanitization (to be refactored) | 631 |
| `src/tunacode/core/agents/resume/prune.py` | Polymorphic pruning (to be refactored) | ~200 |
| `src/tunacode/core/agents/resume/summary.py` | Polymorphic summarization (to be refactored) | ~200 |
| `src/tunacode/core/state.py` | SessionState (40+ fields, to be split) | 426 |

### Test Files

| File | Purpose | Lines |
|------|---------|-------|
| `tests/unit/types/test_canonical.py` | Canonical type tests | 368 |
| `tests/unit/types/test_adapter.py` | Adapter tests (includes parity) | 355 |

### Documentation

| File | Purpose |
|------|---------|
| `PLAN.md` | Architecture refactor adoption plan |
| `docs/refactoring/architecture-refactor-plan.md` | Original plan (547 lines) |
| `docs/refactoring/message-flow-map.md` | Message flow documentation |
| `docs/refactoring/dependency-diagram.md` | Dependency visualization |

### GitHub Permalinks

| File | Link (commit: bc95cdf1) |
|------|------------------------|
| `src/tunacode/types/canonical.py` | https://github.com/alchemiststudiosDOTai/tunacode/blob/bc95cdf1/src/tunacode/types/canonical.py |
| `src/tunacode/utils/messaging/adapter.py` | https://github.com/alchemiststudiosDOTai/tunacode/blob/bc95cdf1/src/tunacode/utils/messaging/adapter.py |
| `src/tunacode/utils/messaging/message_utils.py` | https://github.com/alchemiststudiosDOTai/tunacode/blob/bc95cdf1/src/tunacode/utils/messaging/message_utils.py |
| `src/tunacode/core/state.py` | https://github.com/alchemiststudiosDOTai/tunacode/blob/bc95cdf1/src/tunacode/core/state.py |
| `src/tunacode/core/agents/resume/sanitize.py` | https://github.com/alchemiststudiosDOTai/tunacode/blob/bc95cdf1/src/tunacode/core/agents/resume/sanitize.py |

---

## Metadata

| Field | Value |
|-------|-------|
| Research Date | 2026-01-25 |
| Git Commit | bc95cdf1e68d8f2ff2b8253f631afdf3fbbbfb25 |
| Git Branch | types-architect |
| Repo | alchemiststudiosDOTai/tunacode |
| Related Tasks | Task 01 (Canonical Messaging), Task 03 (Parity Harness), Task 04 (Canonical Sanitization) |
| Related Research | [2026-01-25 Architecture Refactor Status](./2026-01-25_architecture-refactor-status.md) |

---

## Follow-up Research: P1/P2 Split [2026-01-25]

### Summary

Task 01 has been split into two phases to separate messaging concerns from tooling concerns:

| Phase | Scope | Complexity | Files |
|-------|-------|------------|-------|
| **P1 (Messaging)** | Replace 3 `get_message_content()` calls | LOW | 3 files |
| **P2 (Tooling)** | Route sanitize.py through adapter helpers | MEDIUM | 3 files |

### P1 Specific Findings

All 3 production call sites are pure content extraction with no side effects:

| Call Site | Context | Usage |
|-----------|---------|-------|
| `state.py:123` | `update_token_count()` | Token estimation |
| `app.py:355` | `_replay_session_messages()` | Session UI replay |
| `output.py:50` | `_extract_from_messages()` | Headless output |

**Parity verified:** Both functions return `str`, empty string for no content. Tests exist at `tests/unit/types/test_adapter.py:259-273`.

### P2 Specific Findings

**Duplication analysis (~150 LOC can be deleted):**

The tool call tracking logic is duplicated between `adapter.py` and `sanitize.py`:

| adapter.py Function | sanitize.py Equivalent |
|--------------------|------------------------|
| `_get_attr()` (L48-52) | `_get_attr_value()` (L58-62) |
| `_get_parts()` (L55-66) | `_get_message_parts()` (L76-79) |
| `get_tool_call_ids()` (L276-280) | `_collect_message_tool_call_ids()` (L171-178) |
| `get_tool_return_ids()` (L283-287) | `_collect_message_tool_return_ids()` (L181-184) |
| `find_dangling_tool_calls()` (L290-299) | `find_dangling_tool_call_ids()` (L192-225) |

**main.py embedded duplication:**

`main.py:365-397` reimplements the cleanup loop that already exists in `sanitize.py:577-630` as `run_cleanup_loop()`. Replacing this saves 30 lines.

**Unique sanitize.py functions (KEEP):**

These perform session state mutation and cannot be replaced by adapter functions:
- `remove_dangling_tool_calls()` - mutates messages list
- `remove_empty_responses()` - repairs abort scenarios
- `remove_consecutive_requests()` - repairs abort scenarios
- `sanitize_history_for_resume()` - pydantic-ai compatibility
- `run_cleanup_loop()` - orchestration

### Sequencing Dependency

P1 must complete before P2. Rationale: P2 depends on adapter layer stability, and P1 validates that `get_content()` works correctly in production before we route more complex tooling logic through the same adapter.

### Task File Updated

The detailed P1/P2 breakdown is now in `.claude/task/task_01_canonical_messaging_adoption.md`.
