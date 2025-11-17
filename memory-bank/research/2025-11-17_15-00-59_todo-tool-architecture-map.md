# Research – Todo Tool Architecture Map

**Date:** 2025-11-17 15:00:59
**Owner:** Claude Agent (context-engineer:research)
**Phase:** Research
**Git Commit:** bd5ca95061faf9e71296a36f4a6f9a9b90be3c59
**Branch:** master
**Tags:** todo-tool, architecture, cleanup-prep, state-management, tool-system

---

## Goal

Map the complete architecture of the `TodoTool` implementation to understand all dependencies, integration points, and usage patterns across the codebase before cleanup and rebuild. This research documents the current state to enable safe removal and replacement.

---

## Research Methodology

- **Approach:** Parallel sub-agent analysis with three specialized agents
- **Agents Used:**
  1. `codebase-locator` - Found all references to TodoTool across 19 files
  2. `codebase-analyzer` - Analyzed implementation details and dependencies
  3. `codebase-analyzer` - Mapped state management integration
- **Primary Sources:** Live codebase analysis as of commit bd5ca95
- **Search Commands:**
  ```bash
  grep -ri "TodoTool" src/
  grep -ri "todo_tool" src/
  grep -ri "TodoItem" src/
  grep -ri "todo" .claude/
  ```

---

## Executive Summary

The `TodoTool` is a 467-line stateful tool that enables AI agents to manage structured task lists during execution. It integrates deeply with:

1. **State Management Layer** - Direct dependency on `StateManager` with 5 methods
2. **Type System** - Uses `TodoItem` dataclass with 7 fields
3. **Constants & Validation** - Enforces 100 todo limit and 500 char content limit
4. **XML Configuration** - Loads prompts and schema from `todo_prompt.xml`
5. **Agent System** - Injected into main agent via `agent_config.py`
6. **CLI Commands** - Parallel CLI interface with 7 subcommands
7. **System Prompts** - Todo context injected into every agent interaction

**Key Finding:** The tool has 19 file dependencies spanning core systems, making cleanup non-trivial.

---

## 1. Core Implementation Files

### 1.1 Primary Tool Implementation

**File:** [src/tunacode/tools/todo.py](src/tunacode/tools/todo.py)
**Lines:** 467 total
**Class:** `TodoTool(BaseTool)`

**Key Components:**

| Component | Lines | Purpose |
|-----------|-------|---------|
| `_get_base_prompt()` | 33-52 | Load description from XML with fallback |
| `_get_parameters_schema()` | 54-133 | Parse complex parameter schema from XML |
| `__init__()` | 135-143 | Inject state_manager and ui_logger |
| `_execute()` | 149-195 | Route 6 actions to handler methods |
| `_add_todo()` | 197-235 | Create single todo with validation |
| `_add_multiple_todos()` | 237-315 | Batch todo creation (dual input formats) |
| `_update_todo()` | 317-373 | Modify status/priority/content |
| `_complete_todo()` | 375-387 | Mark completed with timestamp |
| `_list_todos()` | 389-417 | Format todos grouped by status |
| `_remove_todo()` | 419-435 | Delete todo from state |
| `get_current_todos_sync()` | 437-466 | Synchronous list for prompt injection |

**Imports:**
```python
# Standard library
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

# Third-party
import defusedxml.ElementTree as ET
from pydantic_ai.exceptions import ModelRetry

# Internal - Constants
from tunacode.constants import (
    MAX_TODO_CONTENT_LENGTH,      # 500 chars
    MAX_TODOS_PER_SESSION,         # 100 todos
    TODO_PRIORITIES,               # [HIGH, MEDIUM, LOW]
    TodoPriority,                  # Enum
    TodoStatus,                    # Enum
)

# Internal - Types
from tunacode.types import TodoItem, ToolResult, UILogger

# Internal - Base
from .base import BaseTool
```

---

### 1.2 State Management Layer

**File:** [src/tunacode/core/state.py](src/tunacode/core/state.py)
**Class:** `StateManager`

**SessionState Storage (line 52):**
```python
@dataclass
class SessionState:
    todos: list[TodoItem] = field(default_factory=list)
```

**StateManager Methods:**

| Method | Line | Signature | Purpose |
|--------|------|-----------|---------|
| `add_todo()` | 120-121 | `(self, todo: TodoItem) -> None` | Append to todos list |
| `update_todo()` | 123-131 | `(self, todo_id: str, status: str) -> None` | Update status + set completed_at |
| `remove_todo()` | 167-168 | `(self, todo_id: str) -> None` | Filter out todo by ID |
| `clear_todos()` | 170-171 | `(self) -> None` | Reset todos to empty list |
| `session` property | 110-111 | `-> SessionState` | Access to session.todos |

**Persistence Model:**
- **Type:** In-memory only (session lifetime)
- **Storage:** Direct list mutations
- **Lifecycle:** Cleared on `reset_session()` (line 184-186)
- **No database or file persistence**

---

### 1.3 CLI Command Interface

**File:** [src/tunacode/cli/commands/implementations/todo.py](src/tunacode/cli/commands/implementations/todo.py)
**Class:** `TodoCommand(SimpleCommand)`
**Lines:** 240 total

**Subcommands:**

| Subcommand | Lines | Purpose | StateManager Method Used |
|------------|-------|---------|--------------------------|
| `list` | 52-101 | Display todos with Rich formatting | Reads `session.todos` |
| `add` | 103-121 | Create new todo | `add_todo()` |
| `done` | 123-143 | Mark as completed | `update_todo()` |
| `update` | 145-164 | Change status | Direct mutation |
| `priority` | 166-185 | Change priority | Direct mutation |
| `remove` | 187-204 | Delete todo | `remove_todo()` |
| `clear` | 206-214 | Remove all todos | `clear_todos()` |

**ID Format:** Uses Unix microseconds instead of UUID (line 110):
```python
new_id = f"{int(datetime.now().timestamp() * 1000000)}"
```

**Critical Finding:** CLI bypasses validation - no content length or max count checks.

---

## 2. Type System & Constants

### 2.1 TodoItem Dataclass

**File:** [src/tunacode/types.py](src/tunacode/types.py:37-46)

```python
@dataclass
class TodoItem:
    id: str                          # Format: "todo_{uuid[:8]}" or Unix µs
    content: str                     # Max 500 chars (validated in tool only)
    status: Literal["pending", "in_progress", "completed"]
    priority: Literal["high", "medium", "low"]
    created_at: datetime             # Set on creation
    completed_at: Optional[datetime] = None  # Set when status → "completed"
    tags: list[str] = field(default_factory=list)  # Unused in current impl
```

**ToolResult Type:**
```python
ToolResult = str  # Simple string return from tool methods
```

**UILogger Protocol:**
```python
class UILogger(Protocol):
    async def info(self, message: str) -> None: ...
    async def error(self, message: str) -> None: ...
    async def warning(self, message: str) -> None: ...
    async def debug(self, message: str) -> None: ...
    async def success(self, message: str) -> None: ...
```

---

### 2.2 Constants & Enums

**File:** [src/tunacode/constants.py](src/tunacode/constants.py)

**Status Enum (lines 171-177):**
```python
class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
```

**Priority Enum (lines 179-185):**
```python
class TodoPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

**Validation Constants:**
```python
TODO_PRIORITIES = [TodoPriority.HIGH, TodoPriority.MEDIUM, TodoPriority.LOW]
MAX_TODOS_PER_SESSION = 100   # Line 199
MAX_TODO_CONTENT_LENGTH = 500  # Line 202
```

**Tool Name Constant:**
```python
class ToolName(str, Enum):
    TODO = "todo"  # Line 46

TOOL_TODO = ToolName.TODO  # Line 59 (backward compatibility)
```

---

## 3. Agent Integration Points

### 3.1 Agent Configuration

**File:** [src/tunacode/core/agents/agent_components/agent_config.py](src/tunacode/core/agents/agent_components/agent_config.py)

**TodoTool Initialization (line 176):**
```python
todo_tool = TodoTool(state_manager=state_manager)
```

**Context Injection (lines 180-187):**
```python
current_todos = todo_tool.get_current_todos_sync()
system_prompt_sections.append(f"""
<current_todos>
{current_todos}
</current_todos>
""")
```

**Tool Registration (line 205):**
```python
Tool(todo_tool._execute, max_retries=max_retries, strict=tool_strict_validation)
```

**Impact:** Every agent interaction includes todo context in system prompt.

---

### 3.2 Tool Registration

**File:** [src/tunacode/configuration/settings.py](src/tunacode/configuration/settings.py:26-35)

```python
self.internal_tools = [
    ToolName.BASH,
    ToolName.READ,
    # ...
    ToolName.TODO,  # Line 33
    # ...
]
```

---

## 4. XML Configuration Layer

### 4.1 Prompt Definition

**File:** [src/tunacode/tools/prompts/todo_prompt.xml](src/tunacode/tools/prompts/todo_prompt.xml)
**Lines:** 96 total

**Structure:**
```xml
<tool_prompt>
    <description>
        <!-- Lines 3-58: Agent instructions -->
        <!-- Markdown-formatted guidance -->
    </description>

    <parameters>
        <!-- Lines 60-83: Parameter schema -->
        <parameter name="todos" required="true">
            <type>array</type>
            <items>
                <type>object</type>
                <properties>
                    <!-- id, content, status, activeForm -->
                </properties>
            </items>
        </parameter>
    </parameters>

    <examples>
        <!-- Lines 85-95: Usage examples -->
    </examples>
</tool_prompt>
```

**Parsing:**
- Uses `defusedxml.ElementTree` for security (XXE protection)
- Fallback to hardcoded schema if XML parsing fails
- Loaded at import time via `_get_base_prompt()` and `_get_parameters_schema()`

---

### 4.2 System Prompt Reference

**File:** [src/tunacode/src/tunacode/prompts/system.xml](src/tunacode/src/tunacode/prompts/system.xml:294)

```xml
<guidance>Use todo tool for complex multistep tasks</guidance>
```

---

## 5. Complete Dependency Graph

### 5.1 Direct Dependencies (Import Graph)

```
TodoTool
├── Standard Library
│   ├── logging
│   ├── uuid (for ID generation)
│   ├── datetime (for timestamps)
│   ├── pathlib (for XML file loading)
│   └── typing (type annotations)
├── Third-Party
│   ├── defusedxml.ElementTree (XML parsing)
│   └── pydantic_ai.exceptions.ModelRetry (validation errors)
├── Internal - Constants
│   ├── MAX_TODO_CONTENT_LENGTH
│   ├── MAX_TODOS_PER_SESSION
│   ├── TODO_PRIORITIES
│   ├── TodoPriority enum
│   └── TodoStatus enum
├── Internal - Types
│   ├── TodoItem dataclass
│   ├── ToolResult (str alias)
│   └── UILogger protocol
└── Internal - Base
    └── BaseTool (abstract base class)
```

### 5.2 Runtime Dependencies

```
TodoTool (runtime)
├── StateManager instance
│   ├── add_todo(TodoItem) -> None
│   ├── update_todo(str, str) -> None
│   ├── remove_todo(str) -> None
│   ├── clear_todos() -> None
│   └── session.todos: list[TodoItem]
├── UILogger instance (optional)
│   ├── info(str) -> None
│   ├── error(str) -> None
│   ├── warning(str) -> None
│   └── debug(str) -> None
└── XML prompt file
    └── src/tunacode/tools/prompts/todo_prompt.xml
```

### 5.3 Reverse Dependencies (What Uses TodoTool)

```
Files That Import/Use TodoTool:
├── Agent System
│   └── agent_config.py (instantiates, registers, injects context)
├── CLI System
│   └── todo.py (parallel interface, bypasses tool)
├── Settings
│   └── settings.py (registers in internal_tools list)
├── Documentation (19 references)
│   ├── main-agent.md
│   ├── tunacode-tool-system.md
│   ├── how-tunacode-agent-works.md
│   ├── plan_mode_architecture.md
│   └── react-shim-analysis.md
└── Knowledge Base
    ├── .claude/semantic_index/type_relationships.json
    ├── .claude/delta_summaries/behavior_changes.json
    └── .claude/delta_summaries/reasoning_logs.json
```

---

## 6. Data Flow Architecture

### 6.1 Todo Creation Flow (Agent Path)

```
Agent LLM
    ↓ (calls tool: action="add", content="Task")
TodoTool._execute()
    ↓ (routes to)
TodoTool._add_todo()
    ↓ (validates)
    ├─→ Check content not None (line 199)
    ├─→ Check len(content) ≤ 500 (line 203)
    ├─→ Check len(todos) < 100 (line 209)
    └─→ Validate priority in [HIGH, MEDIUM, LOW] (line 220)
    ↓ (generates ID)
UUID generation: f"todo_{uuid.uuid4().hex[:8]}"
    ↓ (creates instance)
TodoItem(
    id=new_id,
    content=content,
    status=TodoStatus.PENDING,
    priority=todo_priority,
    created_at=datetime.now()
)
    ↓ (persists)
StateManager.add_todo(new_todo)
    ↓ (mutates)
SessionState.todos.append(new_todo)
    ↓ (returns)
"Added todo {id}: {content} (priority: {priority})"
    ↓
Agent receives success message
```

### 6.2 Todo Update Flow (Agent Path)

```
Agent LLM
    ↓ (calls tool: action="update", todo_id="...", status="completed")
TodoTool._execute()
    ↓ (routes to)
TodoTool._update_todo()
    ↓ (finds todo)
Linear search: for t in state_manager.session.todos (line 330)
    ↓ (validates)
    ├─→ Check todo exists (line 335)
    └─→ Validate status in ["pending", "in_progress", "completed"] (line 342)
    ↓ (mutates directly)
todo.status = status (line 347)
if status == "completed" and not todo.completed_at:
    todo.completed_at = datetime.now() (line 349)
    ↓ (returns)
"Updated todo {id}: status to {status}"
    ↓
Agent receives success message
```

### 6.3 Context Injection Flow

```
Agent Initialization
    ↓
agent_config.py:get_agent_config()
    ↓ (line 176)
todo_tool = TodoTool(state_manager=state_manager)
    ↓ (line 180)
current_todos = todo_tool.get_current_todos_sync()
    ↓ (reads)
state_manager.session.todos: list[TodoItem]
    ↓ (formats)
Group by status:
    - IN PROGRESS: [...]
    - PENDING: [...]
    - COMPLETED: [...]
    ↓ (injects into system prompt, line 181-187)
<current_todos>
IN PROGRESS:
  todo_abc123: Task 1 (priority: high)

PENDING:
  todo_def456: Task 2 (priority: medium)
</current_todos>
    ↓
System prompt includes todo context
    ↓
Agent sees todos in EVERY interaction
```

---

## 7. Validation & Error Handling

### 7.1 Validation Layers

| Validation | Where Enforced | Mechanism | Bypass Path |
|-----------|----------------|-----------|-------------|
| Max 100 todos | TodoTool only | `ModelRetry` (lines 209-213, 283-288) | CLI bypasses |
| Max 500 char content | TodoTool only | `ModelRetry` (lines 203-206, 294-298) | CLI bypasses |
| Status enum | TodoTool only | `ModelRetry` (lines 342-346) | CLI uses direct mutation |
| Priority enum | TodoTool only | `ModelRetry` (lines 220-224, 354-358) | CLI bypasses |
| ID uniqueness | UUID generation | Probabilistic (uuid.uuid4()) | CLI uses Unix µs |
| Required fields | Dataclass | Python type system | N/A |

**Critical Gap:** CLI commands bypass all business logic validation.

---

### 7.2 Error Handling Patterns

**ModelRetry Pattern (from pydantic-ai):**
```python
if invalid_condition:
    raise ModelRetry("Human-readable error message for LLM")
```

**Examples:**
- Line 192: Invalid action
- Line 200: Missing content
- Line 205: Content too long
- Line 211: Too many todos
- Line 222: Invalid priority
- Line 252: Invalid todo dict format
- Line 336: Todo not found
- Line 344: Invalid status

**Purpose:** Guides LLM to correct its tool call parameters without failing the conversation.

---

## 8. Issues & Antipatterns Identified

### 8.1 Architecture Issues

1. **Dual Mutation Paths:**
   - TodoTool uses StateManager methods (clean)
   - CLI uses direct property mutations (lines 159, 180 in todo.py CLI)
   - Inconsistent mutation strategies

2. **Validation Asymmetry:**
   - Agent path enforces all constraints
   - CLI path bypasses content length and count limits
   - Different ID formats (UUID vs Unix µs)

3. **No Persistence:**
   - Todos lost on session reset
   - No undo/redo capability
   - No change history

4. **Linear Search:**
   - `update_todo()` uses O(n) loop (state.py:126)
   - Should use dict lookup for large todo counts

5. **Direct Mutations:**
   - StateManager mutates list directly
   - No immutable/functional patterns
   - Hard to track state changes

### 8.2 Code Quality Issues

1. **XML Complexity:**
   - Complex parsing logic (lines 54-133)
   - Fallback schema maintained separately
   - Potential drift between XML and fallback

2. **Duplicate Logic:**
   - `_list_todos()` (line 389-417) duplicates `get_current_todos_sync()` (line 437-466)
   - Both format todos identically

3. **Inconsistent ID Generation:**
   - Agent: `f"todo_{uuid.uuid4().hex[:8]}"` (8-char hex)
   - CLI: `f"{int(datetime.now().timestamp() * 1000000)}"` (Unix µs)
   - Collision risk with CLI approach

4. **Unused Field:**
   - `TodoItem.tags` field exists but unused (types.py:45)

5. **Mixed Responsibilities:**
   - `get_current_todos_sync()` exists only for prompt injection
   - Violates single responsibility principle

---

## 9. Impact Analysis for Removal

### 9.1 Files Requiring Changes

**Critical Changes (Will Break):**
1. [src/tunacode/core/agents/agent_components/agent_config.py](src/tunacode/core/agents/agent_components/agent_config.py:176-187)
   - Remove TodoTool import (line 17)
   - Remove todo_tool instantiation (line 176)
   - Remove todo context injection (lines 180-187)
   - Remove from tools list (line 205)

2. [src/tunacode/core/state.py](src/tunacode/core/state.py)
   - Remove todo methods: `add_todo()`, `update_todo()`, `remove_todo()`, `clear_todos()` (lines 120-171)
   - Remove `SessionState.todos` field (line 52)
   - Remove TodoItem import

3. [src/tunacode/cli/commands/implementations/todo.py](src/tunacode/cli/commands/implementations/todo.py)
   - Delete entire file (240 lines)

4. [src/tunacode/cli/commands/implementations/__init__.py](src/tunacode/cli/commands/implementations/__init__.py:23)
   - Remove `from .todo import TodoCommand`

5. [src/tunacode/configuration/settings.py](src/tunacode/configuration/settings.py:33)
   - Remove `ToolName.TODO` from internal_tools list

**Optional Cleanup:**
6. [src/tunacode/types.py](src/tunacode/types.py:37-46)
   - Remove TodoItem dataclass (if not used elsewhere)

7. [src/tunacode/constants.py](src/tunacode/constants.py:171-202)
   - Remove TodoStatus enum (lines 171-177)
   - Remove TodoPriority enum (lines 179-185)
   - Remove TODO_PRIORITIES, MAX_TODOS_PER_SESSION, MAX_TODO_CONTENT_LENGTH
   - Remove ToolName.TODO (line 46)
   - Remove TOOL_TODO (line 59)

8. [src/tunacode/tools/prompts/todo_prompt.xml](src/tunacode/tools/prompts/todo_prompt.xml)
   - Delete file (96 lines)

9. [src/tunacode/tools/todo.py](src/tunacode/tools/todo.py)
   - Delete file (467 lines)

---

### 9.2 Documentation Updates Needed

**Knowledge Base:**
1. `.claude/semantic_index/type_relationships.json` (line 519)
2. `.claude/delta_summaries/behavior_changes.json` (line 355)
3. `.claude/delta_summaries/reasoning_logs.json` (line 282)

**Documentation Files:**
1. `documentation/agent/main-agent.md` (lines 10, 19, 66, 84)
2. `documentation/agent/tunacode-tool-system.md` (lines 96, 365)
3. `documentation/agent/how-tunacode-agent-works.md` (line 75)
4. `memory-bank/research/2025-11-11_12-23-58_plan_mode_architecture.md` (lines 640, 706)
5. `memory-bank/research/2025-01-19_react-shim-analysis.md` (lines 22, 43)
6. `memory-bank/plan/2025-09-11_14-15-00_automated_cli_tool_testing_framework.md` (line 170)

**System Prompts:**
1. `src/tunacode/prompts/system.xml` (line 294)

---

### 9.3 Testing Impact

**No Test Files Found:**
- Search for `test_todo` yielded no results
- No unit tests exist for TodoTool
- No integration tests for StateManager todo methods
- No CLI command tests for todo subcommands

**Risk:** Removal has no test coverage to validate.

---

## 10. Cleanup Execution Plan

### Phase 1: Preparation
1. ✅ Map all dependencies (this document)
2. Commit current state with this research doc
3. Create backup branch: `git checkout -b backup/todo-tool-removal`

### Phase 2: Core Removal
1. Delete [src/tunacode/tools/todo.py](src/tunacode/tools/todo.py)
2. Delete [src/tunacode/tools/prompts/todo_prompt.xml](src/tunacode/tools/prompts/todo_prompt.xml)
3. Delete [src/tunacode/cli/commands/implementations/todo.py](src/tunacode/cli/commands/implementations/todo.py)
4. Remove TodoCommand import from `__init__.py`

### Phase 3: State Management Cleanup
1. Remove todo methods from [src/tunacode/core/state.py](src/tunacode/core/state.py:120-171)
2. Remove `todos` field from `SessionState` (line 52)
3. Remove TodoItem import

### Phase 4: Agent Integration Cleanup
1. Remove TodoTool from [agent_config.py](src/tunacode/core/agents/agent_components/agent_config.py:176-187)
   - Import (line 17)
   - Instantiation (line 176)
   - Context injection (lines 180-187)
   - Tool registration (line 205)

### Phase 5: Configuration Cleanup
1. Remove from [settings.py](src/tunacode/configuration/settings.py:33)
2. Remove from [system.xml](src/tunacode/prompts/system.xml:294)

### Phase 6: Type System Cleanup
1. Remove TodoItem from [types.py](src/tunacode/types.py:37-46)
2. Remove enums from [constants.py](src/tunacode/constants.py:171-202)
3. Remove ToolName.TODO references

### Phase 7: Knowledge Base Sync
1. Run `claude-kb delete pattern --component tools.todo`
2. Run `claude-kb sync --verbose`
3. Run `claude-kb validate`

### Phase 8: Verification
1. Run `ruff check .` (ensure no import errors)
2. Run `hatch run test` (ensure no test failures)
3. Test agent initialization (ensure no crashes)
4. Test CLI help (ensure todo command removed)

---

## 11. Knowledge Gaps & Questions

### Open Questions
1. **Are there any external scripts or tools that call the todo CLI command?**
   - Need to search beyond src/ directory

2. **Is TodoItem used by any other tools or systems?**
   - Need full grep across entire codebase

3. **Are there any user workflows that depend on todos?**
   - Need to check user documentation

4. **Should we preserve session todos in a deprecated state temporarily?**
   - Consider backward compatibility period

### Recommended Additional Searches
```bash
# Search entire repo for todo references
grep -ri "todoitem" .
grep -ri "todo_tool" .
grep -ri "TodoCommand" .

# Check for CLI usage
grep -ri "tunacode todo" .

# Check scripts directory
find . -name "*.sh" -exec grep -l "todo" {} \;
```

---

## 12. References & Links

### Primary Source Files
- [src/tunacode/tools/todo.py](src/tunacode/tools/todo.py) - Main implementation (467 lines)
- [src/tunacode/core/state.py](src/tunacode/core/state.py) - State management (line 52, 120-171)
- [src/tunacode/cli/commands/implementations/todo.py](src/tunacode/cli/commands/implementations/todo.py) - CLI interface (240 lines)
- [src/tunacode/tools/prompts/todo_prompt.xml](src/tunacode/tools/prompts/todo_prompt.xml) - XML configuration (96 lines)

### Type Definitions
- [src/tunacode/types.py](src/tunacode/types.py:37-46) - TodoItem dataclass
- [src/tunacode/constants.py](src/tunacode/constants.py:171-202) - Enums and limits

### Integration Points
- [src/tunacode/core/agents/agent_components/agent_config.py](src/tunacode/core/agents/agent_components/agent_config.py:176-187) - Agent integration
- [src/tunacode/configuration/settings.py](src/tunacode/configuration/settings.py:33) - Tool registration
- [src/tunacode/prompts/system.xml](src/tunacode/prompts/system.xml:294) - System prompt reference

### Documentation
- [documentation/agent/main-agent.md](documentation/agent/main-agent.md) - Main agent architecture
- [documentation/agent/tunacode-tool-system.md](documentation/agent/tunacode-tool-system.md) - Tool system overview
- [memory-bank/research/2025-11-16_main-agent-architecture-map.md](memory-bank/research/2025-11-16_main-agent-architecture-map.md) - Related architecture research

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| **Total Files Referencing TodoTool** | 19 |
| **Core Implementation Files** | 3 (tool, CLI, state) |
| **Configuration Files** | 2 (settings, agent_config) |
| **Type Definition Files** | 2 (types, constants) |
| **Documentation Files** | 5 |
| **Knowledge Base Files** | 3 |
| **Total Lines of Code** | ~950 (467 tool + 240 CLI + ~200 state/config) |
| **StateManager Methods** | 5 (add, update, remove, clear, list) |
| **CLI Subcommands** | 7 (list, add, done, update, priority, remove, clear) |
| **Tool Actions** | 6 (add, add_multiple, update, complete, list, remove) |
| **Validation Rules** | 5 (max count, max length, status, priority, required) |
| **Test Files** | 0 (no tests found) |

---

## Conclusion

The TodoTool is a deeply integrated component touching 19 files across the codebase. Key removal challenges include:

1. **Agent System Integration** - Todos injected into every agent prompt
2. **State Management Coupling** - 5 methods in StateManager, todos in SessionState
3. **Dual Interface** - Both agent tool and CLI command paths
4. **No Tests** - No test coverage to validate removal
5. **Documentation Spread** - 8+ doc files need updates

**Recommended Approach:** Incremental removal with feature flag to allow rollback if issues arise. The lack of tests makes this a higher-risk cleanup operation.

**Estimated Effort:**
- Code removal: 2-3 hours
- Testing & verification: 2-4 hours
- Documentation updates: 1-2 hours
- KB cleanup: 30 minutes
- **Total: 6-10 hours**

---

**End of Research Document**
