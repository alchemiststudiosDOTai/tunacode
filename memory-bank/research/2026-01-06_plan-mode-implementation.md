# Research - Plan Mode Implementation
**Date:** 2026-01-06
**Owner:** Claude Agent
**Phase:** Research

## Goal
Understand existing architecture to implement plan mode: a read-only exploration mode where the agent gathers context, then presents a plan for user approval before any writes occur.

## User Requirements Summary
1. `/plan` triggers read-only mode (no write tool permissions)
2. Extra prompt instructs agent: "You are in read-only planning mode. Do not use write tools until user approves a plan."
3. Code hard-blocks write tools (authorization layer)
4. Agent uses a "present plan" tool when ready
5. User approves (creates PLAN.md) or denies (agent takes feedback)

## Flow
```
/plan
  -> plan_mode = True
  -> inject prompt: "read-only mode, use present_plan when ready"
  -> auth layer blocks all writes/bash

Agent explores codebase...
  -> calls present_plan(markdown_content)
  -> UI shows: [1] Approve  [2] Deny

User presses 1:
  -> write PLAN.md to cwd
  -> plan_mode = False (exit)
  -> agent can now use write tools

User presses 2:
  -> prompt for feedback text
  -> return "denied: <feedback>" to agent
  -> stay in plan mode, agent revises
```

## Findings

### 1. Current PlanCommand - Placeholder Only
- **File:** `src/tunacode/ui/commands/__init__.py:168-173`
- **Status:** Stub that shows "Plan mode not yet implemented"
```python
class PlanCommand(Command):
    name = "plan"
    description = "Toggle read-only planning mode"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        app.notify("Plan mode not yet implemented", severity="warning")
```

### 2. Tool Categorization - Already Defined
- **File:** `src/tunacode/constants.py:70-80`
```python
READ_ONLY_TOOLS = [read_file, grep, list_dir, glob, react, research_codebase, web_fetch]
WRITE_TOOLS = [write_file, update_file]
EXECUTE_TOOLS = [bash]
```

### 3. Authorization Rule Chain - Extensible
- **File:** `src/tunacode/tools/authorization/rules.py`
- **Pattern:** Chain of responsibility - rules evaluated by priority (lower = first)
- **Existing rules:**
  | Rule | Priority | Logic |
  |------|----------|-------|
  | `ReadOnlyToolRule` | 200 | Read-only tools skip confirmation |
  | `TemplateAllowedToolsRule` | 210 | Template-defined bypass |
  | `YoloModeRule` | 300 | All tools skip confirmation |
  | `ToolIgnoreListRule` | 310 | Per-tool ignore list |

- **Key insight:** Need a `PlanModeBlockRule` with **lowest priority (e.g., 100)** that returns `DENY` (not just "skip confirmation") for write/execute tools

### 4. Session State - Pattern to Follow
- **File:** `src/tunacode/core/state.py:47-49`
```python
tool_ignore: list[ToolName] = field(default_factory=list)
yolo: bool = False
# Add: plan_mode: bool = False
```

### 5. Authorization Context - Needs Extension
- **File:** `src/tunacode/tools/authorization/context.py:13-32`
```python
@dataclass(frozen=True)
class AuthContext:
    yolo_mode: bool
    tool_ignore_list: tuple[ToolName, ...]
    active_template: Template | None
    # Add: plan_mode: bool
```

### 6. Authorization Protocol - Current Limitations
- **File:** `src/tunacode/tools/authorization/rules.py:13-20`
- **Current Protocol:**
```python
class AuthorizationRule(Protocol):
    def should_allow_without_confirmation(
        self, tool_name: ToolName, context: AuthContext
    ) -> bool: ...

    def priority(self) -> int: ...
```
- **Gap:** Returns `bool` only (confirm vs skip). No `DENY` path exists.
- **Policy at `policy.py:15-19`:**
```python
def should_confirm(self, tool_name: ToolName, context: AuthContext) -> bool:
    for rule in self._rules:
        if rule.should_allow_without_confirmation(tool_name, context):
            return False
    return True
```

### 7. Tool Callback Flow - Where Block Would Happen
- **File:** `src/tunacode/ui/repl_support.py:86-106`
```python
async def _callback(part: Any, _node: Any = None) -> None:
    tool_handler = state_manager.tool_handler or ToolHandler(state_manager)
    state_manager.set_tool_handler(tool_handler)

    if not tool_handler.should_confirm(part.tool_name):
        return  # ALLOW path

    # CONFIRM path - asks user
    ...
    if not tool_handler.process_confirmation(response, part.tool_name):
        raise UserAbortError("User aborted tool execution")
```
- **Gap:** No DENY branch - only ALLOW or CONFIRM (which can be rejected by user)

### 8. Tool Confirmation UI - Existing Pattern
- **File:** `src/tunacode/ui/app.py:326-335`
- **Pattern:** Future-based confirmation with inline Rich Panel
```python
async def request_tool_confirmation(
    self, request: ToolConfirmationRequest
) -> ToolConfirmationResponse:
    future: asyncio.Future[ToolConfirmationResponse] = asyncio.Future()
    self.pending_confirmation = PendingConfirmationState(future=future, request=request)
    self._show_inline_confirmation(request)
    return await future
```
- **Key Handler at `app.py:493-513`:** Captures 1/2/3 keypresses to resolve future

### 9. Rejection Feedback to Agent
- **File:** `src/tunacode/tools/authorization/notifier.py:14-35`
```python
def notify_rejection(
    self,
    tool_name: ToolName,
    response: ToolConfirmationResponse,
    state: StateManager,
) -> None:
    guidance = getattr(response, "instructions", "").strip()
    message = (
        f"Tool '{tool_name}' execution cancelled before running.\n"
        f"{guidance_section}\n"
        "Do not assume the operation succeeded; "
        "request updated guidance or offer alternatives."
    )
    create_user_message(message, state)
```

### 10. Tool Registration Pattern
- **File:** `src/tunacode/core/agents/agent_components/agent_config.py:335-358`
- **Pattern:** Explicit list + factory functions for state-aware tools
```python
# State-aware tools use factories
todowrite = create_todowrite_tool(state_manager)
research_codebase = create_research_codebase_tool(state_manager)
tools_list.append(Tool(todowrite, max_retries=max_retries, strict=tool_strict_validation))
```

### 11. Tool Prompt Loading
- **File:** `src/tunacode/tools/xml_helper.py:10-34`
```python
@lru_cache(maxsize=32)
def load_prompt_from_xml(tool_name: str) -> str | None:
    prompt_file = Path(__file__).parent / "prompts" / f"{tool_name}_prompt.xml"
```
- Tool descriptions loaded from `src/tunacode/tools/prompts/{tool_name}_prompt.xml`

### 12. System Prompt Composition
- **File:** `src/tunacode/core/prompting/prompting_engine.py:42-62`
- **Pattern:** Three stages: load sections -> compose template -> resolve placeholders
- **Built-in placeholders:** `{{CWD}}`, `{{OS}}`, `{{DATE}}`
- **Custom registration:**
```python
engine.register("PLAN_MODE", lambda: instructions if plan_mode else "")
```

## Key Patterns / Solutions Found

### Pattern 1: Authorization Result Enum
Extend from bool to tri-state:
```python
class AuthorizationResult(Enum):
    ALLOW = "allow"      # Skip confirmation
    CONFIRM = "confirm"  # Require confirmation
    DENY = "deny"        # Block entirely

PLAN_MODE_BLOCKED_TOOLS = WRITE_TOOLS + EXECUTE_TOOLS

class PlanModeBlockRule(AuthorizationRule):
    priority = 100  # Highest priority (checked first)

    def evaluate(self, tool_name: ToolName, context: AuthContext) -> AuthorizationResult:
        if context.plan_mode and tool_name in PLAN_MODE_BLOCKED_TOOLS:
            return AuthorizationResult.DENY
        return AuthorizationResult.CONFIRM  # Let other rules decide
```

### Pattern 2: present_plan Tool Factory
Following todo.py pattern:
```python
# src/tunacode/tools/present_plan.py
def create_present_plan_tool(state_manager: StateManager) -> Callable:
    async def present_plan(plan_content: str) -> str:
        """Present a plan to the user for approval."""
        # Implementation: show plan, await approval
        pass

    prompt = load_prompt_from_xml("present_plan")
    if prompt:
        present_plan.__doc__ = prompt
    return present_plan
```

### Pattern 3: Plan Confirmation UI Options

**Option A: Reuse inline confirmation (simplest)**
- Create `ToolConfirmationRequest` with plan content
- Reuse existing [1] Yes / [2] Skip / [3] No UI
- On denial, capture feedback via `ToolConfirmationResponse.instructions`

**Option B: Modal screen (richer UX)**
- Create `PlanConfirmScreen(Screen[bool])` like `UpdateConfirmScreen`
- Use `await app.push_screen_wait(PlanConfirmScreen(plan_content))`
- More control over layout and feedback input

### Pattern 4: Prompt Injection Options

**Option A: Custom Placeholder Provider (recommended)**
```python
engine = get_prompting_engine()
engine.register("PLAN_MODE", lambda: plan_mode_prompt if state.session.plan_mode else "")
```
Add `{{PLAN_MODE}}` to `MAIN_TEMPLATE` at appropriate location.

**Option B: Post-composition append**
```python
# In agent_config.py:328
if state_manager.session.plan_mode:
    system_prompt += "\n\n" + load_plan_mode_instructions()
```

**Option C: New section file**
- Add `PLAN_MODE` to `SystemPromptSection` enum
- Create `prompts/sections/plan_mode.xml`
- Conditionally include in template

### Pattern 5: Plan Mode Prompt Content
```xml
<PLAN_MODE>
You are in READ-ONLY PLANNING MODE.

DISABLED tools: write_file, update_file, bash. Do not attempt to use them.
All other tools (read_file, grep, list_dir, glob, web_fetch, react, research_codebase, todo_write) are available.

When you have gathered enough context:
1. Call `present_plan` with your detailed plan (markdown format)
2. User will approve (1) or deny (2)
3. If approved: PLAN.md is written and plan mode exits
4. If denied: incorporate user feedback and revise
</PLAN_MODE>
```

## Implementation Checklist

### Phase 1: State & Authorization
- [ ] Add `plan_mode: bool = False` to `SessionState` at `core/state.py`
- [ ] Add `plan_mode: bool` to `AuthContext` at `tools/authorization/context.py`
- [ ] Create `AuthorizationResult` enum at `tools/authorization/types.py`
- [ ] Update `AuthorizationRule` protocol to return `AuthorizationResult`
- [ ] Create `PlanModeBlockRule` at `tools/authorization/rules.py`
- [ ] Update `AuthorizationPolicy.should_confirm()` to return `AuthorizationResult`
- [ ] Update `ToolHandler` to handle DENY at `tools/authorization/handler.py`
- [ ] Update callback at `ui/repl_support.py` to handle DENY (raise `ToolDeniedError`)

### Phase 2: Command & Tool
- [ ] Update `PlanCommand` to toggle `state.session.plan_mode`
- [ ] Create `present_plan.py` with factory function at `tools/`
- [ ] Create `present_plan_prompt.xml` at `tools/prompts/`
- [ ] Add `ToolName.PRESENT_PLAN` to constants
- [ ] Register tool in `agent_config.py` (conditionally for plan mode)

### Phase 3: Prompt Injection
- [ ] Register `PLAN_MODE` placeholder provider in prompting engine
- [ ] Add `{{PLAN_MODE}}` to `MAIN_TEMPLATE`
- [ ] Create plan mode instructions content

### Phase 4: Plan Approval UI
- [ ] Choose UI approach (inline confirmation vs modal screen)
- [ ] Implement plan display and approval capture
- [ ] On approval: write `PLAN.md` to cwd
- [ ] On approval: set `plan_mode = False` and notify agent
- [ ] On denial: capture feedback and inject as user message

## Design Decisions (Confirmed)

1. **Plan Approval UI**: Use existing confirmation pattern (1 to approve, 2 to deny) - same as tool edits
2. **Bash**: Completely blocked in plan mode - NO bash at all
3. **Exit Behavior**: Auto-exit plan mode when user approves (confirms with 1)

## References

### Core Files to Modify
| File | Purpose |
|------|---------|
| `src/tunacode/core/state.py:47-49` | Add plan_mode to SessionState |
| `src/tunacode/tools/authorization/context.py:13-32` | Add plan_mode to AuthContext |
| `src/tunacode/tools/authorization/rules.py:13-72` | Add PlanModeBlockRule, update protocol |
| `src/tunacode/tools/authorization/policy.py:15-19` | Handle DENY result |
| `src/tunacode/tools/authorization/handler.py:42-44` | Handle DENY in should_confirm |
| `src/tunacode/ui/repl_support.py:86-106` | Handle DENY in callback |
| `src/tunacode/ui/commands/__init__.py:168-173` | Implement PlanCommand |
| `src/tunacode/core/agents/agent_components/agent_config.py:335-358` | Register present_plan tool |
| `src/tunacode/core/prompting/prompting_engine.py:27-40` | Register PLAN_MODE provider |
| `src/tunacode/core/prompting/templates.py:5-45` | Add {{PLAN_MODE}} placeholder |

### Reference Files (Read-Only Patterns)
| File | Relevance |
|------|-----------|
| `src/tunacode/constants.py:70-80` | Tool categorization |
| `src/tunacode/tools/todo.py:124-222` | Factory pattern for state-aware tools |
| `src/tunacode/tools/xml_helper.py:10-34` | XML prompt loading |
| `src/tunacode/ui/app.py:326-335` | Tool confirmation flow |
| `src/tunacode/ui/app.py:493-513` | Key handler for responses |
| `src/tunacode/tools/authorization/notifier.py:14-35` | Rejection feedback to agent |
