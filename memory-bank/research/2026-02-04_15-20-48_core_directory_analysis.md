# Research – Core Directory Structure Analysis

**Date:** 2026-02-04
**Owner:** claude
**Phase:** Research
**git_commit:** a7711942
**git_branch:** master
**tags:** [architecture, core, refactoring, state-management]

## Goal

Map out the `src/tunacode/core/` directory to understand its structure, identify bloating/messiness issues, and provide recommendations for cleanup and consolidation.

## Additional Search

- `grep -ri "core" .claude/` - Search for existing core-related research

## Findings

### Overview

The `src/tunacode/core/` directory is the central runtime layer of tunacode with **47 Python files totaling ~6,384 lines**. The architecture follows proper layering through the use of protocols (`StateManagerProtocol`, `SessionStateProtocol`) that prevent circular dependencies and maintain clean dependency direction per Gate 2.

### Directory Structure

```
src/tunacode/core/
├── __init__.py (7 lines) - Exception exports
├── state.py (348 lines) - Central state management singleton
├── configuration.py (84 lines) - Facade: re-exports from tunacode.configuration
├── messaging.py (21 lines) - Facade: re-exports from tunacode.utils.messaging
├── shared_types.py (29 lines) - Facade: re-exports from tunacode.types
├── user_configuration.py (38 lines) - Facade: re-exports from tunacode.configuration.user_config
├── constants.py (68 lines) - Facade: re-exports from tunacode.constants
├── file_filter.py (25 lines) - Facade: wraps infrastructure.file_filter
├── formatting.py (18 lines) - Implementation: presentation utilities
├── lsp_status.py (58 lines) - Adapter bridge to tools/lsp
├── system_paths.py (18 lines) - Facade: re-exports from tunacode.configuration.paths
│
├── agents/ (26 files, ~4,740 lines)
│   ├── main.py (390 lines) - Request orchestration entry point
│   ├── history_preparer.py (99 lines) - Message history preparation
│   ├── request_logger.py (145 lines) - Request logging utilities
│   ├── __init__.py (33 lines) - Package exports
│   ├── agent_components/ (13 files, ~2,700 lines)
│   │   ├── agent_config.py (457 lines) - Agent creation/caching
│   │   ├── sanitize.py (564 lines) - Message sanitization
│   │   ├── tool_dispatcher.py (368 lines) - Tool dispatch/execution
│   │   ├── streaming_debug.py (372 lines) - Debug helpers for streaming
│   │   ├── streaming.py (302 lines) - Streaming instrumentation
│   │   ├── orchestrator.py (289 lines) - Node processing
│   │   ├── prune.py (285 lines) - Tool output pruning
│   │   ├── response_state.py (129 lines) - State machine for responses
│   │   ├── agent_helpers.py (131 lines) - Helper functions
│   │   ├── state_transition.py (112 lines) - State transition logic
│   │   ├── tool_executor.py (141 lines) - Parallel tool execution
│   │   ├── result_wrapper.py (51 lines) - Result wrapping classes
│   │   ├── message_handler.py (35 lines) - Message utilities
│   │   └── orchestrator/ (4 files)
│   │       ├── tool_dispatcher.py (368 lines)
│   │       ├── orchestrator.py (289 lines)
│   │       ├── usage_tracker.py (56 lines)
│   │       └── message_recorder.py (8 lines)
│   └── resume/ (6 files, ~1,320 lines)
│       ├── sanitize.py (564 lines) - Message sanitization
│       ├── prune.py (285 lines) - Tool output pruning
│       ├── summary.py (202 lines) - Rolling summary generation
│       ├── sanitize_debug.py (149 lines) - Debug logging
│       ├── filter.py (76 lines) - History filtering
│       └── __init__.py (44 lines)
│
├── types/ (5 files)
│   ├── __init__.py (26 lines) - Type export barrel
│   ├── state.py (105 lines) - SessionStateProtocol, StateManagerProtocol
│   ├── state_structures.py (70 lines) - ConversationState, RuntimeState, TaskState, UsageState
│   ├── agent_state.py (26 lines) - AgentState enum, ResponseState
│   └── tool_registry.py (189 lines) - ToolCallRegistry
│
└── logging/ (5 files, ~500 lines)
    ├── __init__.py (24 lines) - Export barrel
    ├── manager.py (158 lines) - LogManager singleton
    ├── handlers.py (276 lines) - FileHandler, TUIHandler
    ├── levels.py (18 lines) - LogLevel enum
    └── records.py (23 lines) - LogRecord dataclass
```

### Key Relevant Files & Why They Matter

#### Main State Management
- **`src/tunacode/core/state.py:24`** (`SessionState`) - Core session state container with 20+ fields including config, conversation history, task state, runtime counters, usage metrics, persistence fields, and recursive execution tracking
- **`src/tunacode/core/state.py:63`** (`StateManager`) - Singleton managing session lifecycle, serialization, persistence, recursion tracking

#### Type Definitions (Protocols for Decoupling)
- **`src/tunacode/core/types/state.py:17`** (`SessionStateProtocol`) - Protocol for session state access, prevents circular imports
- **`src/tunacode/core/types/state.py:39`** (`StateManagerProtocol`) - Protocol defining StateManager interface, used by all agent components

#### Agent Orchestration (Most Complex Area)
- **`src/tunacode/core/agents/main.py:116`** (`RequestOrchestrator`) - Main request processing loop orchestration
- **`src/tunacode/core/agents/agent_components/agent_config.py:345`** (`get_or_create_agent`) - Agent factory with caching, 457 lines total
- **`src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py:177`** (`process_node`) - Node processing orchestration

#### Resume/Sanitization (Cleanup Logic)
- **`src/tunacode/core/agents/resume/sanitize.py:460`** (`sanitize_history_for_resume`) - Main sanitization entry point, 564 lines total
- **`src/tunacode/core/agents/resume/sanitize.py:506`** (`run_cleanup_loop`) - Iterative cleanup until stable

### Dependency Map (Internal to core/)

```
Layer 1: core/types/ (lowest level, no imports from state.py)
    state_structures.py <- infrastructure.llm_types, types.canonical
    state.py <- state_structures
    agent_state.py (pure types)
    tool_registry.py (pure types)

Layer 2: core/state.py
    SessionState <- core.types (ConversationState, RuntimeState, etc.)
    StateManager <- SessionState, tunacode.configuration

Layer 3: core/agents/
    main.py <- core.types.StateManagerProtocol (NOT core.state.StateManager)
    agent_components/* <- core.types.StateManagerProtocol
    orchestrator/* <- core.types.StateManagerProtocol

Layer 4: core/ facades
    configuration.py <- tunacode.configuration (re-exports)
    shared_types.py <- tunacode.types (re-exports)
    user_configuration.py <- tunacode.configuration.user_config
    messaging.py <- tunacode.utils.messaging

Layer 5: ui/
    main.py <- core.state.StateManager (concrete import allowed)
    app.py <- core.state.StateManager, core.shared_types
    repl_support.py <- core.state.StateManager, core.shared_types, core.constants
```

### Architectural Compliance

**Gate 2 (Dependency Direction): PASS**
- `ui → core` - Valid (UI depends on core)
- `core → configuration` - Valid (core uses configuration)
- `core → infrastructure` - Valid (core wraps infrastructure)
- `core → utils` - Valid (core re-exports from utils)
- `core → tools` - Only via `lsp_status.py` - Valid as bridge for UI

**No circular dependencies detected** - The protocol pattern (`StateManagerProtocol`) prevents this.

## Key Patterns / Solutions Found

### 1. Protocol Pattern for Decoupling
All `core/agents/` components depend on `StateManagerProtocol` instead of concrete `StateManager`. This enables testing and prevents circular dependencies.

**Location:** `src/tunacode/core/types/state.py:39`

### 2. Facade Pattern for Dependency Direction
Multiple facade files re-export from lower layers to maintain Gate 2 compliance:
- `configuration.py` - Re-exports from `tunacode.configuration`
- `shared_types.py` - Re-exports from `tunacode.types`
- `messaging.py` - Re-exports from `tunacode.utils.messaging`

**Trade-off:** Adds indirection but enables clean architectural boundaries.

### 3. State Decomposition Pattern
`SessionState` decomposed into sub-state dataclasses (`ConversationState`, `RuntimeState`, `TaskState`, `UsageState`) defined in `state_structures.py`.

**Location:** `src/tunacode/core/types/state_structures.py`

## Issues Identified

### 1. Large/Complex Files (Candidates for Splitting)

| File | Lines | Issue | Recommendation |
|------|-------|-------|----------------|
| `agent_config.py` | 457 | Mixes agent creation, caching, system prompt loading, HTTP configuration | Split into separate concerns |
| `sanitize.py` | 564 | Multiple cleanup operations (dangling tools, empty responses, consecutive requests) | Already has sub-functions, consider module extraction |
| `tool_dispatcher.py` | 368 | Handles both structured tool calls and fallback parsing from text | Split into two modules |
| `streaming_debug.py` | 372 | Debug helpers tightly coupled to streaming logic | Could be merged into streaming.py or moved to utils |
| `state.py` | 348 | Handles serialization, recursion tracking, file I/O, model context | Consider splitting persistence from state |

### 2. Facade Boilerplate
Files like `constants.py` (68 lines), `shared_types.py` (29 lines), and `messaging.py` (21 lines) are pure re-exports with no added logic.

**Assessment:** This is **intentional for Gate 2 compliance** - UI imports from core, core re-exports from implementation layers. Removing would violate dependency direction.

### 3. Duplication
- Debug preview formatting duplicated across `streaming_debug.py`, `orchestrator.py`, and `sanitize_debug.py`
- Tool name normalization appears in both `tool_dispatcher.py` and `agent_helpers.py`

### 4. Module-level State
`agent_config.py` uses module-level caches (`_AGENT_CACHE`, `_TUNACODE_CACHE`) which can cause issues in tests and require `invalidate_agent_cache()` and `clear_all_caches()` functions for test isolation.

### 5. Resume Module Not Yet Wired
The `resume/` subdirectory has rolling summary generation (`summary.py`) and filtering (`filter.py`) that are not yet integrated into the request loop per issue #271.

## Knowledge Gaps

1. **Performance Impact:** The facade pattern adds indirection - what is the runtime performance cost?
2. **State Size:** What is the typical memory footprint of `SessionState` with large conversation histories?
3. **Agent Cache Hit Rate:** How effective is the agent caching in `agent_config.py`?
4. **Cleanup Frequency:** How often is the `sanitize_history_for_resume()` logic triggered in production?

## Recommendations

### High Priority (Clear Bloating)

1. **Split `agent_config.py` (457 lines)** - Separate concerns:
   - `agent_factory.py` - Agent creation logic
   - `agent_cache.py` - Caching and invalidation
   - `system_prompt.py` - Prompt loading
   - `http_config.py` - HTTP client configuration

2. **Split `tool_dispatcher.py` (368 lines)** - Separate structured and fallback parsing:
   - Keep structured tool dispatch in `tool_dispatcher.py`
   - Move fallback parsing to `fallback_tool_parser.py`

3. **Split `state.py` (348 lines)** - Separate persistence:
   - Keep `SessionState` and `StateManager` in `state.py`
   - Move persistence methods to `state_persistence.py`

### Medium Priority (Cleanup)

4. **Consolidate Debug Formatters** - Extract common debug formatting logic from `streaming_debug.py`, `orchestrator.py`, and `sanitize_debug.py` into a shared `debug_formatter.py`

5. **Remove Tool Name Normalization Duplication** - Consolidate into single utility in `agent_helpers.py`

6. **Wire Resume Module** - Integrate rolling summary compaction per issue #271

### Low Priority (Optional)

7. **Consider Merging `streaming_debug.py`** - Either merge into `streaming.py` or move to `utils/debug/` if used outside agents

8. **Evaluate Facade Boilerplate** - If future changes are unlikely, consider using `__all__` direct re-exports instead of wrapper functions in `configuration.py`

## References

### Key Files for Full Review
- `src/tunacode/core/state.py` - Central state management
- `src/tunacode/core/types/state.py` - Protocol definitions
- `src/tunacode/core/agents/main.py` - Request orchestration entry point
- `src/tunacode/core/agents/agent_components/agent_config.py` - Agent creation/caching (457 lines)
- `src/tunacode/core/agents/resume/sanitize.py` - Message sanitization (564 lines)

### Related Issues
- Issue #271 - Integrate rolling summary compaction into request loop

### GitHub Permalinks
- `state.py`: https://github.com/alchemiststudiosDOTai/tunacode/blob/a7711942/src/tunacode/core/state.py
- `main.py`: https://github.com/alchemiststudiosDOTai/tunacode/blob/a7711942/src/tunacode/core/agents/main.py
- `agent_config.py`: https://github.com/alchemiststudiosDOTai/tunacode/blob/a7711942/src/tunacode/core/agents/agent_components/agent_config.py
- `sanitize.py`: https://github.com/alchemiststudiosDOTai/tunacode/blob/a7711942/src/tunacode/core/agents/resume/sanitize.py
- `tool_dispatcher.py`: https://github.com/alchemiststudiosDOTai/tunacode/blob/a7711942/src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py
