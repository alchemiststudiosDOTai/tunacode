# TunaCode Architecture Refactoring Plan

**Status**: Draft
**Created**: 2026-01-25
**Branch**: `claude/refactor-tunacode-architecture-Ox6gl`

---

## Executive Summary

TunaCode has clean dependency direction (ui → core → tools) but suffers from **state representation polymorphism**. The core pain points are:

1. **SessionState mega-dataclass** (40+ fields mixing unrelated concerns)
2. **Message format polymorphism** (4+ formats requiring defensive accessors everywhere)
3. **Tool call tracking duplication** (session.runtime.tool_calls, message parts, session.runtime.tool_call_args_by_id)
4. **Ad-hoc dicts** where typed structures would prevent bugs (todos, react_scratchpad, usage)

The rowing codebase refactor principles translate as follows:

| Rowing Principle | TunaCode Translation |
|------------------|----------------------|
| One canonical data structure | One canonical `Message` type, one `ToolCall` type |
| Centralized transformations | One place that serializes/deserializes messages |
| Leaf functions take canonical type | Tools receive typed `ToolContext`, not raw dicts |
| Enforce at boundary | Architecture tests for imports, type contracts |
| Explicit exceptions | Allowlist for streaming parsers (inherently messy) |

---

## Chunk 0: Define Target Types (Foundation)

**Goal**: Define the typed structures that will become canonical.

**Location**: `src/tunacode/types/canonical.py` (new file)

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Message Types (replace dict/object polymorphism)
# ─────────────────────────────────────────────────────────────────────────────

class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"

@dataclass(frozen=True, slots=True)
class MessagePart:
    """Base for message content parts."""
    pass

@dataclass(frozen=True, slots=True)
class TextPart(MessagePart):
    content: str

@dataclass(frozen=True, slots=True)
class ToolCallPart(MessagePart):
    tool_call_id: str
    tool_name: str
    args: dict[str, Any]

@dataclass(frozen=True, slots=True)
class ToolReturnPart(MessagePart):
    tool_call_id: str
    content: str

@dataclass(frozen=True, slots=True)
class Message:
    """Canonical message representation."""
    role: MessageRole
    parts: tuple[MessagePart, ...]
    timestamp: datetime | None = None

# ─────────────────────────────────────────────────────────────────────────────
# Tool Call Types (replace list[dict[str, Any]])
# ─────────────────────────────────────────────────────────────────────────────

class ToolCallStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass(frozen=True, slots=True)
class ToolCall:
    """Typed tool call record."""
    tool_call_id: str
    tool_name: str
    args: dict[str, Any]
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

# ─────────────────────────────────────────────────────────────────────────────
# ReAct Types (replace dict[str, Any])
# ─────────────────────────────────────────────────────────────────────────────

class ReActEntryKind(Enum):
    THINK = "think"
    ACT = "act"
    OBSERVE = "observe"

@dataclass(frozen=True, slots=True)
class ReActEntry:
    kind: ReActEntryKind
    content: str
    timestamp: datetime

@dataclass(slots=True)
class ReActScratchpad:
    timeline: list[ReActEntry]
    forced_calls: int = 0
    guidance: list[str] | None = None

# ─────────────────────────────────────────────────────────────────────────────
# Todo Types (replace list[dict[str, Any]])
# ─────────────────────────────────────────────────────────────────────────────

class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

@dataclass(frozen=True, slots=True)
class TodoItem:
    content: str
    status: TodoStatus
    active_form: str

# ─────────────────────────────────────────────────────────────────────────────
# Usage Types (replace ad-hoc dicts, complement existing TokenUsage/CostBreakdown)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class UsageMetrics:
    """API usage for a single call or cumulative session."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost: float = 0.0
```

**Deliverables**:
- [ ] Create `types/canonical.py` with above types
- [ ] Add `__all__` export and update `types/__init__.py`
- [ ] Write unit tests for serialization round-trips

---

## Chunk 1: Message Adapter Layer

**Goal**: Create a single place that converts between pydantic-ai messages and canonical messages.

**Location**: `src/tunacode/utils/messaging/adapter.py` (new file)

The adapter provides:
1. `to_canonical(pydantic_msg) -> Message`
2. `from_canonical(msg) -> pydantic_ai.messages.ModelMessage`
3. `get_content(msg_or_dict) -> str` (replaces 4-branch accessor)

**Key insight**: The current `message_utils.py` and `sanitize.py` show the pain of polymorphic access. With a single canonical type, these 300+ lines collapse to ~50.

**Deliverables**:
- [ ] Create `adapter.py` with bidirectional conversion
- [ ] Add exhaustive tests (all 4 current message formats)
- [ ] Create parity tests: `get_content(old) == get_content(to_canonical(old))`

---

## Chunk 2: Split SessionState

**Goal**: Decompose the 40-field mega-dataclass into cohesive sub-structures.

**Current `SessionState`** mixes:
- **Conversation state**: messages, thoughts, tool_calls
- **ReAct state**: react_scratchpad, react_forced_calls, react_guidance
- **Task state**: todos, task_hierarchy, recursive_context_stack
- **Runtime state**: spinner, is_streaming_active, streaming_panel
- **Usage state**: total_tokens, last_call_usage, session_total_usage
- **Config state**: user_config, current_model, yolo, debug_mode

**Target structure**:

```python
@dataclass
class ConversationState:
    messages: list[Message]  # canonical type
    thoughts: list[str]
    tool_calls: dict[str, ToolCall]  # keyed by tool_call_id

@dataclass
class ReActState:
    scratchpad: ReActScratchpad
    # No more separate react_forced_calls, react_guidance

@dataclass
class TaskState:
    todos: list[TodoItem]
    hierarchy: dict[str, Any]  # tree structure TBD
    context_stack: list[RecursiveContext]
    current_depth: int = 0
    max_depth: int = 5

@dataclass
class RuntimeState:
    """Ephemeral state not persisted."""
    spinner: Any | None = None
    is_streaming: bool = False
    streaming_panel: Any | None = None
    operation_cancelled: bool = False

@dataclass
class UsageState:
    estimated_tokens: int = 0
    max_tokens: int = 0
    last_call: UsageMetrics = field(default_factory=UsageMetrics)
    session_total: UsageMetrics = field(default_factory=UsageMetrics)

@dataclass
class SessionState:
    """Composed state - delegates to focused sub-states."""
    conversation: ConversationState
    react: ReActState
    task: TaskState
    runtime: RuntimeState
    usage: UsageState
    # Config kept at top level (loaded once, rarely mutated)
    user_config: UserConfig
    current_model: ModelName
    session_id: str
    # ... other identity fields
```

**Deliverables**:
- [ ] Create sub-dataclasses in `types/state_components.py`
- [ ] Update `SessionState` to compose them
- [ ] Update `StateManager` accessors (e.g., `session.react.scratchpad`)
- [ ] Migrate callers incrementally (shim old accessors temporarily)

---

## Chunk 3: Parity Harness for Messages

**Goal**: Prove the canonical message path produces identical behavior.

**Pattern**: Run both old and new paths, assert equality.

```python
def test_message_parity():
    """Old path and new path produce same serialized output."""
    old_messages = [...]  # existing mixed format

    # Old path: current serialize/deserialize
    old_serialized = state_manager._serialize_messages()
    old_restored = state_manager._deserialize_messages(old_serialized)

    # New path: canonical adapter
    canonical = [to_canonical(m) for m in old_messages]
    new_serialized = [serialize_message(m) for m in canonical]
    new_restored = [deserialize_message(m) for m in new_serialized]

    # Compare
    assert old_serialized == new_serialized
    assert old_restored == new_restored
```

**Deliverables**:
- [ ] Create `tests/parity/test_message_parity.py`
- [ ] Collect real message samples from session files
- [ ] Run parity on all 4 message format variants

---

## Chunk 4: Port Sanitize to Canonical

**Goal**: Simplify `sanitize.py` by operating on canonical types.

**Current pain** (631 lines): Polymorphic accessors for dict/object, separate handling of parts/tool_calls.

**Target** (~100 lines):
```python
def remove_dangling_tool_calls(messages: list[Message]) -> list[Message]:
    """Remove tool calls without matching returns."""
    call_ids = {p.tool_call_id for m in messages for p in m.parts if isinstance(p, ToolCallPart)}
    return_ids = {p.tool_call_id for m in messages for p in m.parts if isinstance(p, ToolReturnPart)}
    dangling = call_ids - return_ids

    def filter_message(msg: Message) -> Message:
        clean_parts = tuple(
            p for p in msg.parts
            if not (isinstance(p, ToolCallPart) and p.tool_call_id in dangling)
        )
        return Message(role=msg.role, parts=clean_parts, timestamp=msg.timestamp)

    return [filter_message(m) for m in messages if filter_message(m).parts]
```

**Deliverables**:
- [ ] Create `core/agents/resume/sanitize_canonical.py` (new implementation)
- [ ] Add parity tests against old `sanitize.py`
- [ ] Once parity proven, replace old implementation

---

## Chunk 5: Tool Call Registry

**Goal**: Single source of truth for tool call state.

**Current problem**: Tool calls tracked in 3 places:
1. `session.runtime.tool_calls: list[dict[str, Any]]`
2. `session.runtime.tool_call_args_by_id: dict[str, dict]`
3. Message parts (ToolCallPart in pydantic-ai messages)

**Target**: One `dict[str, ToolCall]` keyed by tool_call_id.

```python
class ToolCallRegistry:
    """Single source of truth for tool call lifecycle."""
    _calls: dict[str, ToolCall]

    def register(self, tool_call_id: str, tool_name: str, args: dict) -> ToolCall:
        call = ToolCall(tool_call_id, tool_name, args, status=PENDING)
        self._calls[tool_call_id] = call
        return call

    def start(self, tool_call_id: str) -> None:
        self._calls[tool_call_id] = replace(
            self._calls[tool_call_id],
            status=RUNNING,
            started_at=datetime.now(UTC)
        )

    def complete(self, tool_call_id: str, result: str) -> None:
        self._calls[tool_call_id] = replace(
            self._calls[tool_call_id],
            status=COMPLETED,
            result=result,
            completed_at=datetime.now(UTC)
        )

    def get_pending(self) -> list[ToolCall]:
        return [c for c in self._calls.values() if c.status == PENDING]
```

**Deliverables**:
- [ ] Create `core/tool_registry.py`
- [ ] Integrate with `ToolHandler` and `tool_executor.py`
- [ ] Remove `tool_call_args_by_id` and `tool_calls` list from SessionState

---

## Chunk 6: Migrate ReAct to Typed Structure

**Goal**: Replace `react_scratchpad: dict[str, Any]` with `ReActScratchpad`.

**Current**:
```python
react_scratchpad: dict[str, Any] = field(default_factory=lambda: {"timeline": []})
react_forced_calls: int = 0
react_guidance: list[str] = field(default_factory=list)
```

**Target**:
```python
react: ReActState = field(default_factory=ReActState)
# Where ReActState contains ReActScratchpad, forced_calls, guidance
```

**Deliverables**:
- [ ] Update `StateManager.append_react_entry()` to use typed `ReActEntry`
- [ ] Update `create_react_tool()` to work with typed scratchpad
- [ ] Update serialization in `save_session()`/`load_session()`
- [ ] Remove the three separate fields

---

## Chunk 7: Migrate Todos to Typed Structure

**Goal**: Replace `todos: list[dict[str, Any]]` with `list[TodoItem]`.

**Current**:
```python
todos: list[dict[str, Any]] = field(default_factory=list)
```

**Target**:
```python
todos: list[TodoItem] = field(default_factory=list)
```

**Deliverables**:
- [ ] Update `create_todowrite_tool()` to produce `TodoItem`
- [ ] Update UI rendering (if any)
- [ ] Update serialization

---

## Chunk 8: Usage Tracking Consolidation

**Goal**: Use existing `TokenUsage`/`CostBreakdown` types and new `UsageMetrics`.

**Current**:
```python
last_call_usage: dict = field(default_factory=lambda: {"prompt_tokens": 0, ...})
session_total_usage: dict = field(default_factory=lambda: {"prompt_tokens": 0, ...})
```

**Problem**: We have `TokenUsage` and `CostBreakdown` dataclasses in `types/dataclasses.py` but they're not used in SessionState!

**Target**:
```python
usage: UsageState = field(default_factory=UsageState)
# Where UsageState uses UsageMetrics for both last_call and session_total
```

**Deliverables**:
- [ ] Consolidate with existing `TokenUsage`/`CostBreakdown`
- [ ] Update usage tracking in `orchestrator.py`
- [ ] Update cost display in UI

---

## Chunk 9: Architecture Tests

**Goal**: Encode architectural rules as tests that fail when violated.

```python
# tests/architecture/test_imports.py

def test_core_does_not_import_ui():
    """Core layer must not depend on UI layer."""
    core_files = glob("src/tunacode/core/**/*.py")
    for path in core_files:
        content = Path(path).read_text()
        assert "from tunacode.ui" not in content
        assert "import tunacode.ui" not in content

def test_tools_does_not_import_core():
    """Tools layer must not depend on core layer (only protocols)."""
    tools_files = glob("src/tunacode/tools/**/*.py")
    for path in tools_files:
        content = Path(path).read_text()
        # Allowed: from tunacode.types.state import StateManagerProtocol
        # Forbidden: from tunacode.core import ...
        assert "from tunacode.core" not in content

def test_session_state_field_count():
    """SessionState should not exceed 15 fields after decomposition."""
    import inspect
    from tunacode.core.state import SessionState
    fields = [f for f in inspect.get_annotations(SessionState)]
    assert len(fields) <= 15, f"SessionState has {len(fields)} fields, expected <= 15"
```

**Deliverables**:
- [ ] Create `tests/architecture/test_imports.py`
- [ ] Create `tests/architecture/test_state_structure.py`
- [ ] Add to CI

---

## Chunk 10: Delete Legacy Code

**Goal**: Remove dead code and old implementations.

After each chunk achieves parity:
1. Delete old implementation
2. Remove shims/adapters
3. Update imports

**Candidates for deletion** (after migration):
- `message_utils.py` polymorphic accessors (replace with adapter)
- Duplicate tracking in `session.runtime.tool_calls` (replace with registry)
- Ad-hoc dict factories in SessionState (replace with typed defaults)

---

## Migration Strategy

### Phase 1: Foundations (Chunks 0-1)
- Define canonical types
- Build adapter layer
- No behavioral changes

### Phase 2: Parity (Chunks 2-4)
- Split SessionState (with temporary shims)
- Prove message parity
- Port sanitize

### Phase 3: Consolidation (Chunks 5-8)
- Tool call registry
- Typed ReAct/Todos/Usage
- Remove shims

### Phase 4: Enforcement (Chunks 9-10)
- Architecture tests
- Delete legacy

---

## Testing Strategy

Each chunk has 3 test categories:

1. **Unit tests**: New types work correctly in isolation
2. **Parity tests**: New path == old path for all inputs
3. **Integration tests**: End-to-end with actual LLM calls

Parity tests are CRITICAL. They let us migrate incrementally with confidence.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking session persistence | Parity tests on real session files |
| Breaking pydantic-ai integration | Keep adapter layer thin, test all message types |
| Too many changes at once | Each chunk is independently deployable |
| Performance regression | Benchmark serialization before/after |

---

## Open Questions

1. **Frozen vs mutable dataclasses**: Current plan uses `frozen=True` for Message/ToolCall. Need to verify this doesn't break pydantic-ai integration.

2. **Streaming parts**: During streaming, parts are built incrementally. How do frozen dataclasses interact with this? May need a `StreamingMessage` builder.

3. **Backward compat for sessions**: Old session files have dict-based messages. Adapter must handle gracefully.

---

## Next Steps

1. Review this plan
2. Start with Chunk 0 (define types)
3. Parallel: Set up architecture tests (Chunk 9) to prevent regression
