# Research – Agent Feedback Visibility Issue

**Date:** 2025-11-18
**Owner:** Claude (Research Agent)
**Phase:** Research
**Git Commit:** 46340113007f6b8a94e099830a919b7409ab574c
**Git Branch:** master
**Components Analyzed:** `core.agents.main`, `core.agents.agent_components`, `core.tool_authorization`

---

## Goal

Investigate why the agent appears to see intervention feedback (empty response guidance, iteration limits, clarification requests) that should be internal system messages after refactoring `src/tunacode/core/agents/main.py` from `src/tunacode/core/agents/main_legact.py`.

---

## Executive Summary

**CRITICAL FINDING**: The agent feedback visibility issue is **NOT introduced by the refactoring** from `main_legact.py` to `main.py`. Both versions have the identical architectural vulnerability where intervention messages are appended to `state_manager.session.messages` using `create_user_message()`, which creates `ModelRequest` messages with `part_kind="user-prompt"`. These messages are indistinguishable from real user feedback and become visible to the agent in subsequent iterations.

The refactoring changed code **organization** (introducing manager classes and centralizing prompts) but **NOT the underlying message handling mechanism**.

---

## Root Cause Analysis

### The Vulnerability: `create_user_message()` Appends to Agent's Message History

**Location**: `/home/fabian/tunacode/src/tunacode/core/agents/agent_components/agent_helpers.py:42-51`

```python
def create_user_message(content: str, state_manager: StateManager):
    """Create a user message and add it to the session messages."""
    from .message_handler import get_model_messages

    model_request_cls = get_model_messages()[0]  # ModelRequest class
    UserPromptPart = get_user_prompt_part_class()
    user_prompt_part = UserPromptPart(content=content, part_kind="user-prompt")  # LINE 48
    message = model_request_cls(parts=[user_prompt_part], kind="request")
    state_manager.session.messages.append(message)  # LINE 50 - AGENT SEES THIS
    return message
```

**Problem**: Line 50 appends intervention messages directly to `state_manager.session.messages`, which is the persistent conversation history passed to the agent in each iteration.

**Impact**: The agent sees these messages as if they came from the user because:
1. They have `part_kind="user-prompt"` (line 48)
2. They're formatted as `ModelRequest` with `kind="request"` (line 49)
3. They're in the message history passed to `agent.iter()` (main.py:385, main_legact.py:406)

---

## Technical Details

### Message Storage Architecture

**Two Independent Message Layers**:

1. **`state_manager.session.messages`** (persistent session history)
   - Location: `/home/fabian/tunacode/src/tunacode/core/state.py:38`
   - Persists across all agent runs
   - Passed as `message_history` to `agent.iter()` at start of each run
   - **All intervention messages appended here**

2. **`agent_run.ctx.messages`** (ephemeral LLM context)
   - Managed internally by pydantic_ai
   - Lives only during `async with agent.iter(...)` context
   - Used for mid-iteration react guidance injection

### Intervention Message Flow

All four intervention types use the same vulnerable code path:

#### 1. Empty Response Handler
**Trigger**: `EmptyResponseHandler.prompt_action()` at main.py:414
```python
await self.empty_handler.prompt_action(self.message, empty_reason, i)
```

**Message Creation**: `handle_empty_response()` at agent_helpers.py:205-231
```python
force_action_content = create_empty_response_message(...)
create_user_message(force_action_content, state.sm)  # APPENDS TO SESSION.MESSAGES
```

**Content Example**:
```
Response appears empty or incomplete. Recent context:
- Tools used: grep: 2, read_file: 1

Troubleshooting steps:
1. If task is complete: Respond with TUNACODE DONE:
2. If waiting on tool: Specify what you need
3. If blocked: Describe the blocker
```

---

#### 2. No Progress Handler
**Trigger**: `IterationManager.force_action_if_unproductive()` at main.py:425

**Message Creation**: `format_no_progress()` at prompts.py:7-28
```python
no_progress_message = format_no_progress(...)
ac.create_user_message(no_progress_message, self.state_manager)  # APPENDS
```

**Content Example**:
```
ALERT: No tools executed for 3 iterations.

Last productive iteration: 5
Current iteration: 8/15
Task: Research the feedback system...

You're describing actions but not executing them. You MUST:

1. If task is COMPLETE: Start response with TUNACODE DONE:
2. If task needs work: Execute a tool RIGHT NOW (grep, read_file, bash, etc.)
3. If stuck: Explain the specific blocker

NO MORE DESCRIPTIONS. Take ACTION or mark COMPLETE.
```

---

#### 3. Clarification Request Handler
**Trigger**: `IterationManager.ask_for_clarification()` at main.py:451

**Message Creation**: `format_clarification()` at prompts.py:31-44
```python
clarification_message = format_clarification(...)
ac.create_user_message(clarification_message, self.state_manager)  # APPENDS
```

**Content Example**:
```
I need clarification to continue.

Original request: Research the feedback system

Progress so far:
- Iterations: 8
- Tools used: grep: 2, read_file: 1

If the task is complete, I should respond with TUNACODE DONE:
Otherwise, please provide specific guidance on what to do next.
```

---

#### 4. Iteration Limit Handler
**Trigger**: `IterationManager.handle_iteration_limit()` at main.py:460

**Message Creation**: `format_iteration_limit()` at prompts.py:47-61
```python
limit_message = format_iteration_limit(...)
ac.create_user_message(limit_message, self.state_manager)  # APPENDS
```

**Content Example**:
```
I've reached the iteration limit (15).

Progress summary:
- Tools used: grep: 2, read_file: 1
- Iterations completed: 15

Please add more context to the task.
```

---

### Comparison: main_legact.py vs main.py

| Aspect | main_legact.py | main.py | Vulnerability Status |
|--------|----------------|---------|---------------------|
| **Message append mechanism** | `ac.create_user_message()` | `ac.create_user_message()` | ✅ Identical vulnerability |
| **Empty response handling** | `StateFacade` wrapper | `EmptyResponseHandler` class | ✅ Same message appending |
| **State facade** | Yes (lines 66-126) | No (direct access) | ❌ No isolation improvement |
| **Manager classes** | None (inline logic) | 3 manager classes | ❌ Organizational only |
| **React guidance injection** | Direct to `ctx_messages` | Direct to `ctx_messages` | ✅ Same vulnerability |
| **Prompt location** | Inline (scattered) | `/prompts.py` (centralized) | ❌ Content only (not visibility) |
| **Message history copy** | Reference | Shallow copy | ❌ Copy is ineffective |

**Conclusion**: The refactoring is **purely organizational**. It does NOT change the message handling mechanism or fix the visibility issue.

---

## Key File Locations

### Core Message Handling
- **`create_user_message()`**: `src/tunacode/core/agents/agent_components/agent_helpers.py:42-51`
- **`handle_empty_response()`**: `src/tunacode/core/agents/agent_components/agent_helpers.py:205-231`
- **Message storage**: `src/tunacode/core/state.py:38` (`SessionState.messages`)

### Intervention Managers (main.py)
- **`EmptyResponseHandler`**: `src/tunacode/core/agents/main.py:79-110`
- **`IterationManager`**: `src/tunacode/core/agents/main.py:112-195`
- **`ReactSnapshotManager`**: `src/tunacode/core/agents/main.py:197-296`
- **`RequestOrchestrator`**: `src/tunacode/core/agents/main.py:298-492`

### Prompt Templates
- **`format_no_progress()`**: `src/tunacode/core/agents/prompts.py:7-28`
- **`format_clarification()`**: `src/tunacode/core/agents/prompts.py:31-44`
- **`format_iteration_limit()`**: `src/tunacode/core/agents/prompts.py:47-61`

### Agent Orchestration
- **`process_request()` (refactored)**: `src/tunacode/core/agents/main.py:590-612`
- **`process_request()` (legacy)**: `src/tunacode/core/agents/main_legact.py:372-539`

### Related Systems
- **Tool authorization**: `src/tunacode/core/tool_authorization.py`
- **Tool rejection feedback**: `src/tunacode/core/tool_authorization.py:157-224` (`ToolRejectionNotifier`)
- **Node processor**: `src/tunacode/core/agents/agent_components/node_processor.py`

---

## Additional Search Commands

```bash
# Find all usages of create_user_message
grep -rn "create_user_message" src/tunacode/

# Find all intervention message injections
grep -rn "ac\.create_user_message\|agent_components\.create_user_message" src/tunacode/

# Find message appending operations
grep -rn "session\.messages\.append\|messages\.append" src/tunacode/

# Search KB for related patterns
grep -ri "create_user_message\|intervention\|feedback" .claude/
```

---

## Knowledge Gaps

1. **Desired behavior**: Should intervention messages be **completely hidden** from the agent, or should they be **visible but distinguished** (e.g., as system prompts)?

2. **Tool rejection feedback**: The `ToolRejectionNotifier` (tool_authorization.py:157-224) also uses `create_user_message()` to inject user feedback when tools are rejected. Is this feedback **intentionally** visible to the agent, or is it also affected by this vulnerability?

3. **Historical context**: When was this message handling pattern introduced? Was it ever different (e.g., using system prompts instead of user prompts)?

4. **React guidance**: React snapshot guidance is injected into `agent_run.ctx.messages` as `system-prompt` parts (main.py:284-286). Why is this treated differently from intervention messages?

5. **Testing coverage**: The tests in `tests/test_agents_main.py` verify that intervention handlers are called, but do they verify message visibility/isolation?

---

## Recommendations

### 1. **Distinguish Intervention Messages from User Messages**

**Problem**: Intervention messages have `part_kind="user-prompt"`, making them indistinguishable from real user feedback.

**Solution**: Create intervention messages with `part_kind="system-prompt"` instead:

```python
def create_intervention_message(content: str, state_manager: StateManager):
    """Create a system intervention message (not visible as user feedback)."""
    from .message_handler import get_model_messages

    model_request_cls, _, system_prompt_part_cls = get_model_messages()
    system_part = system_prompt_part_cls(content=content, part_kind="system-prompt")
    message = model_request_cls(parts=[system_part], kind="request")
    state_manager.session.messages.append(message)
    return message
```

**Impact**: The agent will see these as system guidance rather than user feedback.

---

### 2. **Isolate Intervention Messages in Separate Channel**

**Problem**: All messages are appended to the same `session.messages` list.

**Solution**: Create a separate `session.intervention_messages` list and merge only when needed:

```python
@dataclass
class SessionState:
    messages: MessageHistory = field(default_factory=list)
    intervention_messages: MessageHistory = field(default_factory=list)  # NEW

def prepare_agent_context(state_manager: StateManager) -> list:
    """Merge user messages and intervention messages for agent context."""
    # Interleave intervention messages at appropriate points
    return merge_messages(
        state_manager.session.messages,
        state_manager.session.intervention_messages
    )
```

**Impact**: Clear separation between user conversation and system interventions.

---

### 3. **Add Message Visibility Metadata**

**Problem**: No way to distinguish message sources or visibility levels.

**Solution**: Add metadata to messages:

```python
@dataclass
class MessageMetadata:
    source: Literal["user", "agent", "system_intervention", "tool_rejection"]
    visibility: Literal["agent_visible", "agent_hidden", "user_only"]
    timestamp: str

# Attach metadata to messages
message.metadata = MessageMetadata(
    source="system_intervention",
    visibility="agent_visible",  # or "agent_hidden"
    timestamp=datetime.now().isoformat()
)
```

**Impact**: Clear tracking of message provenance and intended visibility.

---

### 4. **Review Tool Rejection Feedback Flow**

**Location**: `src/tunacode/core/tool_authorization.py:193-224`

**Current behavior**: Tool rejection feedback is injected via `create_user_message()`:

```python
def notify_rejection(self, request: ToolConfirmationRequest, response: ToolConfirmationResponse):
    # ...
    if response.instructions:
        guidance = (
            f"Tool '{request.tool_name}' was rejected.\n\n"
            f"User feedback:\n{response.instructions}\n\n"
            "Please acknowledge and adjust your approach accordingly."
        )
        create_user_message(guidance, self.state_manager)
```

**Question**: Is this feedback **intentionally** visible to the agent as user input, or should it also be treated as a system intervention?

**Recommendation**: If this is intentional user feedback (the user explicitly provided guidance), keep it as `user-prompt`. Otherwise, use the new `create_intervention_message()`.

---

### 5. **Update Tests to Verify Message Visibility**

**Current test coverage** (`tests/test_agents_main.py`):
- ✅ Verifies intervention handlers are called
- ✅ Verifies counters are updated
- ❌ Does NOT verify message visibility or isolation

**Recommended test additions**:

```python
async def test_intervention_messages_marked_as_system():
    """Verify intervention messages are not user-prompt parts."""
    # ... create intervention
    messages = state_manager.session.messages
    intervention_msg = messages[-1]
    assert intervention_msg.parts[0].part_kind == "system-prompt"

async def test_intervention_messages_isolated():
    """Verify intervention messages stored separately."""
    # ... create intervention
    assert len(state_manager.session.intervention_messages) == 1
    assert len(state_manager.session.messages) == 0  # Only user messages
```

---

### 6. **Document Intended Behavior**

**Missing documentation**:
- No specification of which messages should be visible to the agent
- No clear separation between "user feedback" and "system intervention"
- No guidance on when to use `create_user_message()` vs a hypothetical `create_intervention_message()`

**Recommendation**: Create architectural documentation in `.claude/docs_model_friendly/` explaining:
1. Message visibility model
2. When to use user prompts vs system prompts
3. Intervention message lifecycle
4. Tool rejection feedback flow

---

## References

### Documentation
- `.claude/docs_model_friendly/option3_feedback_flow.md` - Feedback flow documentation
- `documentation/agent/main-agent-architecture.md` - Main agent architecture

### Related Code
- All intervention handlers use `create_user_message()` from agent_helpers.py:50
- React guidance uses direct `ctx_messages.append()` at main.py:290
- Tool rejection uses `create_user_message()` at tool_authorization.py:218

### Test Files
- `tests/test_agents_main.py` - Agent intervention tests (do not verify visibility)

### Git References
GitHub permalinks (on master branch):
- create_user_message: https://github.com/USER/tunacode/blob/46340113007f6b8a94e099830a919b7409ab574c/src/tunacode/core/agents/agent_components/agent_helpers.py#L42-L51
- EmptyResponseHandler: https://github.com/USER/tunacode/blob/46340113007f6b8a94e099830a919b7409ab574c/src/tunacode/core/agents/main.py#L79-L110
- IterationManager: https://github.com/USER/tunacode/blob/46340113007f6b8a94e099830a919b7409ab574c/src/tunacode/core/agents/main.py#L112-L195

---

## Next Steps

1. **Clarify requirements**: Determine intended visibility behavior for intervention messages
2. **Choose solution**: Select from recommendations above (system-prompt, separate channel, or metadata)
3. **Implement fix**: Update `create_user_message()` or create new `create_intervention_message()`
4. **Update callers**: Modify all intervention handlers to use new function
5. **Add tests**: Verify message visibility and isolation
6. **Document behavior**: Add architectural docs explaining message visibility model
