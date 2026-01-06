---
title: Plan Mode Feature - Read-Only Exploration with Interactive Approval
link: plan-mode-feature
type: delta
ontological_relations:
  - relates_to: [[authorization-system]]
  - relates_to: [[tool-architecture]]
tags:
  - plan-mode
  - authorization
  - ui
  - pr-213
created_at: 2026-01-06T20:00:00Z
updated_at: 2026-01-06T20:00:00Z
uuid: 7ec4c931-8f54-4ab2-89d3-95f4c9adc737
---

# PR #213: Plan Mode Feature

## Summary

Implemented plan mode: a read-only exploration mode where the agent gathers context using read-only tools, then presents a detailed implementation plan for user approval before executing any write operations.

## API Changes

### New Types

**AuthorizationResult Enum** (`src/tunacode/tools/authorization/types.py`)
- Extends authorization from boolean (allow/deny) to tri-state:
  - `ALLOW` - Tool executes without confirmation
  - `CONFIRM` - Tool requires user confirmation
  - `DENY` - Tool is blocked entirely

```python
class AuthorizationResult(Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"
```

### New Exceptions

**ToolDeniedError** (`src/tunacode/exceptions.py:66-72`)
- Raised when a tool is blocked by authorization policy (e.g., write tools in plan mode)
- Inherits from `TunacodeError`

### New State Fields

**SessionState** (`src/tunacode/core/state.py:50`)
- `plan_mode: bool = False` - Whether plan mode is active
- `plan_approval_callback: Any | None = None` - Callback for interactive plan approval

**AuthContext** (`src/tunacode/tools/authorization/context.py:18`)
- `plan_mode: bool` field - Propagates plan mode state to authorization rules

### New Authorization Rule

**PlanModeBlockRule** (`src/tunacode/tools/authorization/rules.py:72-87`)
- Priority 100 (highest) - checked first in authorization chain
- `evaluate()` method returns `AuthorizationResult.DENY` for write/execute tools when plan_mode is True
- Returns `AuthorizationResult.CONFIRM` otherwise

### New Tools

**present_plan** (`src/tunacode/tools/present_plan.py`)
- Factory pattern tool bound to StateManager
- Requires `plan_mode=True` to function
- Uses `session.plan_approval_callback` for interactive approval
- On approval: writes plan to `PLAN.md`, exits plan mode
- On denial: returns feedback for revision

### New UI Components

**plan_approval.py** (`src/tunacode/ui/plan_approval.py`)
- `render_plan_approval_panel()` - NeXTSTEP 4-zone layout rendering
- `handle_plan_approval_key()` - Handles [1] Approve / [2] Deny key events
- `request_plan_approval()` - Async approval flow with Future-based callback

## Behavior Changes

### Authorization Flow

**Before (Boolean):**
1. Rules return `allow_without_confirmation: bool`
2. Any rule returning `True` bypasses confirmation
3. Otherwise, user confirms

**After (Tri-state):**
1. First pass: Check for `DENY` via `evaluate()` method (PlanModeBlockRule)
2. If denied, raise `ToolDeniedError` immediately
3. Second pass: Check for `ALLOW` via `should_allow_without_confirmation()`
4. If no ALLOW, require `CONFIRM`

### Plan Mode Workflow

1. User types `/plan` command
2. `PlanCommand.execute()`:
   - Sets `session.plan_mode = True`
   - Sets `session.plan_approval_callback` to `app.request_plan_approval()`
   - Calls `create_user_message(PLAN_MODE_INSTRUCTION)` to inject instructions
   - Updates status bar to show "PLAN" mode
3. Agent uses read-only tools to explore
4. Agent calls `present_plan(plan_content)` tool
5. `request_plan_approval()` displays plan and waits for user input
6. User presses [1] to approve or [2] to deny
7. On approve: Plan saved to `PLAN.md`, plan mode exits
8. On deny: Feedback returned to agent for revision

### Update Command Simplification

**Before:** `/update` with subcommands `check` and `install`
**After:** `/update` (no args) checks and immediately prompts to install if available

## Design Decisions

1. **Tri-state vs Boolean**: Used `AuthorizationResult` enum to represent DENY as a distinct state from "needs confirmation"

2. **Rule Priority 100**: `PlanModeBlockRule` has highest priority to ensure DENY is checked before any ALLOW rules (YOLO mode, ignore list, etc.)

3. **Instruction Injection**: Used `create_user_message()` rather than system prompt modification to inject plan mode instructions

4. **Callback Pattern**: `plan_approval_callback` set on session allows tool to trigger UI flow without direct coupling

5. **Factory Pattern**: `present_plan` tool uses factory function pattern like `todo.py` to bind to StateManager

## Files Modified

| File | Change |
|------|--------|
| `src/tunacode/tools/authorization/types.py` | NEW - AuthorizationResult enum |
| `src/tunacode/tools/authorization/rules.py` | PlanModeBlockRule added |
| `src/tunacode/tools/authorization/policy.py` | get_authorization() method |
| `src/tunacode/tools/authorization/handler.py` | get_authorization() method |
| `src/tunacode/tools/authorization/context.py` | plan_mode field |
| `src/tunacode/tools/authorization/factory.py` | PlanModeBlockRule registration |
| `src/tunacode/tools/present_plan.py` | NEW - plan submission tool |
| `src/tunacode/tools/prompts/present_plan_prompt.xml` | NEW - tool prompt |
| `src/tunacode/exceptions.py` | ToolDeniedError added |
| `src/tunacode/core/state.py` | plan_mode, plan_approval_callback |
| `src/tunacode/ui/commands/__init__.py` | PlanCommand, UpdateCommand simplified |
| `src/tunacode/ui/plan_approval.py` | NEW - plan approval UI |
| `src/tunacode/ui/repl_support.py` | PendingPlanApprovalState |
| `src/tunacode/ui/app.py` | request_plan_approval methods |
| `src/tunacode/constants.py` | PRESENT_PLAN tool name |
| `src/tunacode/core/agents/agent_components/agent_config.py` | tool registration |

## Additional Changes

### Gitignore-Aware Grep

**file_filter.py** enhancements:
- Added `pathspec` library dependency for .gitignore pattern matching
- `load_gitignore()` method loads .gitignore from project root
- `fast_glob()` now checks gitignore patterns for both files and directories
- Hardcoded `EXCLUDE_DIRS` maintained as baseline

### Token Counter Simplification

**token_counter.py:**
- Removed complex tiktoken-based counting
- Replaced with lightweight heuristic (char_count / 4)

## Behavioral Impact

- Plan mode provides structured workflow for exploratory coding
- Users can review agent plans before any code changes occur
- Grep tool now respects project .gitignore, reducing noise
- Update command simplified to single interaction

## Breaking Changes

None. All changes are additive or preserve backward compatibility.

## Related Documentation

- `docs/tools/plan_mode.md` - Plan mode user guide
- `docs/tools/architecture.md` - Updated with plan mode and new tools
- `docs/ui/keyboard_shortcuts.md` - Keyboard shortcuts for plan approval
- `memory-bank/debug_history/2026-01-06_12-45-00_plan-mode-implementation.md` - Execution log

## Related Commits

- `b07b2c48` - Initial plan mode implementation
- `0f7b6d86` - Documentation fixes (JOURNAL.md moved, delta created, gate results corrected)
