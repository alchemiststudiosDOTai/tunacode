# Research: Task 06 ReAct State Alignment & Task 08 Usage Metrics Consolidation

**Date:** 2026-01-25
**Owner:** Claude (research agent)
**Phase:** Research
**Branch:** task-06-08-react-usage-alignment

---

## Goal

Document the current state of ReAct scratchpad and usage metrics implementations to enable migration from dict-based storage to typed dataclasses defined in `canonical.py`.

---

## Findings

### Current State Summary

| Component | Current Type | Target Type | Status |
|-----------|-------------|-------------|--------|
| ReAct scratchpad | `dict[str, Any]` | `ReActScratchpad` | Typed class exists, unused |
| ReAct timeline entries | `dict[str, Any]` | `ReActEntry` | Typed class exists, unused |
| Usage (last_call) | `dict[str, int\|float]` | `UsageMetrics` | Typed class exists with converters |
| Usage (session_total) | `dict[str, int\|float]` | `UsageMetrics` | Typed class exists with converters |

### Relevant Files & Why They Matter

#### ReAct Scratchpad (Task 06)

| File | Lines | Purpose |
|------|-------|---------|
| `src/tunacode/types/canonical.py` | 177-220 | **TARGET**: `ReActScratchpad`, `ReActEntry`, `ReActEntryKind` definitions |
| `src/tunacode/types/state_structures.py` | 56-62 | **CHANGE**: `ReActState.scratchpad: dict` field |
| `src/tunacode/types/state.py` | 96-107 | **CHANGE**: Protocol method signatures |
| `src/tunacode/core/state.py` | 206-215 | **CHANGE**: StateManager helper methods |
| `src/tunacode/core/state.py` | 354, 409-410 | **CHANGE**: Serialization/deserialization |
| `src/tunacode/tools/react.py` | 40-72 | **CHANGE**: Tool creates dict entries |
| `src/tunacode/core/agents/main.py` | 148-236 | **READ**: `ReactSnapshotManager` reads scratchpad |
| `src/tunacode/ui/commands/__init__.py` | 87-89 | **CHANGE**: Clear command resets fields |

#### Usage Metrics (Task 08)

| File | Lines | Purpose |
|------|-------|---------|
| `src/tunacode/types/canonical.py` | 272-314 | **TARGET**: `UsageMetrics` with `from_dict()`/`to_dict()` |
| `src/tunacode/types/state_structures.py` | 87-92 | **CHANGE**: `UsageState` fields |
| `src/tunacode/core/agents/.../usage_tracker.py` | 30-55 | **CHANGE**: Dict key access → attribute access |
| `src/tunacode/ui/app.py` | 258-259, 474 | **CHANGE**: `.get("cost")` → `.cost` |
| `src/tunacode/ui/main.py` | 219 | **CHANGE**: JSON serialization |
| `src/tunacode/ui/commands/__init__.py` | 105-109 | **CHANGE**: Reset with `UsageMetrics()` |
| `src/tunacode/core/state.py` | 351, 401-405 | **CHANGE**: Serialization uses `.to_dict()` |
| `tests/unit/core/test_usage_tracker.py` | 24-39 | **CHANGE**: Dict keys → attributes |

---

## Key Patterns / Solutions Found

### Pattern 1: TodoItem Migration (Reference Implementation)

**Location:** `canonical.py:236-264`, `state.py:310-332`

This is the proven pattern to follow:

```python
@dataclass(frozen=True, slots=True)
class TodoItem:
    content: str
    status: TodoStatus
    active_form: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TodoItem":
        # Handle legacy camelCase and snake_case keys
        return cls(
            content=data.get("content", ""),
            status=TodoStatus(data.get("status", "pending")),
            active_form=data.get("activeForm", data.get("active_form", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        # Preserve legacy format for backward compatibility
        return {
            "content": self.content,
            "status": self.status.value,
            "activeForm": self.active_form,
        }
```

### Pattern 2: Current ReAct Entry Format (Legacy)

**Location:** `tools/react.py:49, 57`

```python
# "think" action creates:
{"type": "think", "thoughts": thoughts, "next_action": next_action}

# "observe" action creates:
{"type": "observe", "result": result}
```

**Target format** (`canonical.py:192-198`):
```python
ReActEntry(kind=ReActEntryKind.THINK, content=str, timestamp=datetime)
```

**Challenge:** Legacy format has multiple keys (`thoughts`, `next_action`, `result`) vs. single `content` field.

### Pattern 3: UsageMetrics Already Has Converters

**Location:** `canonical.py:296-313`

```python
@classmethod
def from_dict(cls, data: dict[str, Any]) -> "UsageMetrics":
    return cls(
        prompt_tokens=data.get("prompt_tokens", 0),
        completion_tokens=data.get("completion_tokens", 0),
        cached_tokens=data.get("cached_tokens", 0),
        cost=data.get("cost", 0.0),
    )

def to_dict(self) -> dict[str, Any]:
    return {
        "prompt_tokens": self.prompt_tokens,
        "completion_tokens": self.completion_tokens,
        "cached_tokens": self.cached_tokens,
        "cost": self.cost,
    }
```

### Pattern 4: Three-Way State Split (ReAct Bug)

**Discovery:** ReAct state is split across three fields, but only `scratchpad` is persisted:

```python
# ReActState (state_structures.py:56-62)
scratchpad: dict[str, Any]  # PERSISTED to session
forced_calls: int           # NOT persisted - resets on load!
guidance: list[str]         # NOT persisted - resets on load!
```

**Impact:** After session restore, `forced_calls` and `guidance` are lost.

**Fix opportunity:** `ReActScratchpad` unifies all three in one structure that can be fully serialized.

---

## Knowledge Gaps

### Task 06: ReAct Scratchpad

1. **Missing `from_dict()`/`to_dict()`** - `ReActScratchpad` class exists but lacks converters for legacy dict format

2. **Entry format conversion** - Need to decide how to convert legacy `{"type": "think", "thoughts": X, "next_action": Y}` to `ReActEntry(kind=THINK, content=???)`
   - Option A: Concatenate fields: `content = f"{thoughts} -> {next_action}"`
   - Option B: Store as JSON in content field
   - Option C: Extend `ReActEntry` with optional fields

3. **Timeline key access** - Multiple files use `scratchpad.get("timeline", [])` pattern that needs updating

### Task 08: Usage Metrics

1. **`cached_tokens` not in session files** - Old sessions lack this field, `from_dict()` handles via default=0

2. **Duplicate constants** - Two sets of key constants exist:
   - `usage_tracker.py:13-15`: `SESSION_USAGE_KEY_*`
   - `state_structures.py:14-16`: `USAGE_KEY_*`
   - Should consolidate to one location

3. **No tests for typed integration** - Existing tests use dict key access

---

## Migration Strategy

### Phase 1: Add ReAct Converters

```python
# Add to canonical.py ReActScratchpad class:
@classmethod
def from_dict(cls, data: dict[str, Any]) -> "ReActScratchpad":
    timeline = []
    for entry in data.get("timeline", []):
        timeline.append(_entry_from_legacy_dict(entry))
    return cls(
        timeline=timeline,
        forced_calls=data.get("forced_calls", 0),
        guidance=data.get("guidance", []),
    )

def to_dict(self) -> dict[str, Any]:
    return {
        "timeline": [_entry_to_legacy_dict(e) for e in self.timeline],
        "forced_calls": self.forced_calls,
        "guidance": self.guidance,
    }
```

### Phase 2: Update State Types

```python
# state_structures.py
@dataclass(slots=True)
class ReActState:
    scratchpad: ReActScratchpad = field(default_factory=ReActScratchpad)

@dataclass(slots=True)
class UsageState:
    last_call_usage: UsageMetrics = field(default_factory=UsageMetrics)
    session_total_usage: UsageMetrics = field(default_factory=UsageMetrics)
```

### Phase 3: Update Access Sites

**ReAct tool** (`react.py`):
```python
# Before:
entry = {"type": "think", "thoughts": thoughts, "next_action": next_action}
state_manager.append_react_entry(entry)

# After:
scratchpad = state_manager.get_react_scratchpad()
scratchpad.append(ReActEntryKind.THINK, f"{thoughts} -> {next_action}")
```

**Usage tracker** (`usage_tracker.py`):
```python
# Before:
last_call_usage["prompt_tokens"] = prompt_tokens

# After:
session.usage.last_call_usage = UsageMetrics(
    prompt_tokens=prompt_tokens,
    completion_tokens=completion_tokens,
    cost=cost,
)
```

### Phase 4: Update Serialization

```python
# state.py save_session()
session_data = {
    "react_scratchpad": self._session.react.scratchpad.to_dict(),
    "session_total_usage": self._session.usage.session_total_usage.to_dict(),
}

# state.py load_session()
from tunacode.types.canonical import ReActScratchpad, UsageMetrics

self._session.react.scratchpad = ReActScratchpad.from_dict(
    data.get("react_scratchpad", {})
)
self._session.usage.session_total_usage = UsageMetrics.from_dict(
    data.get("session_total_usage", {})
)
```

---

## Acceptance Criteria Verification

### Task 06: ReAct State Alignment

- [ ] `ReActState.scratchpad` is typed `ReActScratchpad`
- [ ] `append_react_entry()` accepts `ReActEntry` objects
- [ ] `tools/react.py` builds typed entries
- [ ] Session persistence handles legacy dict format
- [ ] All tests pass

### Task 08: Usage Metrics Consolidation

- [ ] `UsageState` fields are typed `UsageMetrics`
- [ ] No string key access patterns remain
- [ ] Session persistence handles legacy dict format
- [ ] Resource bar displays session cost correctly
- [ ] All tests pass

---

## References

### Canonical Type Definitions
- `src/tunacode/types/canonical.py:177-220` - ReAct types
- `src/tunacode/types/canonical.py:272-314` - Usage types

### Existing Tests
- `tests/unit/types/test_canonical.py:320-382` - ReActScratchpad tests
- `tests/unit/types/test_canonical.py:266-318` - UsageMetrics tests
- `tests/unit/core/test_usage_tracker.py` - Usage tracker tests

### Task Definitions
- `.claude/task/task_06_react_state_alignment.md`
- `.claude/task/task_08_usage_metrics_consolidation.md`

### Architecture Documentation
- `docs/refactoring/architecture-refactor-plan.md:360-383` - Chunk 6 (ReAct)
- `docs/refactoring/architecture-refactor-plan.md:406-428` - Chunk 8 (Usage)
