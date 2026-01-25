---
title: "Task 06 & 08: ReAct State & Usage Metrics Alignment – Plan"
phase: Plan
date: "2026-01-25T17:46:24"
owner: "Claude"
parent_research: "memory-bank/research/2026-01-25_17-43-52_task-06-08-react-usage-alignment.md"
git_commit_at_plan: "94f6ffd8"
tags: [plan, react, usage-metrics, typing, coding]
---

## Goal

Migrate ReAct scratchpad and usage metrics from untyped `dict[str, Any]` to typed dataclasses (`ReActScratchpad`, `UsageMetrics`) already defined in `canonical.py`, enabling type safety and fixing the ReAct state persistence bug.

**Non-goals:**
- Deployment or observability changes
- New features beyond type migration
- Performance optimization

---

## Scope & Assumptions

**In scope:**
- Add `from_dict()`/`to_dict()` converters to `ReActScratchpad` and `ReActEntry`
- Change `state_structures.py` field types from dict to dataclass
- Update all access sites to use attribute access instead of dict key access
- Update serialization in `state.py`
- Update existing tests to use typed access

**Out of scope:**
- New test files (update existing only)
- Changes to UI layout or behavior
- Changes to agent logic beyond type migration

**Assumptions:**
- `UsageMetrics.from_dict()`/`to_dict()` already exist and are correct
- NO backward compatibility - old sessions may break (acceptable)
- Clean typed format only

---

## Deliverables

1. `ReActEntry.from_dict()`/`to_dict()` methods in `canonical.py`
2. `ReActScratchpad.from_dict()`/`to_dict()` methods in `canonical.py`
3. Updated `ReActState` type in `state_structures.py`
4. Updated `UsageState` type in `state_structures.py`
5. All access sites migrated to attribute access
6. Serialization updated to use converters
7. Updated tests passing

---

## Readiness

**Preconditions:**
- [x] `ReActScratchpad` dataclass exists (`canonical.py:200-220`)
- [x] `ReActEntry` dataclass exists (`canonical.py:191-198`)
- [x] `UsageMetrics` dataclass exists with converters (`canonical.py:272-313`)
- [x] `TodoItem` migration pattern available as reference (`canonical.py:236-264`)
- [x] Git clean on branch `task-06-08-react-usage-alignment`

---

## Milestones

| ID | Name | Description |
|----|------|-------------|
| M1 | Converters | Add `from_dict()`/`to_dict()` to ReAct types |
| M2 | Type Changes | Update `state_structures.py` field types |
| M3 | Access Sites | Migrate all dict access to attribute access |
| M4 | Tests | Update existing tests to pass |

---

## Work Breakdown (Tasks)

### Task 1: Add ReActEntry converters
**Milestone:** M1
**Estimate:** S
**Dependencies:** None

Add `from_dict()` and `to_dict()` methods to `ReActEntry` class.

**Files:**
- `src/tunacode/types/canonical.py:191-198`

**Implementation:**
```python
@classmethod
def from_dict(cls, data: dict[str, Any]) -> "ReActEntry":
    """Convert from dict (serialization only)."""
    return cls(
        kind=ReActEntryKind(data["kind"]),
        content=data["content"],
        timestamp=datetime.fromisoformat(data["timestamp"]),
    )

def to_dict(self) -> dict[str, Any]:
    """Convert to dict for serialization."""
    return {
        "kind": self.kind.value,
        "content": self.content,
        "timestamp": self.timestamp.isoformat(),
    }
```

**Acceptance test:**
- Round-trip: `ReActEntry.from_dict(entry.to_dict())` equals original

---

### Task 2: Add ReActScratchpad converters
**Milestone:** M1
**Estimate:** S
**Dependencies:** Task 1

Add `from_dict()` and `to_dict()` methods to `ReActScratchpad` class.

**Files:**
- `src/tunacode/types/canonical.py:200-220`

**Implementation:**
```python
@classmethod
def from_dict(cls, data: dict[str, Any]) -> "ReActScratchpad":
    """Convert from dict (serialization only)."""
    return cls(
        timeline=[ReActEntry.from_dict(e) for e in data.get("timeline", [])],
        forced_calls=data.get("forced_calls", 0),
        guidance=data.get("guidance", []),
    )

def to_dict(self) -> dict[str, Any]:
    """Convert to dict for serialization."""
    return {
        "timeline": [e.to_dict() for e in self.timeline],
        "forced_calls": self.forced_calls,
        "guidance": list(self.guidance),
    }
```

**Acceptance test:**
- Round-trip: `ReActScratchpad.from_dict(scratchpad.to_dict())` produces equivalent object

---

### Task 3: Update ReActState type
**Milestone:** M2
**Estimate:** S
**Dependencies:** Task 2

Change `ReActState.scratchpad` from `dict[str, Any]` to `ReActScratchpad`. Remove redundant `forced_calls` and `guidance` fields (now in scratchpad).

**Files:**
- `src/tunacode/types/state_structures.py:55-62`

**Before:**
```python
@dataclass(slots=True)
class ReActState:
    scratchpad: dict[str, Any] = field(default_factory=_default_react_scratchpad)
    forced_calls: int = DEFAULT_FORCED_CALLS
    guidance: list[str] = field(default_factory=list)
```

**After:**
```python
@dataclass(slots=True)
class ReActState:
    scratchpad: ReActScratchpad = field(default_factory=ReActScratchpad)
```

**Acceptance test:**
- `ReActState()` creates instance with typed `scratchpad`

---

### Task 4: Update UsageState type
**Milestone:** M2
**Estimate:** S
**Dependencies:** None

Change `UsageState` fields from `dict[str, int | float]` to `UsageMetrics`.

**Files:**
- `src/tunacode/types/state_structures.py:87-92`

**Before:**
```python
@dataclass(slots=True)
class UsageState:
    last_call_usage: dict[str, int | float] = field(default_factory=_default_usage_metrics)
    session_total_usage: dict[str, int | float] = field(default_factory=_default_usage_metrics)
```

**After:**
```python
@dataclass(slots=True)
class UsageState:
    last_call_usage: UsageMetrics = field(default_factory=UsageMetrics)
    session_total_usage: UsageMetrics = field(default_factory=UsageMetrics)
```

**Acceptance test:**
- `UsageState()` creates instance with typed metrics having `.cost` attribute

---

### Task 5: Update StateManager ReAct helpers
**Milestone:** M3
**Estimate:** M
**Dependencies:** Task 3

Update methods that access ReAct state to use typed scratchpad.

**Files:**
- `src/tunacode/core/state.py:206-215` (helper methods)
- `src/tunacode/core/state.py:354, 409-410` (serialization)

**Changes:**
1. `get_react_scratchpad()` returns `ReActScratchpad`
2. `append_react_entry()` accepts `ReActEntryKind` and `content`
3. Serialization uses `.to_dict()` and `.from_dict()`

**Acceptance test:**
- `state_manager.append_react_entry(ReActEntryKind.THINK, "test")` succeeds

---

### Task 6: Update react.py tool
**Milestone:** M3
**Estimate:** S
**Dependencies:** Task 5

Update tool to create typed entries instead of dicts.

**Files:**
- `src/tunacode/tools/react.py:40-72`

**Before:**
```python
entry = {"type": "think", "thoughts": thoughts, "next_action": next_action}
state_manager.append_react_entry(entry)
```

**After:**
```python
content = f"{thoughts} -> {next_action}" if next_action else thoughts
state_manager.append_react_entry(ReActEntryKind.THINK, content)
```

**Acceptance test:**
- `think()` tool creates typed `ReActEntry` in timeline

---

### Task 7: Update usage_tracker.py
**Milestone:** M3
**Estimate:** M
**Dependencies:** Task 4

Convert dict key access to attribute access.

**Files:**
- `src/tunacode/core/agents/callbacks/usage_tracker.py:30-55`

**Before:**
```python
last_call_usage["prompt_tokens"] = prompt_tokens
session_total_usage["cost"] += cost
```

**After:**
```python
session.usage.last_call_usage = UsageMetrics(
    prompt_tokens=prompt_tokens,
    completion_tokens=completion_tokens,
    cached_tokens=cached_tokens,
    cost=cost,
)
session.usage.session_total_usage.add(session.usage.last_call_usage)
```

**Acceptance test:**
- `update_usage()` populates typed metrics with `.cost` attribute

---

### Task 8: Update UI access sites
**Milestone:** M3
**Estimate:** S
**Dependencies:** Task 4

Update app.py and main.py to use attribute access for usage display.

**Files:**
- `src/tunacode/ui/app.py:258-259, 474`
- `src/tunacode/ui/main.py:219`

**Before:**
```python
cost = session_total_usage.get("cost", 0.0)
```

**After:**
```python
cost = session.usage.session_total_usage.cost
```

**Acceptance test:**
- Resource bar displays session cost correctly

---

### Task 9: Update commands/__init__.py
**Milestone:** M3
**Estimate:** S
**Dependencies:** Tasks 3, 4

Update `/clear` command to reset with typed defaults.

**Files:**
- `src/tunacode/ui/commands/__init__.py:87-89, 105-109`

**Changes:**
- Reset ReAct: `state.react.scratchpad.clear()` or `state.react = ReActState()`
- Reset Usage: `state.usage = UsageState()`

**Acceptance test:**
- `/clear` command leaves state with typed fields

---

### Task 10: Update tests
**Milestone:** M4
**Estimate:** S
**Dependencies:** Tasks 5-9

Update existing tests to use attribute access.

**Files:**
- `tests/unit/types/test_canonical.py:320-382` (ReActScratchpad)
- `tests/unit/types/test_canonical.py:266-318` (UsageMetrics)
- `tests/unit/core/test_usage_tracker.py:24-39`

**Changes:**
- Update dict access patterns to attribute access
- Add converter round-trip tests if missing

**Acceptance test:**
- `uv run pytest tests/unit/` passes

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Old sessions won't load | Low | Acceptable - clean break |
| ReactSnapshotManager breakage | Medium | Check reads in main.py:148-236 after Task 5 |

---

## Test Strategy

**Existing tests to update:**
- `test_canonical.py` - verify converter round-trips
- `test_usage_tracker.py` - verify attribute access works

**No new test files.** Each task's acceptance test validates via existing test updates or manual verification.

Run after each milestone:
```bash
uv run pytest tests/unit/ -v
uv run ruff check src/tunacode/
```

---

## References

- Research doc: `memory-bank/research/2026-01-25_17-43-52_task-06-08-react-usage-alignment.md`
- TodoItem pattern: `canonical.py:236-264`
- ReAct types: `canonical.py:177-220`
- Usage types: `canonical.py:272-314`
- Task definitions: `.claude/task/task_06_react_state_alignment.md`, `.claude/task/task_08_usage_metrics_consolidation.md`

---

## Final Gate

| Metric | Value |
|--------|-------|
| Plan path | `memory-bank/plan/2026-01-25_17-46-24_task-06-08-react-usage-alignment.md` |
| Milestones | 4 |
| Tasks | 10 |
| Ready for coding | Yes |

**Next command:** `/context-engineer:execute "memory-bank/plan/2026-01-25_17-46-24_task-06-08-react-usage-alignment.md"`
