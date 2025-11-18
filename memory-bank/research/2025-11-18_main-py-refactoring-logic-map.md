# Research – main.py Refactoring Logic Map

**Date:** 2025-11-18
**Owner:** claude-agent
**Phase:** Research
**Git Commit:** 0fc4c5e43855f5d2e9c87c8cf512ccd143767a5b
**Git Branch:** master
**Components:** core.agents.main, agent_components
**Tags:** refactoring, architecture, state-management, orchestration

---

## Goal

Map all critical logic in `/home/fabian/tunacode/src/tunacode/core/agents/main.py` before refactoring to ensure no functionality is lost. This document provides a complete inventory of:
- All state management patterns and session attributes
- Complete request processing flow and orchestration
- Dependencies on agent_components module
- All intervention mechanisms (productivity tracking, react forcing, empty response handling)
- Error handling paths

---

## Findings

### 1. Module Structure and Dependencies

**Main File:** [main.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/0fc4c5e43855f5d2e9c87c8cf512ccd143767a5b/src/tunacode/core/agents/main.py)

**Agent Components Location:** `/home/fabian/tunacode/src/tunacode/core/agents/agent_components/`

**Critical Functions from agent_components:**

| Function | Purpose | Side Effects |
|----------|---------|--------------|
| `get_or_create_agent()` | Get/create agent with caching | Updates `_AGENT_CACHE` and `session.agents` |
| `_process_node()` | Core node processing | **Appends to session.messages**, tracks tools, transitions states |
| `create_user_message()` | Create synthetic user message | **Appends to session.messages** |
| `patch_tool_messages()` | Add error responses to orphaned tools | **Appends to session.messages** |
| `execute_tools_parallel()` | Execute tools in parallel | Executes tools, no session mutation |

### 2. Critical State Management (StateFacade Pattern)

**StateFacade Class** ([main.py:66-126](https://github.com/alchemiststudiosDOTai/tunacode/blob/0fc4c5e43855f5d2e9c87c8cf512ccd143767a5b/src/tunacode/core/agents/main.py#L66-L126))

**Session Attributes Managed:**

| Attribute | Initialized | Purpose | Mutation Points |
|-----------|-------------|---------|-----------------|
| `request_id` | Line 91 | 8-char UUID for request | `set_request_id()` |
| `current_iteration` | Line 98 | Current iteration number | `set_iteration()` every loop |
| `iteration_count` | Line 99 | Iteration count (duplicate) | `set_iteration()` every loop |
| `tool_calls` | Line 100 | All tool invocations | Appended in node_processor.py:465 |
| `react_forced_calls` | Line 101 | Auto-snapshot counter (max 5) | Incremented at line 196 |
| `react_guidance` | Line 102 | ReAct guidance for LLM | Appended/trimmed at lines 231-234 |
| `batch_counter` | Line 105 | Parallel batch ID | Incremented in node_processor.py:362 |
| `consecutive_empty_responses` | Line 107 | Empty response streak | increment/clear methods |
| `original_query` | Line 109 | Initial user query | `set_original_query_once()` |

**State Lifecycle:**
1. **Request Start** (`reset_for_new_request()` @ line 95-109): Zeros out 8 attributes
2. **Per Iteration** (line 409): Updates iteration counters
3. **Request End**: No cleanup, state preserved

### 3. Complete Request Processing Flow

**Entry Point:** `process_request()` ([main.py:372-538](https://github.com/alchemiststudiosDOTai/tunacode/blob/0fc4c5e43855f5d2e9c87c8cf512ccd143767a5b/src/tunacode/core/agents/main.py#L372-L538))

**Main Iteration Loop - Each iteration performs:**

1. Set iteration (line 409)
2. Stream tokens (lines 412-414) - optional
3. **Process node** (lines 417-425) - Core via `ac._process_node()`
4. **Handle empty response** (lines 428-433) - If consecutive >= 1: inject retry prompt
5. Track user output (lines 435-436)
6. **Productivity tracking** (lines 439-457) - No tools for 3 iterations? Force action
7. **React snapshot forcing** (lines 458-464) - Every 2 iterations (max 5 times)
8. Display debug (lines 466-475)
9. User guidance request (lines 477-479)
10. **Completion check** (lines 482-485) - If task_completed: break
11. **Iteration limit check** (lines 488-509) - At limit: inject extend prompt
12. Increment iteration (line 510)

### 4. Intervention Mechanisms

#### A. Productivity Tracking ([main.py:439-457](https://github.com/alchemiststudiosDOTai/tunacode/blob/0fc4c5e43855f5d2e9c87c8cf512ccd143767a5b/src/tunacode/core/agents/main.py#L439-L457))

**Trigger:** `unproductive_iterations >= 3` AND `not task_completed`

**Action:** Inject message:
```
ALERT: No tools executed for N iterations.
You MUST:
1. If COMPLETE: Start with TUNACODE DONE:
2. If needs work: Execute a tool RIGHT NOW
3. If stuck: Explain blocker
NO MORE DESCRIPTIONS. Take ACTION or mark COMPLETE.
```

#### B. React Snapshot Forcing ([main.py:174-254](https://github.com/alchemiststudiosDOTai/tunacode/blob/0fc4c5e43855f5d2e9c87c8cf512ccd143767a5b/src/tunacode/core/agents/main.py#L174-L254))

**Trigger:** `iteration >= 2` AND `iteration % 2 == 0` AND `forced_calls < 5`

**Execution:**
1. Execute react_tool
2. Increment `session.react_forced_calls`
3. Build contextual guidance from last tool
4. Append to `session.react_guidance`, trim to last 5
5. **CRITICAL:** Inject into `agent_run.ctx.messages` so next LLM call sees guidance

#### C. Empty Response Handling ([main.py:428-433](https://github.com/alchemiststudiosDOTai/tunacode/blob/0fc4c5e43855f5d2e9c87c8cf512ccd143767a5b/src/tunacode/core/agents/main.py#L428-L433))

**Trigger:** After 1 consecutive empty response

**Action:** Inject troubleshooting message with specific actions

#### D. Completion Detection

**Markers:**
- `TUNACODE DONE:`
- `TUNACODE_TASK_COMPLETE`

**Checks:**
- Premature: If has queued tools → Override
- Intention: If has pending phrases ("let me", "going to") → Log warning
- Valid: Set `task_completed`, break loop

#### E. Iteration Limit ([main.py:488-509](https://github.com/alchemiststudiosDOTai/tunacode/blob/0fc4c5e43855f5d2e9c87c8cf512ccd143767a5b/src/tunacode/core/agents/main.py#L488-L509))

**Trigger:** `i >= max_iterations` AND `not task_completed`

**Action:** Inject "reached limit" message, set `awaiting_user_guidance`

**Key:** NO auto-increment (prevents infinite loops)

### 5. Constants

```python
DEFAULT_MAX_ITERATIONS = 15      # Iteration cap
UNPRODUCTIVE_LIMIT = 3           # Iterations before forcing action
DEBUG_METRICS_DEFAULT = False
FORCED_REACT_INTERVAL = 2        # Force react every N iterations
FORCED_REACT_LIMIT = 5           # Max forced snapshots
```

### 6. Error Handling

- **UserAbortError**: Re-raise immediately
- **ToolBatchingJSONError**: Log, patch messages, re-raise
- **Generic Exception**: Log with context, patch messages, re-raise

---

## Key Patterns to Preserve

1. **Facade Pattern** - Single point for session mutations
2. **Defensive Initialization** - setattr for dynamic attributes
3. **Context Mutation** - Direct mutation of `agent_run.ctx.messages` for guidance injection
4. **Local Tracker + Session Write** - Local variables for transient state

---

## Knowledge Gaps / Questions

1. **ToolBuffer** - Created but appears unused in main loop (line 399)
2. **Iteration Counter Duplication** - Both `current_iteration` and `iteration_count` exist
3. **debug_metrics Flag** - Read but not visibly used
4. **Message Mutations** - Scattered across multiple files, should all go through facade?

---

## Next Steps for Refactoring

**Preserve:**
- All 5 intervention mechanisms (productivity, react, empty, completion, limit)
- State lifecycle (reset 8 attrs at start)
- Facade pattern for mutations

**Delegate to focused classes:**
- `ProductivityTracker` - Unproductive iteration logic
- `ReactSnapshotManager` - Forced react calls
- `IterationOrchestrator` - Main loop coordination
- `CompletionDetector` - Marker checking
- `EmptyResponseHandler` - Empty response tracking

**Extract constants to config dataclass:**
```python
@dataclass
class AgentConfig:
    max_iterations: int = 15
    unproductive_limit: int = 3
    forced_react_interval: int = 2
    forced_react_limit: int = 5
```

**Address gaps:**
- Clarify/remove ToolBuffer
- Consolidate iteration counters
- Potentially centralize message mutations

---

**Research completed:** 2025-11-18
**Ready for refactoring:** Yes, with full logic map documented
