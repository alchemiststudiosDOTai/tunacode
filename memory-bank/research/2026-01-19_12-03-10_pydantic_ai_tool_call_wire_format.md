# Research – pydantic_ai Tool Call Wire Format and Lifecycle

**Date:** 2026-01-19
**Owner:** claude
**Phase:** Research

## Goal

Document the full tool call lifecycle including the pydantic_ai wire format, args normalization, and edge cases. This research supports issue #249: "docs: Document pydantic_ai tool call wire format and lifecycle".

### Additional Search
- `grep -ri "tool_call" .claude/` → `.claude/delta/2026-01-17-dangling-tool-calls.md` (dangling tool calls bug documentation)

---

## Findings

### Relevant Files & Why They Matter

| File | Purpose |
|------|---------|
| `docs/codebase-map/architecture/conversation-turns.md` | Existing conversation flow docs (needs expansion) |
| `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py` | Core tool dispatch logic, args normalization |
| `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py` | `_emit_tool_returns()` consumes stored args |
| `src/tunacode/core/agents/main.py` | `_remove_dangling_tool_calls()` cleanup on abort |
| `src/tunacode/core/state.py` | `SessionState.tool_call_args_by_id` field definition |
| `src/tunacode/types/pydantic_ai.py` | Type re-exports, isolates pydantic-ai deps |
| `src/tunacode/constants.py` | `ERROR_TOOL_CALL_ID_MISSING`, `ERROR_TOOL_ARGS_MISSING` |
| `.claude/delta/2026-01-17-dangling-tool-calls.md` | Bug report for dangling tool calls on abort |

---

## Key Patterns / Solutions Found

### 1. The pydantic_ai Wire Format

The pydantic-ai library uses two primary message part types for tool calls:

**ToolCallPart** (from `pydantic_ai.messages`)
```python
ToolCallPart(
    tool_name="grep",
    args='{"pattern": "TODO"}',  # Raw JSON string OR dict
    tool_call_id="call_abc123"    # Unique identifier
)
```

**ToolReturnPart** (from `pydantic_ai.messages`)
```python
ToolReturnPart(
    tool_call_id="call_abc123",  # Reference to ToolCallPart
    content="Found 42 TODOs",    # Tool output
    tool_name="grep"             # Which tool was called
)
```

**Critical observation:** `ToolReturnPart` does NOT contain the args field - it only has a `tool_call_id` reference back to the original call.

### 2. The tool_call_id Link

The `tool_call_id` is the critical identifier that links `ToolCallPart` → `ToolReturnPart` across iterations:

```
Iteration N:   ModelResponse with ToolCallPart
                ├─ tool_call_id: "call_abc123"
                ├─ tool_name: "grep"
                └─ args: '{"pattern": "TODO"}'

                ↓ tool executes

Iteration N+1: ModelRequest with ToolReturnPart
                ├─ tool_call_id: "call_abc123"  ← SAME ID
                ├─ content: "Found 42 TODOs"
                └─ tool_name: "grep"
```

### 3. Args Normalization Pattern

**Why args are stored separately:**

Since `ToolReturnPart` lacks argument data, a separate dict bridges the temporal gap:

```python
# Storage location: SessionState.tool_call_args_by_id
tool_call_args_by_id: dict[ToolCallId, ToolArgs]
# = dict[str, dict[str, Any]]
```

**Data flow:**
```
ToolCallPart arrives
    ↓
record_tool_call_args(part, state_manager)
    ├─ raw_args = getattr(part, "args", {})
    ├─ parsed_args = await normalize_tool_args(raw_args)
    └─ tool_call_args_by_id[tool_call_id] = parsed_args

    ↓ (later, next iteration)

ToolReturnPart arrives
    ↓
consume_tool_call_args(part, state_manager)
    ├─ tool_call_id = getattr(part, "tool_call_id")
    ├─ args = tool_call_args_by_id.pop(tool_call_id)
    └─ return args  ← For UI callback display
```

**Entry points:**
- `record_tool_call_args()` → `tool_dispatcher.py:62`
- `consume_tool_call_args()` → `tool_dispatcher.py:72`
- `normalize_tool_args()` → `tool_dispatcher.py:54`

### 4. Message Invariant

The conversation has a critical invariant documented in `conversation-turns.md`:

```
INVARIANT: Every ModelResponse with tool_calls MUST be followed by
           matching ToolReturn(s) before any new ModelRequest
```

**Enforcement:** `_remove_dangling_tool_calls()` in `except UserAbortError` handler removes trailing `ModelResponse` messages with unanswered tool calls.

### 5. Edge Cases and Error Handling

| Edge Case | Location | Handling |
|-----------|----------|----------|
| Missing `tool_call_id` attribute | `tool_dispatcher.py:75-76` | Raises `StateError("Tool return missing tool_call_id.")` |
| Missing args in cache | `tool_dispatcher.py:78-79` | Raises `StateError("Tool args missing for tool_call_id '{id}'.")` |
| `None` `tool_call_id` during record | `tool_dispatcher.py:67-68` | Silently skips caching, continues processing |
| User abort mid-tool-call | `main.py:409-417` | Calls `_remove_dangling_tool_calls()` to restore state |
| Empty messages list | `main.py:491-492` | Returns `False` immediately |
| Partial tool call cleanup | `main.py:495-507` | Removes trailing messages with tool calls backward |

### 6. Fallback Tool Call Parsing

When LLMs embed tool calls in text (not structured parts), `_extract_fallback_tool_calls()` parses text content:

```python
# tool_dispatcher.py:88-165
async def _extract_fallback_tool_calls(parts, state_manager, response_state):
    # 1. Extract text from TextParts
    # 2. Check for tool call indicators
    # 3. Parse tool calls from text
    # 4. Create synthetic ToolCallPart instances
    # 5. Store args in tool_call_args_by_id
    return [(ToolCallPart(...), ToolArgs), ...]
```

---

## Knowledge Gaps

### 1. Missing Documentation Sections

Per issue #249, the following needs to be added to `conversation-turns.md`:

- [ ] **Wire format section**: Exact structure of `ToolCallPart` and `ToolReturnPart`
- [ ] **Args normalization explanation**: Why we store/consume args separately
- [ ] **Edge cases catalog**: All error scenarios and how they're handled
- [ ] **Sequence diagrams**: Visual showing `tool_call_id` flow across iterations

### 2. Missing Test Coverage

Per dangling-tool-calls delta doc, no test exists for:
- Abort scenarios during tool execution
- Verification that `messages` ends in valid state after abort
- Verification that next request succeeds after abort cleanup

### 3. ToolCallPart Source Not Fully Traced

We use `ToolCallPart` from `pydantic_ai.messages` but didn't trace:
- How pydantic-ai generates `tool_call_id` values
- Whether IDs are guaranteed unique across the session
- What happens if the LLM sends duplicate `tool_call_id` values

---

## References

### Files to Review for Implementation

1. **`src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`**
   - Lines 54-59: `normalize_tool_args()`
   - Lines 62-69: `record_tool_call_args()`
   - Lines 72-80: `consume_tool_call_args()`
   - Lines 171-329: `dispatch_tools()` main logic

2. **`src/tunacode/core/agents/main.py`**
   - Lines 62-69: `_reset_session_state()` clears dict
   - Lines 409-417: `except UserAbortError` handler
   - Lines 486-508: `_remove_dangling_tool_calls()` implementation

3. **`src/tunacode/core/state.py`**
   - Line 80: `tool_call_args_by_id` field definition

4. **`docs/codebase-map/architecture/conversation-turns.md`**
   - Lines 212-215: Message types table (add wire format detail)
   - Lines 279-299: Message invariants (expand with edge cases)

### Related Documentation

- `.claude/delta/2026-01-17-dangling-tool-calls.md` - Bug report for dangling tool calls
- `docs/codebase-map/architecture/conversation-turns.md` - Target doc for expansion
- Issue #249 - Original documentation request
- Issue #250 - Testing issue (blocked by this doc work)

### Type Definitions

- `src/tunacode/types/base.py`:
  - Line 17: `ToolCallId = str`
  - Line 36: `ToolArgs = dict[str, Any]`

- `src/tunacode/types/pydantic_ai.py`:
  - Line 12: `from pydantic_ai.messages import ToolReturnPart`
  - Line 21: `MessagePart = ToolReturnPart | Any`

---

## Next Steps (for implementation)

1. Create new section in `conversation-turns.md`: "## Tool Call Wire Format"
2. Document `ToolCallPart` and `ToolReturnPart` structure with code examples
3. Add sequence diagram showing `tool_call_id` flow across iterations
4. Create "## Args Normalization Pattern" section with:
   - Why args are stored separately
   - The `record_tool_call_args()` / `consume_tool_call_args()` contract
   - Code examples showing the data flow
5. Create "## Edge Cases" section cataloging all error scenarios
6. (Future) Add tests for abort scenarios once docs are complete
