# Research – Plan Mode Architecture and Issues

**Date:** 2025-11-11
**Research ID:** 2025-11-11_12-23-58
**Git Commit:** e353150d940749e1ed2e1e76f2c331883b5e8658
**Branch:** master
**Owner:** Claude (Research Agent)
**Phase:** Research

## Goal

Map out the complete plan mode architecture of the TunaCode agentic harness, identifying all state management flows, tool architectures, approval workflows, and critical issues before attempting any fixes.

## Executive Summary

Plan mode is a two-phase workflow (planning → implementation) that restricts agent tool access during research, presents a structured plan for user approval, and transforms approved plans into implementation requests. The research uncovered **7 critical state inconsistency risks**, architectural confusion with dual-tool designs, and fragile patterns including dead code, missing state attributes, and aggressive but ineffective prompt engineering.

### Key Findings

1. **Premature State Transitions**: Plan mode is exited BEFORE user approval, requiring re-entry for modify/reject
2. **Dual-Tool Confusion**: Two plan presentation tools exist (present_plan is active, exit_plan_mode is dead code)
3. **Dead Code Flags**: `_continuing_from_plan` flag is checked but never set
4. **Dynamic State Attributes**: Approval abort tracking uses undefined SessionState attributes
5. **Fragile Text Detection**: Fallback plan detection creates low-quality stub plans
6. **Cache Race Conditions**: Two-level agent caching with timing-dependent consistency
7. **Aggressive Prompt Replacement**: System prompt nuclear option loses all project context

---

## Architecture Overview

### Component Map

```
┌─────────────────────────────────────────────────────────────┐
│                    User Commands Layer                       │
│  /plan → enter_plan_mode()                                  │
│  /exit-plan → exit_plan_mode()                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  State Management Layer                      │
│  StateManager (src/tunacode/core/state.py)                  │
│  - plan_mode: bool                                           │
│  - plan_phase: PlanPhase enum                                │
│  - current_plan: PlanDoc                                     │
│  - plan_approved: bool                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Agent Configuration Layer                  │
│  agent_config.py: get_or_create_agent()                     │
│  - Tool filtering based on is_plan_mode()                   │
│  - System prompt replacement (nuclear option)               │
│  - Agent cache invalidation on mode change                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Tool Execution Layer                    │
│  Plan Mode: 5 tools (present_plan + 4 read-only)           │
│  Normal Mode: 10 tools (all operations)                     │
│  Authorization: PlanModeBlockingRule (priority 100)         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    REPL Detection Layer                      │
│  execute_repl_request() → detect PLAN_READY phase          │
│  Fallback: _detect_and_handle_text_plan()                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Plan Approval Layer                        │
│  _handle_plan_approval() → display + user choice (a/m/r)   │
│  Approval → transform request → recursive execution         │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

**Core State Management:**
- [src/tunacode/core/state.py:34-108](src/tunacode/core/state.py#L34-L108) - SessionState dataclass
- [src/tunacode/core/state.py:197-230](src/tunacode/core/state.py#L197-L230) - Plan mode state methods

**Type Definitions:**
- [src/tunacode/types.py:197-204](src/tunacode/types.py#L197-L204) - PlanPhase enum
- [src/tunacode/types.py:216-254](src/tunacode/types.py#L216-L254) - PlanDoc dataclass

**Agent Configuration:**
- [src/tunacode/core/agents/agent_components/agent_config.py:127-323](src/tunacode/core/agents/agent_components/agent_config.py#L127-L323) - Agent creation & tool filtering
- [src/tunacode/core/agents/agent_components/agent_config.py:174-236](src/tunacode/core/agents/agent_components/agent_config.py#L174-L236) - Plan mode prompt replacement

**Tools:**
- [src/tunacode/tools/present_plan.py:16-291](src/tunacode/tools/present_plan.py#L16-L291) - Active plan presentation tool
- [src/tunacode/tools/exit_plan_mode.py:16-280](src/tunacode/tools/exit_plan_mode.py#L16-L280) - Deprecated tool (never registered)

**REPL Handlers:**
- [src/tunacode/cli/repl.py:45-67](src/tunacode/cli/repl.py#L45-L67) - Request transformation
- [src/tunacode/cli/repl.py:70-104](src/tunacode/cli/repl.py#L70-L104) - Plan display formatter
- [src/tunacode/cli/repl.py:107-168](src/tunacode/cli/repl.py#L107-L168) - Text plan fallback detection
- [src/tunacode/cli/repl.py:170-258](src/tunacode/cli/repl.py#L170-L258) - Plan approval handler
- [src/tunacode/cli/repl.py:416-424](src/tunacode/cli/repl.py#L416-L424) - Phase detection in main loop

**Authorization:**
- [src/tunacode/core/tool_authorization.py:143-172](src/tunacode/core/tool_authorization.py#L143-L172) - PlanModeBlockingRule
- [src/tunacode/core/tool_handler.py:93-103](src/tunacode/core/tool_handler.py#L93-L103) - Tool blocking check

**Commands:**
- [src/tunacode/cli/commands/implementations/plan.py:10-50](src/tunacode/cli/commands/implementations/plan.py#L10-L50) - /plan and /exit-plan commands

**Tests:**
- [tests/test_plan_mode.py:1-221](tests/test_plan_mode.py#L1-L221) - Comprehensive plan mode tests

---

## Critical Issue 1: Premature Plan Mode Exit

### Location
[src/tunacode/cli/repl.py:178-180](src/tunacode/cli/repl.py#L178-L180)

### The Problem

```python
async def _handle_plan_approval(state_manager, original_request=None):
    state_manager.session.plan_phase = PlanPhase.REVIEW_DECISION  # Line 178
    plan_doc = state_manager.session.current_plan
    state_manager.exit_plan_mode(plan_doc)  # Line 180 ⚠️ EXITS TOO EARLY
```

Plan mode is exited **BEFORE** the user makes their approval decision. The function then presents options and waits for user input.

### Consequences

1. **State Thrashing**: If user chooses "modify" or "reject", `enter_plan_mode()` is called again:
   - Lines 214, 229, 233 re-enter plan mode
   - Double agent cache clear
   - Unnecessary state transitions

2. **Plan Data Loss**: Re-entering plan mode clears `current_plan`:
   ```python
   # src/tunacode/core/state.py:201
   self._session.current_plan = None  # ⚠️ User loses reviewed plan
   ```

3. **Abort During Review**: If user presses ESC/Ctrl+C during approval (lines 204-220):
   - Re-enters plan mode
   - Current plan is cleared
   - User loses the plan they were just reviewing

### Data Flow

```
User reviews plan → Presses ESC (abort)
  ↓
_handle_plan_approval catches UserAbortError
  ↓
Calls enter_plan_mode() (line 214)
  ↓
enter_plan_mode() sets current_plan = None
  ↓
PLAN LOST
```

### Recommendation

Exit plan mode **only on approval**, stay in plan mode for modify/reject:

```python
async def _handle_plan_approval(state_manager, original_request=None):
    state_manager.session.plan_phase = PlanPhase.REVIEW_DECISION
    plan_doc = state_manager.session.current_plan
    # Don't exit here! Stay in plan mode until approved

    await _display_plan(plan_doc)
    # ... get user choice ...

    if choice == "a":  # Only exit on approval
        state_manager.exit_plan_mode(plan_doc)
        state_manager.approve_plan()
        # ... proceed with implementation ...
```

---

## Critical Issue 2: Dual-Tool Confusion

### Location
- [src/tunacode/tools/present_plan.py](src/tunacode/tools/present_plan.py) - ACTIVE
- [src/tunacode/tools/exit_plan_mode.py](src/tunacode/tools/exit_plan_mode.py) - DEAD CODE

### The Problem

Two plan presentation tools exist with fundamentally different architectures:

| Aspect | present_plan (Active) | exit_plan_mode (Dead) |
|--------|----------------------|------------------------|
| Registration | ✅ Registered in agent_config.py:266, 276 | ❌ Never registered |
| Philosophy | Separation of concerns | God Object |
| Approval Flow | External (REPL-driven) | Internal (built-in) |
| Side Effects | Sets phase flag | Displays + prompts + modifies state |
| Parameters | 11 structured fields | 8 simpler fields |
| Validation | PlanDoc.validate() | None |

### Evidence of Confusion

**Misleading Error Message** at [src/tunacode/cli/repl_components/tool_executor.py:69](src/tunacode/cli/repl_components/tool_executor.py#L69):
```python
error_msg = (
    f"Use 'exit_plan_mode' tool to present your plan and exit Plan Mode.\n"
    #      ^^^^^^^^^^^^^^^ This tool doesn't exist in agent's tool list!
)
```

**Naming Collision**:
- State method: `state_manager.exit_plan_mode()` - changes session state
- Tool: `exit_plan_mode` - would have handled approval (but never registered)

### Impact

1. **Developer Confusion**: Two tools with similar names but different purposes
2. **User Confusion**: Error messages reference non-existent tools
3. **Maintenance Burden**: 280 lines of dead code to maintain

### Recommendation

1. **Delete** [src/tunacode/tools/exit_plan_mode.py](src/tunacode/tools/exit_plan_mode.py) entirely
2. **Fix** error message to reference `present_plan`
3. **Document** the single-tool approach

---

## Critical Issue 3: Dead Code Flag (_continuing_from_plan)

### Location
[src/tunacode/cli/repl.py:421-424](src/tunacode/cli/repl.py#L421-L424)

### The Problem

```python
elif state_manager.is_plan_mode() and not getattr(
    state_manager.session, "_continuing_from_plan", False
):
    await _detect_and_handle_text_plan(state_manager, res, text)
```

The `_continuing_from_plan` flag is checked but **never set anywhere** in the codebase.

### What Should Happen

This flag should prevent text plan fallback during recursive implementation execution after approval (lines 245-249):

```python
if key == "a" and original_request:
    # MISSING: state_manager.session._continuing_from_plan = True
    await execute_repl_request(
        _transform_to_implementation_request(original_request),
        state_manager,
        output=True,
    )
```

### Current Behavior

Since `getattr(..., False)` always returns `False`, the text plan fallback **always runs** if:
1. In plan mode
2. Agent response didn't trigger PLAN_READY phase

### Consequences

- Text plan detection runs even during implementation execution
- No way to distinguish planning phase from implementation phase
- Potential for false positive plan detection during implementation

### Recommendation

Either:
1. **Set the flag** before recursive implementation call
2. **Remove the flag** and use `plan_approved` state instead
3. **Delete text plan fallback** entirely and require proper tool usage

---

## Critical Issue 4: Dynamic State Attributes

### Location
[src/tunacode/cli/repl.py:201-202, 206-207, 218-219](src/tunacode/cli/repl.py#L201-L202)

### The Problem

```python
# Line 201-202: Setting attributes
state_manager.session.approval_abort_pressed = False
state_manager.session.approval_last_abort_time = 0.0

# Line 206-207: Reading with getattr fallback
abort_pressed = getattr(state_manager.session, "approval_abort_pressed", False)
last_abort = getattr(state_manager.session, "approval_last_abort_time", 0.0)
```

These attributes are **not defined in SessionState dataclass** at [src/tunacode/core/state.py:34-100](src/tunacode/core/state.py#L34-L100).

### Why This is Bad

1. **Type Safety Violation**: Dataclass attributes should be explicit
2. **Opaque State**: Hard to track what state exists at runtime
3. **No IDE Support**: No autocomplete or type checking
4. **Harder Debugging**: State mutations invisible to static analysis

### SessionState Structure

Current SessionState has:
- 44 defined attributes (lines 37-100)
- Missing: `approval_abort_pressed`, `approval_last_abort_time`

### Recommendation

Add to SessionState dataclass at [src/tunacode/core/state.py:100](src/tunacode/core/state.py#L100):

```python
# Plan approval double-abort tracking
approval_abort_pressed: bool = False
approval_last_abort_time: float = 0.0
```

---

## Critical Issue 5: Fragile Text Plan Detection

### Location
[src/tunacode/cli/repl.py:107-168](src/tunacode/cli/repl.py#L107-L168)

### The Problem

When agent outputs text plan instead of calling `present_plan` tool, fallback detection creates a minimal stub:

```python
plan_doc = PlanDoc(
    title="Implementation Plan",
    overview="Automated plan extraction from text",
    steps=["Review and implement the described functionality"],
    files_to_modify=[],
    files_to_create=[],
    success_criteria=[],
)
```

This bypasses validation in `present_plan` tool ([src/tunacode/tools/present_plan.py:138-143](src/tunacode/tools/present_plan.py#L138-L143)).

### Why This Exists

Despite aggressive system prompt replacement ([src/tunacode/core/agents/agent_components/agent_config.py:196-236](src/tunacode/core/agents/agent_components/agent_config.py#L196-L236)) that says:

```
CRITICAL: You cannot respond with text. You MUST use tools for everything.
```

Agents **still output text plans** sometimes. The fallback is a workaround for prompt engineering failures.

### Heuristic Matching (Lines 133-147)

```python
plan_indicators = {
    "plan for",
    "implementation plan",
    "here's a plan",
    "i'll create a plan",
    "plan to",
    "outline for",
    "overview:",
    "steps:",
}
has_plan = any(ind in response_text.lower() for ind in plan_indicators)
has_structure = (
    any(x in response_text for x in ["1.", "2.", "•"])
    and response_text.count("\n") > 5
)
```

### Consequences

1. **Low-Quality Plans**: Empty lists for critical fields
2. **False Positives**: Any text with keywords + numbered lists triggers detection
3. **Bypasses Validation**: `PlanDoc.validate()` never called on text plans
4. **User Confusion**: Plan looks complete but has no real content

### Recommendation

**Option 1 (Strict)**: Remove fallback, reject text plans with actionable error:
```
❌ Plan detected in text format. You MUST use the present_plan tool.
Example: present_plan(title="...", overview="...", steps=[...])
```

**Option 2 (Parse Better)**: Extract actual content from text plan instead of stub

**Option 3 (Improve Prompt)**: Find why prompt engineering fails and fix root cause

---

## Critical Issue 6: Agent Cache Race Conditions

### Location
- Session cache: [src/tunacode/core/state.py:204, 213](src/tunacode/core/state.py#L204)
- Module cache: [src/tunacode/core/agents/agent_components/agent_config.py:30-31, 139-155](src/tunacode/core/agents/agent_components/agent_config.py#L30-L31)

### The Problem

Two-level caching with different clear semantics:

1. **Session Cache**: `state_manager.session.agents` (dict per session)
2. **Module Cache**: `_AGENT_CACHE` (global dict across sessions)

### Cache Invalidation Logic

**Explicit Clear** (enter/exit plan mode):
```python
# Only clears session cache
self._session.agents.clear()
```

**Version Hash Check** (module cache):
```python
current_version = hash(
    (
        state_manager.is_plan_mode(),  # ← Plan mode in hash
        str(state_manager.session.user_config.get("settings", {}).get("max_retries", 3)),
        str(state_manager.session.user_config.get("mcpServers", {})),
    )
)
```

### Race Scenario

```
1. User enters plan mode → session.agents.clear()
2. Agent created → stored in session.agents AND _AGENT_CACHE
3. User exits plan mode → session.agents.clear()
4. Next agent request:
   - Session cache miss
   - Checks module cache
   - If version hash matches (race condition), wrong agent returned! ⚠️
```

### Mitigation

Version hash includes `is_plan_mode()` (line 143), so hash **should** mismatch when mode changes. But this is **timing-dependent** on when agent is recreated vs when state changes.

### Recommendation

**Option 1**: Clear both caches explicitly:
```python
def enter_plan_mode(self):
    self._session.agents.clear()
    from tunacode.core.agents.agent_components.agent_config import clear_all_caches
    clear_all_caches()  # Clear module cache too
```

**Option 2**: Single-level caching (remove module cache)

**Option 3**: Add assertions to verify cache consistency

---

## Critical Issue 7: Aggressive Prompt Replacement

### Location
[src/tunacode/core/agents/agent_components/agent_config.py:196-236](src/tunacode/core/agents/agent_components/agent_config.py#L196-L236)

### The Problem

In plan mode, the **entire system prompt is replaced** (nuclear option):

```python
# COMPLETELY REPLACE system prompt in plan mode - nuclear option
system_prompt = """
🔧 PLAN MODE - TOOL EXECUTION ONLY 🔧

You are a planning assistant that ONLY communicates through tool execution.
...
"""
```

### What This Loses

The original system prompt includes:
- Project-specific instructions from AGENTS.md
- Domain knowledge from system.xml
- User preferences and conventions
- Tool usage patterns and best practices

All of this is **obliterated** in plan mode.

### Why It's Ineffective

Despite the aggressive prompt that says "CRITICAL: You cannot respond with text", agents **still output text plans**. The text plan fallback detection exists precisely because this prompt doesn't work.

### Consequences

1. **Loss of Context**: Agent forgets project-specific knowledge
2. **Inconsistent Behavior**: Different "personality" in plan mode vs normal mode
3. **Ineffective**: Doesn't actually prevent text responses
4. **Fragile**: Any project context needed for planning is lost

### Recommendation

**Option 1**: Augment instead of replace:
```python
system_prompt = original_prompt + "\n\n" + plan_mode_instructions
```

**Option 2**: Use prefix/suffix markers:
```python
system_prompt = f"[PLAN MODE ACTIVE]\n{original_prompt}\n[Use present_plan tool to submit plans]"
```

**Option 3**: Remove aggressive prompt, rely on tool restrictions (simpler)

---

## State Lifecycle and Phase Transitions

### PlanPhase Enum

Defined at [src/tunacode/types.py:197-204](src/tunacode/types.py#L197-L204):

```python
class PlanPhase(Enum):
    PLANNING_RESEARCH = "research"  # User entered plan mode
    PLANNING_DRAFT = "draft"        # ⚠️ NEVER USED
    PLAN_READY = "ready"            # present_plan tool called
    REVIEW_DECISION = "review"      # User reviewing plan
```

**Note**: `PLANNING_DRAFT` is defined but never set anywhere in codebase.

### State Transition Diagram

```
[User: /plan]
    ↓
┌─────────────────────────────────┐
│ enter_plan_mode()               │
│ plan_mode = True                │
│ plan_phase = PLANNING_RESEARCH  │
│ current_plan = None             │
│ agents.clear()                  │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Agent: research (read-only)     │
│ Agent: calls present_plan(...)  │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ present_plan tool:              │
│ plan_phase = PLAN_READY         │
│ current_plan = PlanDoc          │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ REPL detects PLAN_READY         │
│ Calls _handle_plan_approval()  │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ _handle_plan_approval:          │
│ plan_phase = REVIEW_DECISION    │
│ exit_plan_mode() ⚠️ TOO EARLY  │
│ Display plan, wait for choice   │
└─────────────────────────────────┘
    ↓
    ├─[a: approve]───────────────────────────────┐
    │                                             │
    │ ┌─────────────────────────────────────┐   │
    │ │ approve_plan()                      │   │
    │ │ plan_approved = True                │   │
    │ │ plan_mode = False (redundant)       │   │
    │ └─────────────────────────────────────┘   │
    │                ↓                            │
    │ ┌─────────────────────────────────────┐   │
    │ │ Transform request                   │   │
    │ │ "plan X" → "create X"               │   │
    │ └─────────────────────────────────────┘   │
    │                ↓                            │
    │ ┌─────────────────────────────────────┐   │
    │ │ Recursive execute_repl_request()    │   │
    │ │ Agent recreated with all tools      │   │
    │ │ Implementation executes             │   │
    │ └─────────────────────────────────────┘   │
    │                                             │
    ├─[m: modify]──────────────────────────────┐ │
    │                                           │ │
    │ ┌─────────────────────────────────────┐ │ │
    │ │ enter_plan_mode() ⚠️ RE-ENTERS     │ │ │
    │ │ plan_mode = True                    │ │ │
    │ │ current_plan = None ⚠️ LOST        │ │ │
    │ │ agents.clear()                      │ │ │
    │ └─────────────────────────────────────┘ │ │
    │                                           │ │
    └─[r: reject]──────────────────────────────┘ │
                                                  │
      ┌─────────────────────────────────────┐   │
      │ enter_plan_mode() ⚠️ RE-ENTERS     │   │
      │ plan_mode = True                    │   │
      │ current_plan = None ⚠️ LOST        │   │
      │ agents.clear()                      │   │
      └─────────────────────────────────────┘   │
                                                  │
                                                  ↓
                                          [Implementation]
```

---

## Tool Architecture

### Tool Availability by Mode

**Plan Mode** ([agent_config.py:263-271](src/tunacode/core/agents/agent_components/agent_config.py#L263-L271)):
```python
tools_list = [
    present_plan,  # Exit plan mode
    glob,          # Find files
    grep,          # Search content
    list_dir,      # List directories
    read_file,     # Read files
]
```
**Total: 5 tools (1 presentation + 4 read-only)**

**Normal Mode** ([agent_config.py:274-285](src/tunacode/core/agents/agent_components/agent_config.py#L274-L285)):
```python
tools_list = [
    bash,          # Execute commands
    present_plan,  # Still available!
    glob,
    grep,
    list_dir,
    read_file,
    run_command,   # Run commands
    todo_tool,     # Manage todos
    update_file,   # Edit files
    write_file,    # Create files
]
```
**Total: 10 tools (all operations)**

### present_plan Tool Flow

**Schema** ([src/tunacode/tools/present_plan.py:106-119](src/tunacode/tools/present_plan.py#L106-L119)):

```python
async def _execute(
    title: str,                           # Required
    overview: str,                        # Required
    steps: List[str],                     # Required
    files_to_modify: List[str] = None,    # Optional
    files_to_create: List[str] = None,    # Optional
    risks: List[str] = None,              # Optional
    tests: List[str] = None,              # Optional
    rollback: Optional[str] = None,       # Optional
    open_questions: List[str] = None,     # Optional
    success_criteria: List[str] = None,   # Optional
    references: List[str] = None,         # Optional
)
```

**Execution Steps**:
1. Create `PlanDoc` from parameters (lines 122-135)
2. Validate plan completeness (lines 138-143)
   - Checks required fields: title, overview, steps
   - Checks at least one of: files_to_modify or files_to_create
3. Set phase flag: `plan_phase = PLAN_READY` (line 147)
4. Store plan: `current_plan = plan_doc` (line 148)
5. Return simple message (line 150)

**Key Design**: Tool does NOT display plan or prompt user. Separation of concerns.

### Authorization System

**PlanModeBlockingRule** ([src/tunacode/core/tool_authorization.py:143-172](src/tunacode/core/tool_authorization.py#L143-L172)):

```python
class PlanModeBlockingRule(AuthorizationRule):
    priority = 100  # High priority

    def should_allow_without_confirmation(self, tool_name: ToolName, context: AuthContext) -> bool:
        if not context.is_plan_mode:
            return False

        is_read_only = is_read_only_tool(tool_name)
        return is_read_only  # Allow read-only, block write
```

**Read-Only Tools**:
- glob
- grep
- list_dir
- read_file
- present_plan (special exception via PresentPlanRule at priority 0)

**Blocked Tools in Plan Mode**:
- bash
- run_command
- write_file
- update_file
- todo_tool

---

## Request Transformation Logic

### _transform_to_implementation_request

**Location**: [src/tunacode/cli/repl.py:45-67](src/tunacode/cli/repl.py#L45-L67)

**Purpose**: Convert planning request to implementation request after approval.

**Transformations**:
```python
"plan a new feature" → "create a new feature"
"plan an API" → "create an API"
"plan to add logging" → "add logging"
"plan for tests" → "create for tests"
```

**Appends Instruction**:
```
IMPORTANT: Actually implement and create the file(s) -
do not just plan or outline. The plan has been approved,
now execute the implementation.
```

### Recursive Execution

After user approves plan ([repl.py:243-249](src/tunacode/cli/repl.py#L243-L249)):

```python
if key == "a" and original_request:
    await ui.info("Executing implementation...")
    await execute_repl_request(
        _transform_to_implementation_request(original_request),
        state_manager,
        output=True,
    )
```

**Issues**:
1. No recursion depth limit (could loop if implementation creates another plan)
2. No cleanup of ephemeral state before recursion
3. Missing `_continuing_from_plan` flag (dead code)

---

## Approval Flow Error Handling

### Exception Handling in _handle_plan_approval

**Location**: [src/tunacode/cli/repl.py:255-258](src/tunacode/cli/repl.py#L255-L258)

```python
except Exception as e:
    logger.error(f"Error in plan approval: {e}")
    state_manager.session.plan_phase = None  # ⚠️ Only clears phase
```

**Problem**: Partial cleanup leaves inconsistent state:
- `plan_phase` cleared
- `plan_mode` remains False (was set at line 180)
- `current_plan` remains set
- `plan_approved` remains False
- Agent cache remains cleared

**Result**: System in limbo - not in plan mode, but plan data present.

### UserAbortError During Approval

**Location**: [src/tunacode/cli/repl.py:204-220](src/tunacode/cli/repl.py#L204-L220)

**Double-ESC Logic**:
```python
except UserAbortError:
    current_time = time.time()
    abort_pressed = getattr(state_manager.session, "approval_abort_pressed", False)
    last_abort = getattr(state_manager.session, "approval_last_abort_time", 0.0)

    if current_time - last_abort > 3.0:
        abort_pressed = False

    if abort_pressed:
        await ui.info("Returning to Plan Mode")
        state_manager.enter_plan_mode()  # ⚠️ Clears current_plan
        return

    state_manager.session.approval_abort_pressed = True
    state_manager.session.approval_last_abort_time = current_time
```

**Issue**: If user double-ESC aborts, `enter_plan_mode()` is called which sets `current_plan = None`, **losing the plan they were just reviewing**.

---

## Summary of All 7 Critical Issues

| # | Issue | Location | Severity | Impact |
|---|-------|----------|----------|--------|
| 1 | Premature plan mode exit | [repl.py:180](src/tunacode/cli/repl.py#L180) | 🔴 High | State thrashing, plan data loss on abort |
| 2 | Dual-tool confusion | [tools/exit_plan_mode.py](src/tunacode/tools/exit_plan_mode.py) | 🟡 Medium | Developer confusion, misleading errors |
| 3 | Dead code flag | [repl.py:421-424](src/tunacode/cli/repl.py#L421-L424) | 🟡 Medium | Text fallback always runs |
| 4 | Dynamic state attrs | [repl.py:201-202](src/tunacode/cli/repl.py#L201-L202) | 🟡 Medium | Type safety violation, opaque state |
| 5 | Text plan fallback | [repl.py:107-168](src/tunacode/cli/repl.py#L107-L168) | 🔴 High | Low-quality stub plans bypass validation |
| 6 | Cache race conditions | [state.py:204](src/tunacode/core/state.py#L204) | 🟠 Medium-High | Wrong agent with wrong tools |
| 7 | Aggressive prompt | [agent_config.py:196-236](src/tunacode/core/agents/agent_components/agent_config.py#L196-L236) | 🟡 Medium | Loss of project context, ineffective |

---

## Recommendations

### Immediate Fixes (High Priority)

1. **Fix Premature Exit** (Issue #1):
   - Move `exit_plan_mode()` call to only the approve branch
   - Add `enter_plan_mode(preserve_plan=True)` parameter for modify/reject
   - Prevents state thrashing and plan data loss

2. **Delete Dead Code** (Issue #2):
   - Remove [src/tunacode/tools/exit_plan_mode.py](src/tunacode/tools/exit_plan_mode.py)
   - Fix error message at [tool_executor.py:69](src/tunacode/cli/repl_components/tool_executor.py#L69)
   - Document single-tool architecture

3. **Add Missing State Attributes** (Issue #4):
   - Add to SessionState: `approval_abort_pressed`, `approval_last_abort_time`
   - Ensures type safety and state visibility

### Medium Priority Fixes

4. **Fix or Remove Text Fallback** (Issue #5):
   - Option A: Remove fallback, reject text plans with actionable error
   - Option B: Parse text plans properly instead of creating stubs
   - Option C: Fix root cause (why agents output text despite prompt)

5. **Fix Dead Flag** (Issue #3):
   - Either set `_continuing_from_plan` flag properly
   - Or remove it and use `plan_approved` state
   - Or delete text fallback entirely

6. **Synchronize Cache Clearing** (Issue #6):
   - Clear both session and module caches explicitly
   - Add assertions to verify cache consistency
   - Consider single-level caching

### Lower Priority Improvements

7. **Improve Prompt Strategy** (Issue #7):
   - Augment instead of replace system prompt
   - Preserve project context in plan mode
   - Test if less aggressive prompt still enforces tool usage

8. **Add State Validation**:
   - Assert state transitions are legal
   - Validate invariants (e.g., PLAN_READY requires plan_mode=True)
   - Build explicit state machine

9. **Comprehensive Exception Handling**:
   - Wrap all state transitions in try/finally
   - Ensure atomic state updates (all fields or none)
   - Add recovery logic for inconsistent states

10. **Add Recursion Depth Limit**:
    - Prevent infinite loops in recursive implementation
    - Track recursion depth in session state
    - Warn if depth exceeds threshold

---

## Testing Strategy

### Current Test Coverage

[tests/test_plan_mode.py](tests/test_plan_mode.py) has:
- TestPlanModeState: State transition tests
- TestToolHandler: Tool blocking in plan mode
- TestPlanCommands: /plan and /exit-plan commands
- TestExitPlanModeTool: Deprecated tool (should be removed)

### Gaps in Test Coverage

Missing tests for:
1. Premature exit and re-entry scenarios
2. Abort during approval (double-ESC)
3. Exception handling in approval flow
4. Text plan fallback detection
5. Request transformation logic
6. Recursive implementation execution
7. Cache invalidation timing
8. PlanPhase transitions

### Recommended New Tests

```python
# Test premature exit issue
def test_plan_mode_stays_active_until_approval()

# Test abort handling
def test_abort_during_approval_preserves_plan()

# Test exception handling
def test_exception_in_approval_restores_consistent_state()

# Test text fallback
def test_text_plan_detection_creates_valid_plan()

# Test cache synchronization
def test_agent_cache_invalidated_on_mode_change()

# Test recursion
def test_implementation_after_approval_has_correct_tools()
```

---

## Related Documentation

- [.claude/docs_model_friendly/component_purpose.md](.claude/docs_model_friendly/component_purpose.md) - Component overview
- [documentation/agent/how-tunacode-agent-works.md](documentation/agent/how-tunacode-agent-works.md) - Agent architecture
- [documentation/agent/agent-flow.md](documentation/agent/agent-flow.md) - Agent loop flow

## Additional Context

- Git history shows recent refactoring at commit e353150 to separate tool authorization concerns
- Memory bank has research docs on tool_handler mapping (2025-11-05_17-35-17)
- Debug history documents tool_handler refactoring (2025-11-05_tool_handler_refactoring.md)

---

## Knowledge Gaps

1. **Why does text plan fallback exist?** - Historical context on when/why it was added
2. **Why aggressive prompt replacement?** - Was there a specific failure mode that prompted this?
3. **PLANNING_DRAFT phase** - Why defined but never used?
4. **exit_plan_mode tool** - When was it deprecated and why?
5. **User experience** - What specific issues have users reported with plan mode?

## Next Steps

1. **Prioritize fixes** based on user impact and implementation complexity
2. **Create implementation plan** for top 3 fixes
3. **Write regression tests** before making changes
4. **Refactor incrementally** - fix one issue at a time with tests
5. **Document changes** in delta summaries and debug history

---

**Research Complete: 2025-11-11 12:23:58**
**Files Analyzed: 15 core files, 1 test file**
**Issues Identified: 7 critical, multiple architectural concerns**
**Lines of Code Reviewed: ~3,500 LOC**
