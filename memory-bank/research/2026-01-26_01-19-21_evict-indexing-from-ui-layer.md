# Research – Evict Indexing Logic from UI Layer

**Date:** 2026-01-26
**Owner:** claude
**Phase:** Research
**Ticket:** t-ea8a
**Git Branch:** ui-dependency-direction
**Git Commit:** d93e8d4b

---

## Goal

Summarize all *existing knowledge* about the UI → Indexing dependency violation before implementing the fix. The UI layer currently directly imports and manages the CodeIndex background task, violating the 'Dependency Direction' rule (Gate 2) from CLAUDE.md where UI should only know about Core.

### Additional Search

```bash
grep -ri "indexing" .claude/
```

---

## Findings

### Relevant Files & Why They Matter

| File | Purpose | Issue |
|------|---------|-------|
| [`src/tunacode/ui/startup.py:10-11`](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/ui/startup.py#L10-L11) | Orchestrates startup indexing | **Gate 2 violation**: UI imports `from tunacode.indexing import CodeIndex` |
| [`src/tunacode/ui/app.py:194`](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/ui/app.py#L194) | Launches indexing worker | UI directly launches `run_startup_index(self.rich_log)` as background task |
| [`src/tunacode/indexing/code_index.py:18-54`](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/indexing/code_index.py#L18-L54) | CodeIndex singleton with state | Thread-safe singleton, manages in-memory file index |
| [`src/tunacode/indexing/constants.py:7`](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/indexing/constants.py#L7) | `QUICK_INDEX_THRESHOLD = 1000` | Defines small vs large codebase strategy |
| [`src/tunacode/tools/glob.py:12`](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/tools/glob.py#L12) | Tools uses CodeIndex | **Correct pattern**: tools → indexing is valid dependency flow |
| [`layers.dot:29`](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/layers.dot#L29) | Dependency graph | Shows `ui -> indexing [label="2", penwidth=1.4];` (2 violation links) |
| [`deps.dot:570-571`](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/deps.dot#L570-L571) | Module-level deps | `tunacode_ui_startup -> tunacode_indexing;` and `tunacode_indexing_constants;` |
| [`src/tunacode/core/state.py:117`](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/core/state.py#L117) | StateManager class | **Missing**: No indexing service property or lifecycle management |

---

## Key Patterns / Solutions Found

### 1. **Gate 2 Violation: Dependency Direction**

**Rule:** "Dependencies flow inward, never backward: ui → core → tools → utils/types"

**Current State:**
```
ui → indexing  ❌ VIOLATION
tools → indexing  ✓ CORRECT
```

**Evidence:**
- `startup.py:10` imports `CodeIndex` directly
- `startup.py:11` imports `QUICK_INDEX_THRESHOLD` from indexing
- `app.py:194` directly orchestrates indexing background worker

**Required Fix:**
```
ui → core → indexing  ✓ CORRECT
```

---

### 2. **State Pollution: UI Widgets in Core Logic**

**Location:** `startup.py:16`

```python
async def run_startup_index(rich_log: RichLog) -> None:
```

**Issue:**
- Function receives Textual-specific `RichLog` widget
- Indexing logic knows about UI implementation details
- Violates: "If core needs UI state, you're violating the boundary. Extract what you need and pass it as a plain argument."

**Solution Pattern (from CLAUDE.md):**
```python
# WRONG:
def run_agent(app: TunaCodeApp):
    app.notify_status("Running")

# RIGHT:
def run_agent(notify_status: Callable[[str], None]):
    notify_status("Running")
```

**Proposed Fix:**
```python
# Core layer: callback protocol
from collections.abc import Callable

async def start_startup_index(
    status_callback: Callable[[str, str], None] | None = None
) -> tuple[int, int | None, bool]:
    # ... indexing logic ...
    if status_callback:
        status_callback(message, style)
    return indexed, total, is_partial
```

---

### 3. **Two-Phase Indexing Strategy**

**Location:** `startup.py:23-35`

**Logic:**
```python
def do_index() -> tuple[int, int | None, bool]:
    index = CodeIndex.get_instance()
    total = index.quick_count()

    if total < QUICK_INDEX_THRESHOLD:  # < 1000 files
        index.build_index()            # Full index immediately
        return len(index._all_files), None, False
    else:
        count = index.build_priority_index()  # Priority dirs first
        return count, total, True
```

**Strategy:**
| Repo Size | Behavior |
|-----------|----------|
| Small (<1000 files) | Full index, immediate completion |
| Large (≥1000 files) | Priority index (src/, lib/, core/) first, then expand in background |

**Priority Directories:** `{"src", "lib", "app", "packages", "core", "internal"}`

---

### 4. **Communication Pattern: RichLog Writes Only**

**Current Implementation:**

| Event | Code Location | Style | Message |
|-------|---------------|-------|---------|
| Full index complete | `startup.py:55-58` | `STYLE_SUCCESS` (#4ec9b0) | `Code cache built: {count} files indexed` |
| Partial index done | `startup.py:38-43` | `STYLE_MUTED` (#808080) | `Code cache: {indexed}/{total} files indexed, expanding...` |
| Expansion complete | `startup.py:52-54` | `STYLE_SUCCESS` (#4ec9b0) | `Code cache built: {final_count} files indexed` |

**No Callback Pattern:**
- No streaming progress updates
- Only three discrete messages at phase boundaries
- No error handling communicated to UI (silent failures)

**Threading:**
```python
# Thread pool delegation for blocking I/O
indexed, total, is_partial = await asyncio.to_thread(do_index)
final_count = await asyncio.to_thread(do_expand)
```

---

### 5. **CodeIndex Singleton State**

**Location:** `code_index.py:18-54`

**Instance Variables:**
```python
_basename_to_paths: dict[str, list[Path]]      # filename → paths
_path_to_imports: dict[Path, set[str]]         # file → import modules
_all_files: set[Path]                          # all indexed files
_class_definitions: dict[str, list[Path]]      # class name → files
_function_definitions: dict[str, list[Path]]   # function name → files
_dir_cache: dict[Path, list[Path]]             # directory listing cache
_cache_timestamps: dict[Path, float]           # cache freshness (TTL=5s)
_indexed: bool                                  # full index complete
_partial_indexed: bool                          # priority index done
```

**Thread Safety:**
- `threading.RLock()` at instance level
- Class-level lock for singleton creation
- Double-checked locking pattern in `get_instance()`

**Configuration:**
- Cache TTL: 5 seconds
- File size limit: 10MB max
- Indexed extensions: 50+ (.py, .js, .ts, .java, .go, .rs, etc.)

---

## Data Flow Diagram

### Current (Violating) Flow

```
┌─────────────────────────────────────────────────────────────┐
│ UI Layer (startup.py, app.py)                               │
│                                                             │
│ 1. app.py:194 → run_worker(run_startup_index(self.rich_log))│
│ 2. startup.py:16 → receives RichLog widget                  │
│ 3. startup.py:25 → CodeIndex.get_instance()                │
│ 4. startup.py:35,51 → asyncio.to_thread(do_index)           │
│ 5. startup.py:43,54,58 → rich_log.write(msg)                │
└─────────────────────────────────────────────────────────────┘
                              ↓
                ❌ VIOLATION: UI → indexing direct import
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Indexing Layer (CodeIndex)                                  │
│ - Singleton instance management                             │
│ - File system scanning                                      │
│ - In-memory index structures                                │
└─────────────────────────────────────────────────────────────┘
```

### Required (Correct) Flow

```
┌─────────────────────────────────────────────────────────────┐
│ UI Layer (app.py)                                           │
│                                                             │
│ 1. app.py → self.state_manager.indexing_service.start()     │
│ 2. Define status_callback(message, style) → Text + RichLog  │
│ 3. Render formatted messages to self.rich_log               │
└─────────────────────────────────────────────────────────────┘
                              ↓
                ✓ CORRECT: UI → Core (indexing_service)
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Core Layer (indexing_service.py)                            │
│                                                             │
│ 1. IndexingService class                                    │
│ 2. start_startup_index(callback) → orchestrates indexing    │
│ 3. expand_index(callback) → background expansion            │
│ 4. Threading decisions (asyncio.to_thread)                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
                ✓ CORRECT: Core → Indexing (infrastructure)
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Indexing Layer (CodeIndex)                                  │
│ - Singleton instance management                             │
│ - File system scanning                                      │
│ - In-memory index structures                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Architectural Violations Summary

| Violation | Location | Rule | Impact |
|-----------|----------|------|--------|
| **UI imports indexing** | `startup.py:10-11` | Gate 2: Dependency Direction | Tight coupling, backward dependency |
| **UI widget passed to logic** | `startup.py:16` | Gate 2: "Extract what you need" | Core logic knows about Textual |
| **No Core service for indexing** | Missing in `state.py` | High cohesion, single responsibility | Indexing lifecycle scattered in UI |
| **Background task in UI** | `app.py:194` | Low coupling, module boundaries | UI owns infrastructure concern |

---

## Proposed Implementation Plan

### Step 1: Create Core Indexing Service

**File:** `src/tunacode/core/indexing_service.py` (NEW)

```python
"""Indexing orchestration service - manages CodeIndex lifecycle."""
from collections.abc import Callable
import asyncio

from tunacode.indexing import CodeIndex
from tunacode.indexing.constants import QUICK_INDEX_THRESHOLD

class IndexingService:
    """Manages code indexing lifecycle for the application."""

    def __init__(self, status_callback: Callable[[str, str], None] | None = None) -> None:
        self._status_callback = status_callback

    async def start_startup_index(self) -> tuple[int, int | None, bool]:
        """Build startup index with dynamic sizing.

        Returns:
            Tuple of (indexed_count, total_or_none, is_partial)
        """
        def do_index() -> tuple[int, int | None, bool]:
            index = CodeIndex.get_instance()
            total = index.quick_count()

            if total < QUICK_INDEX_THRESHOLD:
                index.build_index()
                return len(index._all_files), None, False
            else:
                count = index.build_priority_index()
                return count, total, True

        indexed, total, is_partial = await asyncio.to_thread(do_index)

        if is_partial and self._status_callback:
            self._status_callback(
                f"Code cache: {indexed}/{total} files indexed, expanding...",
                "muted"
            )

        return indexed, total, is_partial

    async def expand_index(self) -> int:
        """Expand partial index to full index in background."""
        def do_expand() -> int:
            index = CodeIndex.get_instance()
            index.expand_index()
            return len(index._all_files)

        final_count = await asyncio.to_thread(do_expand)

        if self._status_callback:
            self._status_callback(
                f"Code cache built: {final_count} files indexed",
                "success"
            )

        return final_count
```

---

### Step 2: Add Indexing Service to StateManager

**File:** `src/tunacode/core/state.py` (MODIFY)

Add to `__init__`:
```python
def __init__(self) -> None:
    self._session = SessionState()
    self._tool_handler: ToolHandler | None = None
    self._indexing_service: IndexingService | None = None  # NEW
    self._load_user_configuration()
```

Add properties:
```python
@property
def indexing_service(self) -> "IndexingService":
    """Get or create the indexing service."""
    if self._indexing_service is None:
        from tunacode.core.indexing_service import IndexingService
        self._indexing_service = IndexingService()
    return self._indexing_service

def set_indexing_status_callback(
    self, callback: Callable[[str, str], None]
) -> None:
    """Set status callback for indexing service."""
    if self._indexing_service:
        self._indexing_service._status_callback = callback
    else:
        from tunacode.core.indexing_service import IndexingService
        self._indexing_service = IndexingService(status_callback=callback)
```

---

### Step 3: Update UI to Use Core Service

**File:** `src/tunacode/ui/app.py` (MODIFY)

Replace line 194:
```python
# OLD:
self.run_worker(run_startup_index(self.rich_log), exclusive=False)

# NEW:
self.run_worker(self._run_startup_index_via_core(), exclusive=False)
```

Add method to TextualReplApp:
```python
async def _run_startup_index_via_core(self) -> None:
    """Orchestrate startup indexing through Core service."""
    from tunacode.ui.styles import STYLE_MUTED, STYLE_SUCCESS
    from rich.text import Text

    def status_callback(message: str, style: str) -> None:
        msg = Text()
        msg.append(
            message,
            style=STYLE_MUTED if style == "muted" else STYLE_SUCCESS
        )
        self.rich_log.write(msg)

    # Set callback on Core's indexing service
    self.state_manager.set_indexing_status_callback(status_callback)

    # Run indexing through Core
    indexed, total, is_partial = await self.state_manager.indexing_service.start_startup_index()

    if is_partial:
        await self.state_manager.indexing_service.expand_index()
```

---

### Step 4: Delete UI Startup Module

**File:** `src/tunacode/ui/startup.py` (DELETE)

- Remove entire file (59 lines)
- All logic moves to `core/indexing_service.py`

---

### Step 5: Verify Dependency Graph

After changes:
```bash
grep -r "from tunacode.indexing" src/tunacode/ui/
```

**Expected:** `(no results)`

**Dependency Graph Changes:**
- Remove: `ui -> indexing [label="2", penwidth=1.4];`
- Add: `core -> indexing [label="2", penwidth=1.4];`
- Keep: `tools -> indexing` (correct direction)

---

## Knowledge Gaps

1. **Error Handling:** Current indexing silently catches all exceptions. Should errors be surfaced through the status callback?

2. **Progress Updates:** No streaming progress during indexing. Should we add progress reporting for large codebases?

3. **Cache Invalidation:** No mechanism to invalidate/rebuild the index when files change. Is this needed?

4. **Index Persistence:** Index is rebuilt on every launch. Should we cache to disk for faster startup?

---

## References

### Code Files
- [src/tunacode/ui/startup.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/ui/startup.py)
- [src/tunacode/ui/app.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/ui/app.py)
- [src/tunacode/indexing/code_index.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/indexing/code_index.py)
- [src/tunacode/indexing/constants.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/indexing/constants.py)
- [src/tunacode/core/state.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/core/state.py)
- [src/tunacode/tools/glob.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/src/tunacode/tools/glob.py)

### Documentation
- [CLAUDE.md - Gate 2: Dependency Direction](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/CLAUDE.md#L247-L272)
- [docs/codebase-map/modules/indexing.md](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/docs/codebase-map/modules/indexing.md)
- [docs/codebase-map/architecture/architecture.md](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/docs/codebase-map/architecture/architecture.md#L429)

### Dependency Graphs
- [layers.dot](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/layers.dot)
- [deps.dot](https://github.com/alchemiststudiosDOTai/tunacode/blob/d93e8d4b/deps.dot)

### Ticket
- [.tickets/t-ea8a.md](https://github.com/alchemiststudiosDOTai/tunacode/blob/ui-dependency-direction/.tickets/t-ea8a.md)
