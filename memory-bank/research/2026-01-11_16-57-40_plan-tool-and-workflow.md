---
title: Plan Tool and Workflow Research
owner: claude
phase: research
date: 2026-01-11
last_updated: 2026-01-11
last_updated_by: claude
git_commit: bfa1bc8
git_branch: 222-register-present-plan-tool
tags:
  - plan-tool
  - workflow
  - authorization
  - ui-components
---

# Research – Plan Tool and Workflow

**Date:** 2026-01-11
**Owner:** claude
**Phase:** Research

## Goal

Map out the plan tool, plan mode workflow, and how it integrates with the tunacode agent system. Understand the complete flow from entering plan mode to exiting, including authorization rules, UI components, and state management.

## Findings

### Core Implementation Files

| File | Purpose |
|------|---------|
| [`src/tunacode/tools/present_plan.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/tools/present_plan.py) | Present plan tool - agent calls this to submit plans for approval |
| [`src/tunacode/ui/plan_approval.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/plan_approval.py) | Plan approval UI components - renders panel, handles key events |
| [`src/tunacode/ui/commands/__init__.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/commands/__init__.py) (lines 266-303) | PlanCommand - toggles plan mode via `/plan` command |
| [`src/tunacode/tools/authorization/rules.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/tools/authorization/rules.py) (lines 72-87) | PlanModeBlockRule - blocks write/execute tools in plan mode |
| [`src/tunacode/core/state.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/core/state.py) (lines 53-56) | Session state - plan_mode and plan_approval_callback |
| [`src/tunacode/ui/app.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/app.py) (line 312, 535) | UI integration - request_plan_approval, key handling |

### Entry/Exit Patterns

**Entry Point:** `/plan` command ([`commands/__init__.py:266`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/commands/__init__.py#L266))

```python
async def execute(self, app: TextualReplApp, args: str) -> None:
    session = app.state_manager.session
    session.plan_mode = not session.plan_mode

    if session.plan_mode:
        # Set up the approval callback
        async def plan_approval_callback(plan_content: str) -> tuple[bool, str]:
            return await app.request_plan_approval(plan_content)

        session.plan_approval_callback = plan_approval_callback
        # Update status bar, inject instruction message
```

**Exit Paths (3 ways):**
1. **Approved** - Plan written to `PLAN.md`, mode exits
2. **User Exits (key [3])** - Mode exits without saving
3. **Manual Toggle** - User types `/plan` again

### Authorization System

**PlanModeBlockRule** ([`rules.py:72-87`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/tools/authorization/rules.py#L72))

```python
class PlanModeBlockRule:
    """Block write/execute tools in plan mode. Highest priority - checked first."""

    def priority(self) -> int:
        return 100  # Highest priority

    def evaluate(self, tool_name: ToolName, context: AuthContext) -> AuthorizationResult:
        if context.plan_mode and tool_name in PLAN_MODE_BLOCKED_TOOLS:
            return AuthorizationResult.DENY
        return AuthorizationResult.CONFIRM
```

**Blocked tools:** `write_file`, `update_file`, `bash`

**Available tools in plan mode:** `read_file`, `grep`, `list_dir`, `glob`, `web_fetch`, `react`, `research_codebase`, `todowrite`, `present_plan`

### Present Plan Tool

**Implementation** ([`present_plan.py:45-92`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/tools/present_plan.py#L45))

```python
async def present_plan(plan_content: str) -> str:
    session = state_manager.session

    if not session.plan_mode:
        return PLAN_NOT_IN_PLAN_MODE

    approval_callback = getattr(session, "plan_approval_callback", None)

    if approval_callback is not None:
        approved, feedback = await approval_callback(plan_content)
    else:
        approved, feedback = True, ""  # Non-interactive auto-approve

    if approved:
        plan_path = Path.cwd() / "PLAN.md"
        plan_path.write_text(plan_content, encoding="utf-8")
        session.plan_mode = False
        return PLAN_APPROVED_MESSAGE

    if feedback == EXIT_PLAN_MODE_SENTINEL:
        session.plan_mode = False
        return PLAN_EXITED_MESSAGE

    return PLAN_DENIED_MESSAGE.format(feedback=feedback)
```

### UI Approval Workflow

**Request Approval** ([`plan_approval.py:113-144`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/plan_approval.py#L113))

```python
async def request_plan_approval(
    plan_content: str,
    pending_state_holder: PlanApprovalHolder,
    rich_log: RichLog,
) -> tuple[bool, str]:
    future: asyncio.Future[tuple[bool, str]] = asyncio.Future()
    pending = PendingPlanApprovalState(future=future, plan_content=plan_content)
    pending_state_holder.pending_plan_approval = pending

    panel = render_plan_approval_panel(plan_content)
    rich_log.write(panel, expand=True)

    return await future
```

**Key Handler** ([`plan_approval.py:77-110`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/plan_approval.py#L77))
- `1` key: Approve → `future.set_result((True, ""))`
- `2` key: Feedback → `future.set_result((False, "Please revise..."))`
- `3` key: Exit → `future.set_result((False, EXIT_PLAN_MODE_SENTINEL))`

**Panel Layout (NeXTSTEP 4-zone):**
1. Title bar: "Plan Mode - Review Implementation Plan"
2. Primary viewport: Markdown plan content
3. Context zone: Shows "Output: PLAN.md will be created in project root"
4. Actions zone: [1] Approve, [2] Feedback, [3] Exit

### State Management

**SessionState** ([`state.py:53-56`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/core/state.py#L53))

```python
@dataclass
class SessionState:
    # ... other fields
    plan_mode: bool = False
    plan_approval_callback: Any | None = None
```

**PendingPlanApprovalState** ([`repl_support.py:101-106`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/repl_support.py#L101))

```python
@dataclass
class PendingPlanApprovalState:
    future: asyncio.Future[tuple[bool, str]]
    plan_content: str
```

### Complete Data Flow

```
1. User types: /plan
   └─> PlanCommand.execute() [commands/__init__.py:270]
       └─> session.plan_mode = True
       └─> session.plan_approval_callback = app.request_plan_approval
       └─> status_bar.set_mode("PLAN")
       └─> Inject PLAN_MODE_INSTRUCTION message

2. Agent receives plan mode instruction, gathers context with read-only tools

3. Agent calls present_plan(plan_content)
   └─> present_plan() [present_plan.py:45]
       └─> Check session.plan_mode
       └─> Call session.plan_approval_callback(plan_content)
           └─> app.request_plan_approval() [app.py:312]
               └─> request_plan_approval() [plan_approval.py:113]
                   └─> Create asyncio.Future
                   └─> Store in pending_plan_approval
                   └─> Render approval panel to RichLog
                   └─> await future (blocks here)

4. User presses key (1, 2, or 3)
   └─> app.on_key() [app.py:507]
       └─> Check pending_plan_approval
       └─> _handle_plan_approval_key() [app.py:535]
           └─> handle_plan_approval_key() [plan_approval.py:77]
               └─> If key "1": future.set_result((True, ""))
               └─> If key "2": future.set_result((False, "Please revise..."))
               └─> If key "3": future.set_result((False, EXIT_PLAN_MODE_SENTINEL))

5. Future completes, approval callback returns
   └─> present_plan() receives (approved, feedback)
       └─> If approved:
           └─> Write plan_content to PLAN.md
           └─> session.plan_mode = False
       └─> If feedback == EXIT_PLAN_MODE_SENTINEL:
           └─> session.plan_mode = False
       └─> Return message to agent

6. Status bar updates on resource bar refresh
   └─> _update_resource_bar() [app.py:454-456]
       └─> status_bar.set_mode("PLAN" if session.plan_mode else None)
```

## Key Patterns

1. **Callback Pattern**: Tool receives callback at creation time, stored in session. Decouples tool from UI layer.

2. **Future/Promise Pattern**: `asyncio.Future[tuple[bool, str]]` for blocking on async user input. Future created in `request_plan_approval()`, resolved in key handler.

3. **Protocol-based Type Safety**: `PlanApprovalHolder` protocol defines interface for objects holding pending approval state.

4. **Priority-based Authorization**: `PlanModeBlockRule` has priority 100 (highest), evaluated before other rules.

5. **State Machine**: Plan mode is a boolean state in `SessionState` that controls tool availability.

6. **Factory Pattern**: Tool created via `create_present_plan_tool(state_manager)` for dependency injection.

## Constants

| Constant | Value | Location |
|----------|-------|----------|
| `EXIT_PLAN_MODE_SENTINEL` | `"__EXIT_PLAN_MODE__"` | [`constants.py:96`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/constants.py#L96) |

## Related Documentation

- [`memory-bank/plan/2026-01-09_19-00-00_register-present-plan-tool-222.md`](../plan/2026-01-09_19-00-00_register-present-plan-tool-222.md) - Planning document for registering the present_plan tool (PR #222)
- [`memory-bank/execute/2026-01-09_19-05-00_register-present-plan-tool-222.md`](../execute/2026-01-09_19-05-00_register-present-plan-tool-222.md) - Execution notes for the same feature

## Knowledge Gaps

None identified. The planning system is well-documented and follows clear architectural patterns.

## References

**Source Files:**
- [`src/tunacode/tools/present_plan.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/tools/present_plan.py)
- [`src/tunacode/ui/plan_approval.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/plan_approval.py)
- [`src/tunacode/ui/commands/__init__.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/commands/__init__.py)
- [`src/tunacode/tools/authorization/rules.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/tools/authorization/rules.py)
- [`src/tunacode/core/state.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/core/state.py)
- [`src/tunacode/ui/app.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/app.py)
- [`src/tunacode/types/state.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/types/state.py)
- [`src/tunacode/ui/repl_support.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/repl_support.py)
- [`src/tunacode/constants.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/constants.py)
- [`src/tunacode/tools/prompts/present_plan_prompt.xml`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/tools/prompts/present_plan_prompt.xml)
- [`src/tunacode/ui/widgets/status_bar.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/ui/widgets/status_bar.py)
- [`src/tunacode/core/agents/agent_components/agent_config.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/core/agents/agent_components/agent_config.py)
- [`src/tunacode/tools/authorization/context.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/tools/authorization/context.py)
- [`src/tunacode/tools/authorization/factory.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/tools/authorization/factory.py)
- [`src/tunacode/tools/authorization/policy.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/src/tunacode/tools/authorization/policy.py)

**Test Files:**
- [`tests/test_present_plan.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/bfa1bc8/tests/test_present_plan.py)

**Additional Research:**
- [`memory-bank/research/2026-01-08_23-46-19_plan-permission-keeps-asking.md`](./2026-01-08_23-46-19_plan-permission-keeps-asking.md) - Research on plan permission behavior
