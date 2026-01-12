# Research – Agent Components Codebase Mapping

**Date:** 2026-01-12
**Owner:** claude-code
**Phase:** Research

## Goal

Map out all files in `src/tunacode/core/agents/agent_components/` to identify:
- **Wins**: Well-designed patterns and code worth preserving
- **Smells**: Anti-patterns, complexity issues, technical debt
- **Quick Wins**: Small changes with high ROI

## Findings

### File Inventory (12 files + __init__.py)

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 49 | Package exports |
| `agent_config.py` | 449 | Agent creation, caching, tool registration |
| `agent_helpers.py` | 292 | Message/user creation, tool summaries |
| `message_handler.py` | 100 | Message class retrieval, patch logic |
| `node_processor.py` | 486 | Core node/tool processing logic |
| `response_state.py` | 130 | State machine wrapper for responses |
| `result_wrapper.py` | 52 | Wrapper classes for agent runs |
| `state_transition.py` | 117 | State machine implementation |
| `streaming.py` | 277 | Token streaming instrumentation |
| `task_completion.py` | 41 | Completion marker detection |
| `tool_buffer.py` | 45 | Read-only tool batching buffer |
| `tool_executor.py` | 114 | Parallel tool execution + retry |
| `truncation_checker.py` | 38 | Response truncation detection |

---

## Wins (Well-Designed Code)

### 1. `state_transition.py` – Clean State Machine
**Lines:** 1-117

**Why it wins:**
- Thread-safety with `RLock` (line 50)
- Separation of rules from machine (lines 21-35, 37-106)
- Custom exception with context (`InvalidStateTransitionError`)
- Pre-defined transition rules as data structure (lines 109-116)

**Pattern:** State machine pattern with rules as data

```python
# Lines 109-116: Rules defined declaratively
AGENT_TRANSITION_RULES = StateTransitionRules(
    valid_transitions={
        AgentState.USER_INPUT: {AgentState.ASSISTANT},
        AgentState.ASSISTANT: {AgentState.TOOL_EXECUTION, AgentState.RESPONSE},
        AgentState.TOOL_EXECUTION: {AgentState.RESPONSE},
        AgentState.RESPONSE: {AgentState.ASSISTANT},
    }
)
```

**Preserve:** This pattern is exemplary. Use as template for other stateful components.

---

### 2. `response_state.py` – Backward Compatibility Wrapper
**Lines:** 1-130

**Why it wins:**
- Thread-safe property access with locks (lines 52-59)
- Wraps new state machine while preserving legacy boolean flags
- Clean property delegation pattern

**Pattern:** Facade for backward compatibility

---

### 3. `task_completion.py` – Focused Utility
**Lines:** 1-41

**Why it wins:**
- Pre-compiled regex at module level (lines 5-8) – O(1) matching
- Single-responsibility function
- Returns `(is_complete, cleaned_content)` tuple – caller gets everything

```python
# Lines 5-8: Pre-compiled patterns
_COMPLETION_MARKERS = (
    re.compile(r"^\s*TUNACODE\s+DONE:\s*", re.IGNORECASE),
    re.compile(r"^\s*TUNACODE[_\s]+TASK_COMPLETE\s*:?[\s]*", re.IGNORECASE),
)
```

**Preserve:** This is the gold standard for simple utilities.

---

### 4. `tool_buffer.py` – Minimalist Buffer
**Lines:** 1-45

**Why it wins:**
- No external dependencies
- Clear API: `add()`, `flush()`, `has_tasks()`, `peek()`, `count_by_type()`
- Type-agnostic (stores `Any` tuples)

**Preserve:** Reuse this pattern for other buffering needs.

---

### 5. `agent_config.py` – Dual-Layer Caching
**Lines:** 310-448 (`get_or_create_agent`)

**Why it wins:**
- Two-tier cache: session-level + module-level (lines 317-339)
- Version-based invalidation (lines 114-123, 314-315)
- Lazy imports to avoid circular deps (lines 149-151, 344-345)

**Preserve:** Cache pattern is excellent. Document in codebase-map.

---

### 6. `tool_executor.py` – Explicit Error Classification
**Lines:** 26-36, 46-113

**Why it wins:**
- Clear separation of retryable vs non-retryable errors
- Per-tool timing metrics (line 75-76)
- Batched parallel execution with env-configurable parallelism (line 66)

```python
# Lines 26-36: Explicit error classification
NON_RETRYABLE_ERRORS = (
    UserAbortError,
    ModelRetry,
    KeyboardInterrupt,
    SystemExit,
    ValidationError,
    ConfigurationError,
    ToolExecutionError,
    FileOperationError,
)
```

**Preserve:** This error taxonomy should be documented centrally.

---

### 7. `truncation_checker.py` – Composable Heuristics
**Lines:** 1-38

**Why it wins:**
- Each check is independent and testable
- No side effects
- Composition of simple rules

**Preserve:** Pattern for heuristic-based validators.

---

## Smells (Issues & Anti-Patterns)

### 1. `node_processor.py` – God Function
**Lines:** 158-339 (`_process_node`) + 342-486 (`_process_tool_calls`)

**Issues:**
- **Function length:** `_process_node` is 182 lines, `_process_tool_calls` is 145 lines
- **Cyclomatic complexity:** Nested `if/elif/else` chains (lines 217-289)
- **Too many responsibilities:**
  1. State transitions (183-185, 286-289, 320-326)
  2. Token usage tracking (130-156)
  3. Task completion detection (217-289)
  4. Truncation checking (291-306)
  5. Tool call extraction (308-317)
- **Magic strings:** `"let me"`, `"i'll check"`, etc. (lines 245-258)

**Impact:** High coupling – changing one behavior risks breaking others.

**Refactor path:**
```
_process_node (182 lines) → extract:
  ├── _update_token_usage() [ALREADY EXISTS, lines 130-156]
  ├── _check_task_completion() [extract from 217-289]
  └── _detect_truncation() [extract from 291-306]
```

---

### 2. `node_processor.py` – Nested Callback Chain
**Lines:** 309-317

**Issue:** Callback injection at 3 levels:
```python
await _process_tool_calls(
    node,
    buffering_callback,      # Level 1
    state_manager,
    tool_buffer,
    response_state,
    tool_result_callback,    # Level 2
    tool_start_callback,     # Level 3
)
```

**Smell:** Hidden dependency flow. Callbacks obscure what data flows where.

**Alternative:** Pass a context object or use structured concurrency.

---

### 3. `agent_helpers.py` – Hidden Global State
**Lines:** 17-39 (`get_user_prompt_part_class`)

**Issue:**
```python
_USER_PROMPT_PART_CLASS = None  # Module-level cache

def get_user_prompt_part_class():
    global _USER_PROMPT_PART_CLASS
    if _USER_PROMPT_PART_CLASS is not None:
        return _USER_PROMPT_PART_CLASS
    # ... lazy load ...
```

**Smell:** Global mutable state with lazy initialization. Testing becomes harder – tests must reset this cache.

**Fix:** Pass the class explicitly or use a dependency injection pattern.

---

### 4. `agent_helpers.py` – Unused Function Exported
**Lines:** 76-118

**Issue:** `get_readable_tool_description` is defined but NOT exported in `__init__.py`.

```python
# In agent_helpers.py:
def get_readable_tool_description(...): ...

# In __init__.py - NOT in __all__:
# get_readable_tool_description is missing
```

**Smell:** Either dead code or forgotten export. Should be one or the other.

---

### 5. `result_wrapper.py` – Over-Engineered Wrappers
**Lines:** 13-52

**Issue:** Two nearly identical wrapper classes with complex `__getattribute__`:

```python
class AgentRunWrapper:
    def __getattribute__(self, name: str) -> Any:
        if name in ["_wrapped", "_result", "response_state"]:
            return object.__getattribute__(self, name)
        if name == "result":
            return object.__getattribute__(self, "_result")
        # ... 15 lines of delegation logic ...
```

**Smell:** 23 lines of `__getattribute__` for simple delegation.

**Alternative:** Use `__getattr__` or dataclass with `__slots__`.

---

### 6. `streaming.py` – Function Extract Candidates
**Lines:** 70-99, 103-166

**Issue:** `_extract_text()` (lines 70-99) is a 30-line inline helper. `_find_overlap_length()` (lines 18-34) is good – extract more like it.

**Lines 103-166:** Debug event logging is 64 lines embedded in the streaming loop.

**Fix:** Extract to module-level functions:
- `_extract_text()` → already extracted (good)
- Debug event logging → extract to `_log_debug_event()`

---

### 7. `message_handler.py` – Hard-Coded Fallback
**Lines:** 28-37

**Issue:** Inline class definition as fallback:
```python
if not hasattr(messages, "SystemPromptPart"):
    class SystemPromptPart:  # type: ignore
        def __init__(self, content: str = "", role: str = "system", part_kind: str = ""):
            self.content = content
            self.role = role
            self.part_kind = part_kind
```

**Smell:** Class defined inside `if` block – hard to test, hard to find.

**Alternative:** Define fallback class at module level.

---

## Quick Wins (High ROI Changes)

### Quick Win 1: Extract `check_task_completion` from `node_processor.py`
**File:** `node_processor.py:234-289`

**Lines:** ~56 lines embedded in `_process_node`

**Change:** Extract completion detection logic to helper function.

**Before:**
```python
for part in response_parts:
    if hasattr(part, "content") and isinstance(part.content, str):
        if part.content.strip():
            has_non_empty_content = True
            all_content_parts.append(part.content)

        is_complete, cleaned_content = check_task_completion(part.content)
        if is_complete:
            # ... 40+ lines of nested logic ...
```

**After:**
```python
has_non_empty_content, all_content_parts, completion_detected = _analyze_response_parts(
    response_parts, state_manager
)
```

**ROI:**
- Reduces `_process_node` from 182 → ~130 lines
- Makes completion detection testable in isolation
- Removes ~15 levels of nesting

---

### Quick Win 2: Export `get_readable_tool_description`
**File:** `agent_helpers.py:76-118` + `__init__.py`

**Change:** Add to `__all__` in `__init__.py`

**Before:** Function defined but not exported.

**After:**
```python
# In agent_helpers.py - already defined
def get_readable_tool_description(tool_name: str, tool_args: dict[str, Any]) -> str:

# In __init__.py - add to __all__:
from .agent_helpers import (
    ...
    get_readable_tool_description,
    ...
)
```

**ROI:**
- 1 line change
- Makes function available for batch panel rendering (already has use case)

---

### Quick Win 3: Define Fallback Class at Module Level
**File:** `message_handler.py:28-37`

**Change:** Move inline class to module level.

**Before:**
```python
if not hasattr(messages, "SystemPromptPart"):
    class SystemPromptPart:  # type: ignore
        ...
```

**After:**
```python
class _SystemPromptPartFallback:
    def __init__(self, content: str = "", role: str = "system", part_kind: str = ""):
        ...

if not hasattr(messages, "SystemPromptPart"):
    SystemPromptPart = _SystemPromptPartFallback
```

**ROI:**
- Makes fallback testable
- Reduces cognitive load in `get_model_messages()`
- 5 lines moved, 5 lines saved in function

---

### Quick Win 4: Use `__getattr__` Instead of `__getattribute__`
**File:** `result_wrapper.py:21-35`

**Change:** Replace complex `__getattribute__` with simpler `__getattr__`.

**Before:**
```python
def __getattribute__(self, name: str) -> Any:
    if name in ["_wrapped", "_result", "response_state"]:
        return object.__getattribute__(self, name)
    if name == "result":
        return object.__getattribute__(self, "_result")
    # ... delegation ...
```

**After:**
```python
def __getattr__(self, name: str) -> Any:
    if name == "result":
        return self._result
    return getattr(self._wrapped, name)
```

**ROI:**
- Reduces from 15 lines to 5 lines
- `__getattr__` is only called for missing attributes – simpler logic
- Fixes potential edge case bugs with `__getattribute__`

---

### Quick Win 5: Add Type Hints to `agent_helpers.py`
**File:** `agent_helpers.py` – multiple functions

**Changes:**
```python
# Line 55: Add return type
def get_tool_summary(tool_calls: list[dict[str, Any]]) -> dict[str, int]:

# Line 64: Add type hints
def get_tool_description(tool_name: str, tool_args: dict[str, Any]) -> str:

# Line 120: Add type hints
def get_recent_tools_context(tool_calls: list[dict[str, Any]], limit: int = 3) -> str:
```

**ROI:**
- 3 lines changed
- Enables static type checking
- Documents expected inputs

---

## Priority Matrix

| Quick Win | Effort | Impact | Risk |
|-----------|--------|--------|------|
| 1. Extract completion detection | Medium | High | Low |
| 2. Export `get_readable_tool_description` | Low | Medium | None |
| 3. Move fallback class to module level | Low | Low | None |
| 4. Use `__getattr__` in wrappers | Low | Medium | None |
| 5. Add type hints to helpers | Low | Low | None |

**Recommendation:** Do Quick Wins 2, 3, 4, 5 first (1 hour total). Then tackle Quick Win 1 as part of `node_processor.py` refactoring.

---

## References

- `src/tunacode/core/agents/agent_components/` – All files reviewed
- `src/tunacode/core/agents/agent_components/__init__.py` – Export list
