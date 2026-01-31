# Research – Pydantic Minimal Layer

**Date:** 2026-01-30
**Phase:** Research
**Topic:** Smallest layer pydantic provides in tunacode

---

## Summary

Pydantic provides exactly **one minimal layer**: a **boundary interface** between the external `pydantic-ai` library and the internal canonical type system. Core business logic, state management, tools, and UI are all completely independent of pydantic.

---

## Architecture

```
pydantic-ai (external)
    │
    ▼
┌────────────────────────────────────────┐
│  BOUNDARY LAYER (pydantic-dependent)   │
│  - types/pydantic_ai.py                │
│  - core/agents/main.py                 │
│  - core/agents/agent_config/           │
│  - utils/messaging/adapter.py          │
└────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────┐
│  CORE LAYER (pydantic-INDEPENDENT)     │
│  - types/canonical.py (dataclasses)    │
│  - core/state.py (dataclasses)         │
│  - tools/*.py (pure functions)         │
│  - ui/* (canonical types only)         │
└────────────────────────────────────────┘
```

---

## Key Finding: Zero Direct BaseModel Usage

The codebase has **no pydantic `BaseModel` subclasses**. Internal types use:
- `@dataclass(frozen=True, slots=True)`
- Enums for role/kind constants
- Type aliases for semantic clarity

---

## The Minimal Contract

Pydantic provides exactly **4 things** to tunacode:

| # | Symbol | Location | Purpose |
|---|--------|----------|---------|
| 1 | `Agent` | `types/pydantic_ai.py:20` | Re-exported as `PydanticAgent` for creating LLM agents |
| 2 | `ModelRequest`, `ModelResponse` | `types/pydantic_ai.py:22-23` | Re-exported for message serialization |
| 3 | `ModelRetry` | `tools/decorators.py:15` | Exception for tool retry logic |
| 4 | `TypeAdapter` | `core/state.py:181` | JSON dump/load for message persistence |

---

## Dependency Direction

```
External: pydantic-ai
    ↓
Boundary: types/pydantic_ai.py (imports pydantic-ai)
    ↓
Adapter: utils/messaging/adapter.py (converts pydantic-ai ↔ canonical)
    ↓
Core: types/canonical.py (dataclasses, enums, type aliases)
```

**Rule:** Core never imports pydantic. Only the boundary layer knows about pydantic-ai.

---

## Files by Layer

### Boundary Layer (pydantic-dependent)

**Type Adapter:**
- `src/tunacode/types/pydantic_ai.py` - Central isolation module for all pydantic-ai imports

**Agent Configuration:**
- `src/tunacode/core/agents/main.py` - Agent orchestration
- `src/tunacode/core/agents/agent_config/` - Agent and tool configuration
- `src/tunacode/core/agents/resume/` - Resume handling

**Message Conversion:**
- `src/tunacode/utils/messaging/adapter.py` - Bidirectional conversion between pydantic-ai and canonical types

**UI Output (boundary only):**
- `src/tunacode/ui/headless/output.py` - Extracts output from `ModelResponse`
- `src/tunacode/ui/app.py` - UI handling of `ModelResponse`
- `src/tunacode/ui/repl_support.py` - REPL support

### Core Layer (pydantic-independent)

**Canonical Types:**
- `src/tunacode/types/canonical.py` - All message types as dataclasses
- `src/tunacode/types/base.py` - Type aliases
- `src/tunacode/types/callbacks.py` - Callback type hints

**State Management:**
- `src/tunacode/core/state.py` - `SessionState` as dataclass

**Tools:**
- `src/tunacode/tools/*.py` - Pure Python functions, no pydantic

**UI Rendering:**
- `src/tunacode/ui/screens/` - Textual widgets, canonical types only

---

## Usage Patterns

### 1. Agent Creation (pydantic-ai boundary)

```python
# src/tunacode/core/agents/main.py
from tunacode.types.pydantic_ai import Agent as PydanticAgent

agent = PydanticAgent(
    model=model_name,
    tools=tool_list,
    system_prompt=system_prompt,
)
```

### 2. Message Serialization (TypeAdapter)

```python
# src/tunacode/core/state.py:181-229
from pydantic import TypeAdapter
from pydantic_ai.messages import ModelMessage

msg_adapter = TypeAdapter(ModelMessage)
serialized = msg_adapter.dump_python(msg, mode="json")
deserialized = msg_adapter.validate_python(item)
```

### 3. Type Conversion (adapter layer)

```python
# src/tunacode/utils/messaging/adapter.py
def message_to_canonical(msg: ModelMessage) -> CanonicalMessage:
    """Convert pydantic-ai message to canonical type."""
    # Implementation converts parts and role

def canonical_message_to_pydantic(msg: CanonicalMessage) -> ModelMessage:
    """Convert canonical message back to pydantic-ai format."""
    # Implementation rebuilds pydantic-ai message
```

---

## What Would Break If Pydantic Were Removed?

**Would break (boundary only):**
- Agent creation (needs `PydanticAgent`)
- Message serialization (needs `TypeAdapter`)
- Tool retry logic (needs `ModelRetry` exception)

**Would NOT break (core unaffected):**
- State management (`SessionState` is pure dataclass)
- Message handling (`CanonicalMessage` is pure dataclass)
- Tool execution (pure Python functions)
- UI rendering (Textual + canonical types)
- Configuration (plain dicts + validation functions)

---

## Design Rationale

1. **Isolation:** `types/pydantic_ai.py` contains all pydantic-ai imports in one place
2. **Decoupling:** Core logic depends on `CanonicalMessage`, not `ModelResponse`
3. **Migration path:** Could replace pydantic-ai by changing only the boundary layer
4. **Performance:** Dataclasses with slots are faster and lighter than BaseModel
5. **Testability:** Core types have no external dependency baggage

---

## File Count Summary

| Layer | Pydantic-Dependent Files | Total Files |
|-------|-------------------------|-------------|
| Boundary | ~12 | ~12 |
| Core | 0 | ~30+ |
| Tools | 0 | ~20 |
| UI | 0 | ~15 |

**Result:** Pydantic is confined to ~12 files at the boundary. Core has zero pydantic dependency.

---

## Related

- [[Dependency Direction]] - Gate 2 of quality gates
- [[Canonical Type System]] - Internal type architecture
- [[Adapter Pattern]] - Message conversion layer
