# Option 3 Feedback Flow - Current Logic Map

## Complete Flow: User Selects Option 3 with Feedback

### Step 1: User Interaction
**File:** `src/tunacode/ui/tool_ui.py`
- **Line 129:** UI displays option 3: `"[3] No, and tell {APP_NAME} what to do differently"`
- **Line 130-137:** User selects option "3"
- **Line 141-147:** If `resp == "3"`:
  ```python
  instructions = await self._prompt_rejection_feedback(state_manager)
  return ToolConfirmationResponse(
      approved=False,
      abort=True,
      instructions=instructions,  # User's feedback stored here
  )
  ```
- **Line 206-212:** `_prompt_rejection_feedback()` collects user input:
  ```python
  guidance = await ui.input(
      session_key=self.REJECTION_FEEDBACK_SESSION,
      pretext=self.REJECTION_GUIDANCE_PROMPT,  # "Describe what the agent should do instead..."
      state_manager=state_manager,
  )
  return guidance.strip() if guidance else ""
  ```

### Step 2: Confirmation Processing
**File:** `src/tunacode/cli/repl_components/tool_executor.py`
- **Line 78:** `response = _tool_ui.show_sync_confirmation(request)`
  - Returns `ToolConfirmationResponse(approved=False, abort=True, instructions="do caps")`
- **Line 80:** `if not tool_handler_instance.process_confirmation(response, part.tool_name):`
  - Calls `process_confirmation()` which returns `False` (because `abort=True`)
- **Line 81:** `return True  # Abort`
- **Line 84:** `should_abort = await run_in_terminal(confirm_func)` → `True`
- **Line 86-87:** `raise UserAbortError("User aborted.")`

### Step 3: Rejection Notification (Feedback Injection)
**File:** `src/tunacode/core/tool_handler.py`
- **Line 120-121:** `process_confirmation()` checks:
  ```python
  if not response.approved or response.abort:
      self._notifier.notify_rejection(tool_name, response, self.state)
  ```
  - This is called BEFORE returning `False`, so feedback IS processed

**File:** `src/tunacode/core/tool_authorization.py`
- **Line 332-364:** `ToolRejectionNotifier.notify_rejection()`:
  ```python
  guidance = getattr(response, "instructions", "").strip()  # "do caps"
  
  if guidance:
      guidance_section = f"User guidance:\n{guidance}"  # "User guidance:\ndo caps"
  else:
      guidance_section = "User cancelled without additional instructions."
  
  message = (
      f"Tool '{tool_name}' execution cancelled before running.\n"
      f"{guidance_section}\n"
      "Do not assume the operation succeeded; "
      "request updated guidance or offer alternatives."
  )
  
  create_user_message(message, state)  # ✅ FEEDBACK IS ADDED TO MESSAGES HERE
  ```

**File:** `src/tunacode/core/agents/agent_components/agent_helpers.py`
- **Line 42-51:** `create_user_message()`:
  ```python
  def create_user_message(content: str, state_manager: StateManager):
      model_request_cls = get_model_messages()[0]
      UserPromptPart = get_user_prompt_part_class()
      user_prompt_part = UserPromptPart(content=content, part_kind="user-prompt")
      message = model_request_cls(parts=[user_prompt_part], kind="request")
      state_manager.session.messages.append(message)  # ✅ MESSAGE ADDED TO SESSION
      return message
  ```

### Step 4: Error Propagation
**File:** `src/tunacode/cli/repl_components/tool_executor.py`
- **Line 89-91:** `UserAbortError` is caught and re-raised:
  ```python
  except UserAbortError:
      patch_tool_messages(MSG_OPERATION_ABORTED_BY_USER, state_manager)
      raise  # Re-raised to propagate up
  ```

**File:** `src/tunacode/core/agents/agent_components/node_processor.py`
- **Line 497-500:** Tool callback exception handling:
  ```python
  try:
      await tool_callback(part, node)
  except UserAbortError:
      raise  # Re-raised, propagates to process_request()
  ```

**File:** `src/tunacode/core/agents/main.py`
- **Line 580-581:** `UserAbortError` is caught and re-raised:
  ```python
  except UserAbortError:
      raise  # Propagates to REPL
  ```

### Step 5: REPL Error Handling (THE PROBLEM)
**File:** `src/tunacode/cli/repl.py`
- **Line 400-402:** `UserAbortError` is caught and silently ignored:
  ```python
  except UserAbortError:
      # CLAUDE_ANCHOR[7b2c1d4e]: Guided aborts inject user instructions; skip legacy banner.
      pass  # ❌ ERROR IS IGNORED - NO FURTHER PROCESSING
  ```

## The Problem

### What Happens:
1. ✅ Feedback is collected: `"do caps"` stored in `ToolConfirmationResponse.instructions`
2. ✅ Feedback is injected: Message added to `state_manager.session.messages` via `create_user_message()`
3. ✅ Tool execution is aborted: `UserAbortError` raised
4. ❌ **Agent loop stops**: Error caught in REPL and silently ignored with `pass`
5. ❌ **No new iteration**: Agent doesn't process the feedback message because:
   - The current `process_request()` call has ended
   - No new `process_request()` is triggered
   - The feedback message sits in `session.messages` but is never consumed

### The Feedback Message Structure:
The message added to `session.messages` looks like:
```
Tool 'update_file' execution cancelled before running.
User guidance:
do caps
Do not assume the operation succeeded; request updated guidance or offer alternatives.
```

### Why It Doesn't Work:
- The agent's `process_request()` has already completed or is in the middle of processing
- When `UserAbortError` is raised, it stops the current iteration
- The REPL catches it and does `pass`, ending the request
- The feedback message is in the session, but the agent won't see it until the NEXT user request
- If the agent is streaming or has already generated output, it may display that cached output instead of processing the feedback

## Current State After Option 3:

```
session.messages = [
    ...previous messages...,
    UserMessage("Tool 'update_file' execution cancelled...\nUser guidance:\ndo caps\n...")
]
```

But the agent has stopped processing, so this message is never consumed in the current request cycle.

## Files Involved:

1. **UI Collection:**
   - `src/tunacode/ui/tool_ui.py` (lines 106-148, 206-212)

2. **Response Structure:**
   - `src/tunacode/types.py` (lines 119-125)

3. **Confirmation Processing:**
   - `src/tunacode/cli/repl_components/tool_executor.py` (lines 78-91)
   - `src/tunacode/core/tool_handler.py` (lines 105-123)

4. **Feedback Injection:**
   - `src/tunacode/core/tool_authorization.py` (lines 332-364)
   - `src/tunacode/core/agents/agent_components/agent_helpers.py` (lines 42-51)

5. **Error Propagation:**
   - `src/tunacode/core/agents/agent_components/node_processor.py` (lines 497-500)
   - `src/tunacode/core/agents/main.py` (lines 580-581)
   - `src/tunacode/cli/repl.py` (lines 400-402) ← **PROBLEM LOCATION**

## Key Insight:

The feedback IS being added to the session messages correctly, but the agent loop terminates before it can process that message. The message will only be seen on the NEXT user request, not immediately after providing feedback.

### Critical Finding: Message History Snapshot

**File:** `src/tunacode/core/agents/main.py`
- **Line 96-97:** `StateFacade.messages` property:
  ```python
  @property
  def messages(self) -> list:
      return list(getattr(self.sm.session, "messages", []))  # Returns a COPY
  ```
- **Line 154-155:** `_prepare_message_history()`:
  ```python
  def _prepare_message_history(state: StateFacade) -> list:
      return state.messages  # Returns a COPY of session.messages
  ```
- **Line 443:** `message_history = _prepare_message_history(state)`
  - This creates a **snapshot COPY** of `session.messages` at the START of `process_request()`
- **Line 453:** `async with agent.iter(message, message_history=message_history) as agent_run:`
  - The agent uses this snapshot COPY, NOT the live `session.messages` list

**What This Means:**
1. When `process_request()` starts, it captures `session.messages` at that moment
2. The agent iterates using that snapshot
3. When feedback is added via `create_user_message()` during tool execution, it's added to `session.messages`
4. **BUT** the agent is still using the old snapshot, so it never sees the feedback
5. The feedback will only be seen on the NEXT `process_request()` call when a new snapshot is taken

**The Root Cause:**
- Message history is snapshotted at the start of `process_request()`
- Feedback added during execution updates `session.messages` but not the snapshot
- Agent continues with stale snapshot that doesn't include feedback
- Even if we didn't catch `UserAbortError`, the agent wouldn't see the feedback in the current request

