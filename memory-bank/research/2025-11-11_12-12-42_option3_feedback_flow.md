# Research – Option 3 Feedback Flow Issue

**Date:** 2025-11-11 12:12:42
**Owner:** Claude (Research Agent)
**Phase:** Research
**Git Commit:** e353150d940749e1ed2e1e76f2c331883b5e8658
**Repository:** alchemiststudiosDOTai/tunacode

## Goal

Investigate why Option 3 (reject tool with feedback) doesn't work as intended in the TunaCode CLI. The user provides feedback when rejecting a tool execution, but the agent never processes this feedback. Additionally, analyze the recently added `_extract_feedback_from_last_message()` solution and identify potential issues.

## Problem Statement

When a user selects Option 3 during tool confirmation:
1. ✅ Feedback is collected and stored in `ToolConfirmationResponse.instructions`
2. ✅ Feedback message is injected into `session.messages` via `create_user_message()`
3. ✅ Tool execution is aborted via `UserAbortError`
4. ❌ **Agent loop terminates** before processing the feedback
5. ❌ **No new iteration** occurs - feedback sits unused in message history

## Research Methods

- File Analysis: Read key files in feedback flow chain
- Code Tracing: Traced execution path from UI to error handling
- Timeline Analysis: Mapped exact sequence of events with state changes
- Pattern Analysis: Examined sub-agent findings for related patterns

## Findings

### 1. Root Cause: Message History Snapshot Mechanism

**Location:** [src/tunacode/core/agents/main.py:443](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/agents/main.py#L443)

```python
# Message history is snapshotted at the START of process_request()
message_history = _prepare_message_history(state)

# Agent iterates using this snapshot, NOT the live session.messages
async with agent.iter(message, message_history=message_history) as agent_run:
```

**Why This Matters:**
- `_prepare_message_history()` creates a **snapshot copy** of `session.messages` at line 443
- The agent uses this snapshot throughout the entire iteration
- When feedback is added via `create_user_message()` during tool execution, it updates `session.messages`
- **BUT** the agent is still using the old snapshot, so it never sees the feedback
- Feedback will only be visible in the NEXT call to `process_request()`

**Supporting Evidence:**

[src/tunacode/core/agents/main.py:96-97](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/agents/main.py#L96-L97)
```python
@property
def messages(self) -> list:
    return list(getattr(self.sm.session, "messages", []))  # Returns a COPY
```

[src/tunacode/core/agents/main.py:154-155](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/agents/main.py#L154-L155)
```python
def _prepare_message_history(state: StateFacade) -> list:
    return state.messages  # Returns a COPY of session.messages
```

### 2. Complete Feedback Injection Flow

#### Step-by-Step Execution:

**Step 1: User Interaction**
- [src/tunacode/ui/tool_ui.py:141-147](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/ui/tool_ui.py#L141-L147)
```python
if resp == "3":
    instructions = await self._prompt_rejection_feedback(state_manager)
    return ToolConfirmationResponse(
        approved=False,
        abort=True,
        instructions=instructions,  # User's feedback stored here
    )
```

**Step 2: Confirmation Processing**
- [src/tunacode/cli/repl_components/tool_executor.py:78-87](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/cli/repl_components/tool_executor.py#L78-L87)
```python
response = _tool_ui.show_sync_confirmation(request)

if not tool_handler_instance.process_confirmation(response, part.tool_name):
    return True  # Abort

should_abort = await run_in_terminal(confirm_func)

if should_abort:
    raise UserAbortError("User aborted.")
```

**Step 3: Feedback Injection**
- [src/tunacode/core/tool_handler.py:120-121](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/tool_handler.py#L120-L121)
```python
if not response.approved or response.abort:
    self._notifier.notify_rejection(tool_name, response, self.state)
```

- [src/tunacode/core/tool_authorization.py:332-364](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/tool_authorization.py#L332-L364)
```python
def notify_rejection(self, tool_name: ToolName, response: ToolConfirmationResponse, state: StateManager):
    guidance = getattr(response, "instructions", "").strip()

    if guidance:
        guidance_section = f"User guidance:\n{guidance}"
    else:
        guidance_section = "User cancelled without additional instructions."

    message = (
        f"Tool '{tool_name}' execution cancelled before running.\n"
        f"{guidance_section}\n"
        "Do not assume the operation succeeded; "
        "request updated guidance or offer alternatives."
    )

    create_user_message(message, state)  # ✅ FEEDBACK ADDED TO session.messages
```

**Step 4: Message Creation**
- [src/tunacode/core/agents/agent_components/agent_helpers.py:42-51](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/agents/agent_components/agent_helpers.py#L42-L51)
```python
def create_user_message(content: str, state_manager: StateManager):
    model_request_cls = get_model_messages()[0]
    UserPromptPart = get_user_prompt_part_class()
    user_prompt_part = UserPromptPart(content=content, part_kind="user-prompt")
    message = model_request_cls(parts=[user_prompt_part], kind="request")
    state_manager.session.messages.append(message)  # ✅ APPENDED TO LIVE MESSAGE LIST
    return message
```

**Step 5: Error Propagation Chain**

1. **Raised:** [src/tunacode/cli/repl_components/tool_executor.py:87](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/cli/repl_components/tool_executor.py#L87)
2. **Re-raised:** [src/tunacode/core/agents/agent_components/node_processor.py:499](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/agents/agent_components/node_processor.py#L499)
3. **Re-raised:** [src/tunacode/core/agents/main.py:580](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/agents/main.py#L580)
4. **Caught (ORIGINAL):** [src/tunacode/cli/repl.py:400-402](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/cli/repl.py#L400-L402)

```python
except UserAbortError:
    # CLAUDE_ANCHOR[7b2c1d4e]: Guided aborts inject user instructions; skip legacy banner.
    pass  # ❌ ERROR IGNORED - NO FURTHER PROCESSING
```

### 3. Timeline Analysis

```
T0: Agent is in iteration N, processing tool call
    State: agent.iter() running with message_history snapshot

T1: Tool confirmation UI shown to user
    Location: tool_ui.py:141

T2: User selects option "3" and types: "use a different file path"
    Location: tool_ui.py:142

T3: ToolConfirmationResponse created
    Fields: approved=False, abort=True, instructions="use a different file path"
    Location: tool_ui.py:143-147

T4: process_confirmation() called
    Location: tool_executor.py:80

T5: notify_rejection() triggered
    Location: tool_handler.py:121

T6: Feedback message formatted
    Content: "Tool 'write_file' execution cancelled before running.\n
              User guidance:\nuse a different file path\n
              Do not assume the operation succeeded..."
    Location: tool_authorization.py:357-362

T7: create_user_message() appends to session.messages ✅
    State: session.messages now contains feedback message
    Problem: Agent is still using old message_history snapshot
    Location: agent_helpers.py:50

T8: UserAbortError raised
    Location: tool_executor.py:87

T9: Error propagates through node_processor.py:499

T10: Error propagates through main.py:580, exits agent.iter() loop
    State: Agent iteration terminates, feedback never processed

T11: Error caught in repl.py:400 (ORIGINAL CODE)
    Action: pass (silently ignored)
    Result: Feedback sits in session.messages, never consumed

T12: Control returns to REPL input prompt
    State: Feedback message orphaned in message history
```

### 4. The New Solution Analysis

**Recently Added:** [src/tunacode/cli/repl.py:275-310, 438-447](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/cli/repl.py#L275-L310)

The user just added `_extract_feedback_from_last_message()` to attempt fixing this issue:

```python
def _extract_feedback_from_last_message(state_manager: StateManager) -> str | None:
    """Extract user guidance feedback from the last message in session.messages."""
    if not state_manager.session.messages:
        return None

    last_msg = state_manager.session.messages[-1]

    if not hasattr(last_msg, "parts"):
        return None

    for part in last_msg.parts:
        if hasattr(part, "content") and isinstance(part.content, str):
            content = part.content

            if "User guidance:" in content:
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if "User guidance:" in line and i + 1 < len(lines):
                        guidance = lines[i + 1].strip()
                        if guidance and guidance != "User cancelled without additional instructions.":
                            return guidance

    return None
```

**Modified Error Handler:** [src/tunacode/cli/repl.py:438-447](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/cli/repl.py#L438-L447)

```python
except UserAbortError:
    # CLAUDE_ANCHOR[7b2c1d4e]: Guided aborts inject user instructions; skip legacy banner.
    # Check if there's feedback to process immediately
    feedback = _extract_feedback_from_last_message(state_manager)
    if feedback:
        # Process the feedback as a new request
        await execute_repl_request(feedback, state_manager, output=output)
        return
    # No feedback, just abort normally
    pass
```

#### Solution Analysis: What It Does

1. Catches `UserAbortError` in REPL
2. Extracts feedback text from last message (e.g., "use a different file path")
3. Recursively calls `execute_repl_request()` with just the feedback text
4. Creates a new agent request with new UUID and fresh iteration counters

#### Solution Analysis: Potential Issues

**Issue 1: Message History Duplication**

Current state after Option 3:
```python
session.messages = [
    # ... previous messages ...
    ModelRequest(parts=[UserPromptPart(content="User's original request")]),
    ModelResponse(parts=[...]),  # Agent's response
    ModelRequest(parts=[ToolCallPart(tool_name="write_file", ...)]),  # Tool call that was rejected
    ModelRequest(parts=[UserPromptPart(content="Tool 'write_file' execution cancelled...\nUser guidance:\nuse a different file path\n...")]),  # ← Formatted feedback message
]
```

After recursive `execute_repl_request("use a different file path", ...)`:
```python
session.messages = [
    # ... all the above messages still present ...
    ModelRequest(parts=[UserPromptPart(content="use a different file path")]),  # ← NEW MESSAGE with extracted feedback only
]
```

**Problem:** The formatted feedback message is still in history, creating duplication. The agent sees both:
- The full formatted message: "Tool 'write_file' execution cancelled... User guidance: use a different file path..."
- The extracted feedback as a new request: "use a different file path"

**Issue 2: Context Loss**

The recursive call creates a **completely new request**:
- New request ID (UUID) generated
- Iteration counters reset to 0
- Tool call history continues to accumulate but iteration tracking restarts
- Agent loses context about:
  - Which specific tool was rejected
  - What the original tool parameters were
  - Why the tool was being called in the first place

**Original context:**
```
User: "Create a config file at /etc/app/config.json"
Agent: <attempts to write_file with filepath="/etc/app/config.json">
User: [Rejects tool] "use /home/user/.config/app.json instead"
```

**New request context:**
```
User: "use /home/user/.config/app.json instead"
Agent: <has no context about what this refers to>
```

**Issue 3: Potential Infinite Loop**

Scenario:
1. Agent tries tool X with parameters A
2. User rejects with feedback: "try parameters B"
3. Recursive call creates new request with "try parameters B"
4. Agent tries tool X with parameters B
5. User rejects again with feedback: "try parameters C"
6. Recursive call creates new request with "try parameters C"
7. ... continues indefinitely

No mechanism prevents:
- Repeated rejections
- Circular feedback loops
- User exhaustion

**Issue 4: State Inconsistency**

**State before recursive call:**
```python
state_manager.session.current_iteration = 3
state_manager.session.tool_calls = [
    {"tool": "grep", "args": {...}},
    {"tool": "read_file", "args": {...}},
    {"tool": "write_file", "args": {...}}  # The rejected tool
]
state_manager.session.request_id = "abc123"
```

**State during recursive call:**
```python
state_manager.session.current_iteration = 0  # RESET!
state_manager.session.tool_calls = [
    {"tool": "grep", "args": {...}},
    {"tool": "read_file", "args": {...}},
    {"tool": "write_file", "args": {...}},  # Old tool calls still present
    # ... new tool calls will be added ...
]
state_manager.session.request_id = "xyz789"  # NEW ID!
```

Iteration tracking becomes meaningless when it resets mid-conversation.

**Issue 5: No Message Cleanup**

The original formatted feedback message remains in `session.messages`:
```
"Tool 'write_file' execution cancelled before running.\nUser guidance:\nuse a different file path\n..."
```

This message:
- Serves no further purpose
- Adds noise to the agent's context window
- Could confuse the agent about the conversation state
- Consumes tokens unnecessarily

**Issue 6: Incomplete Extraction Logic**

The extraction only gets the line immediately after "User guidance:":

```python
if "User guidance:" in line and i + 1 < len(lines):
    guidance = lines[i + 1].strip()
```

**Problems:**
- Multi-line feedback is truncated (only first line extracted)
- Assumes specific formatting (fragile to format changes)
- Doesn't handle edge cases (empty lines, special characters)

Example failure:
```
User guidance:
use a different file path
and make sure it's writable
```
Only extracts: "use a different file path" (loses second line)

### 5. Architectural Issues

**The Design Disconnect:**

```
┌─────────────────────────────────────────────────────┐
│ DESIGN ASSUMPTION (from comment)                    │
│                                                      │
│ "Guided aborts inject user instructions"            │
│                                                      │
│ Expected: Feedback → Messages → Agent Continues →   │
│           Agent Processes Feedback                   │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│ ACTUAL BEHAVIOR (original code)                     │
│                                                      │
│ Feedback → Messages → Exception Raised →            │
│ Agent Exits → Error Caught → pass → Feedback        │
│ Orphaned                                             │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│ NEW SOLUTION (attempted fix)                        │
│                                                      │
│ Feedback → Messages → Exception Raised →            │
│ Agent Exits → Extract Feedback → Recursive Call →   │
│ New Request (with issues)                            │
└─────────────────────────────────────────────────────┘
```

### 6. Related Patterns in Codebase

**React Tool Guidance Injection:**

Found in [src/tunacode/core/agents/main.py:249-261](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/agents/main.py#L249-L261):

```python
if agent_run_ctx is not None:
    ctx_messages = getattr(agent_run_ctx, "messages", None)
    if isinstance(ctx_messages, list):
        ModelRequest, _, SystemPromptPart = ac.get_model_messages()
        system_part = SystemPromptPart(
            content=f"[React Guidance] {guidance_entry}",
            part_kind="system-prompt",
        )
        # CLAUDE_ANCHOR[react-system-injection]
        # Append synthetic system message so LLM receives react guidance next turn
        ctx_messages.append(ModelRequest(parts=[system_part], kind="request"))
```

**Key Difference:**
- React guidance injects into `agent_run_ctx.messages` (the LIVE context messages)
- This works because it modifies the context the agent is actively using
- Feedback injection modifies `session.messages` (the historical messages)
- The agent doesn't see `session.messages` changes because it uses a snapshot

## Knowledge Gaps

1. **pydantic-ai internals**: How does `agent.iter()` manage its message context? Can we inject messages mid-iteration?

2. **Continuation mechanism**: Is there a way to resume or continue an agent iteration after UserAbortError without starting fresh?

3. **Context window impact**: What's the token cost of keeping rejected tool messages in history?

4. **User experience testing**: Has the new solution been tested with:
   - Multi-line feedback?
   - Repeated rejections?
   - Complex tool parameters?

5. **Error recovery**: What happens if the recursive `execute_repl_request()` also raises UserAbortError?

## References

### Key Files Analyzed

- [src/tunacode/ui/tool_ui.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/ui/tool_ui.py) - UI layer for tool confirmation
- [src/tunacode/cli/repl_components/tool_executor.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/cli/repl_components/tool_executor.py) - Tool execution and error raising
- [src/tunacode/core/tool_handler.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/tool_handler.py) - Business logic coordination
- [src/tunacode/core/tool_authorization.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/tool_authorization.py) - Feedback injection via notify_rejection()
- [src/tunacode/core/agents/agent_components/agent_helpers.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/agents/agent_components/agent_helpers.py) - Message creation utilities
- [src/tunacode/core/agents/agent_components/node_processor.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/agents/agent_components/node_processor.py) - Error propagation
- [src/tunacode/core/agents/main.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/core/agents/main.py) - Main agent loop and message history snapshotting
- [src/tunacode/cli/repl.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/cli/repl.py) - REPL error handling and new solution

### Documentation Reference

- [.claude/docs_model_friendly/option3_feedback_flow.md](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/.claude/docs_model_friendly/option3_feedback_flow.md) - Original analysis document

## Summary

### The Core Problem

Option 3 feedback doesn't work because:

1. **Snapshot Isolation**: Message history is snapshotted at the start of `process_request()`. Feedback added during tool execution updates `session.messages` but not the snapshot the agent is using.

2. **Immediate Abort**: `UserAbortError` is raised immediately after feedback injection, terminating the agent iteration before it can process the new message.

3. **Silent Error Handling**: The REPL catches `UserAbortError` and does nothing, preventing any continuation mechanism.

### The Attempted Solution

The new `_extract_feedback_from_last_message()` solution attempts to:
- Extract feedback text from the injected message
- Recursively call `execute_repl_request()` to create a new agent request

### Issues with Current Solution

1. **Message duplication** - Original formatted message remains in history
2. **Context loss** - Agent doesn't know what tool was rejected or why
3. **Potential infinite loops** - No protection against repeated rejections
4. **State inconsistency** - Iteration counters reset mid-conversation
5. **No cleanup** - Orphaned messages pollute context window
6. **Fragile extraction** - Only handles single-line feedback

### Recommended Next Steps

1. **Test current solution** with various scenarios:
   - Multi-line feedback
   - Repeated rejections
   - Complex tool parameters
   - Error cases

2. **Consider alternative approaches**:
   - **Option A**: Modify `agent.iter()` context directly (like React tool does)
   - **Option B**: Don't raise UserAbortError - let agent continue naturally
   - **Option C**: Enhance extraction to preserve full context and clean up messages

3. **Add protection mechanisms**:
   - Rejection counter to prevent infinite loops
   - Message cleanup after extraction
   - Multi-line feedback support
   - Context preservation (tool name, original parameters)

4. **Update documentation**:
   - Correct misleading comment at [repl.py:439](https://github.com/alchemiststudiosDOTai/tunacode/blob/e353150d940749e1ed2e1e76f2c331883b5e8658/src/tunacode/cli/repl.py#L439)
   - Document expected behavior vs actual behavior
   - Add architecture decision records for chosen solution

## Additional Search Suggestions

- `grep -ri "agent_run" src/` - Find agent context manipulation patterns
- `grep -ri "ctx.messages" src/` - Find existing mid-iteration message injection
- `grep -ri "continuation" src/` - Check for any continuation mechanisms
- Review pydantic-ai documentation on agent.iter() lifecycle and context management
