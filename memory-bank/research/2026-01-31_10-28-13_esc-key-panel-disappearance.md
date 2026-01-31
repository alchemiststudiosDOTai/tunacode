# Research – ESC Key Causes Tool Panels/Context to Disappear

**Date:** 2026-01-31
**Owner:** agent
**Phase:** Research
**Last Updated:** 2026-01-31
**Last Updated Note:** Clarified reproduction scenario - happens during streaming cancellation

## Goal

Understand why pressing ESC **during streaming** causes tool panels from that turn to disappear.

## Clarified Scenario

User reports: "While the chat is incoming, if I ESC to try to clear it, the tool panels from that turn disappear."

**Specific behavior:**
1. Agent is streaming a response
2. Tools have executed, panels rendered
3. User presses ESC to cancel
4. Tool panels from that turn vanish

## Findings

### ESC Key Handler

The ESC key is bound in `src/tunacode/ui/app.py:71`:

```python
Binding("escape", "cancel_request", "Cancel", show=False, priority=True)
```

The handler at `src/tunacode/ui/app.py:351-363`:

```python
def action_cancel_request(self) -> None:
    """Cancel the current request, shell command, or clear editor input."""
    if self._current_request_task is not None:
        self._current_request_task.cancel()
        return

    shell_runner = getattr(self, "shell_runner", None)
    if shell_runner is not None and shell_runner.is_running():
        shell_runner.cancel()
        return

    if self.editor.value or self.editor.has_paste_buffer:
        self.editor.clear_input()
```

**This handler does NOT clear the chat container.** It only:
1. Cancels the current request task (if running)
2. Cancels the shell runner (if running)
3. Clears the editor input (if has content)

### Tool Panel Rendering Path

Tool panels are rendered via `ToolResultDisplay` message:
- `src/tunacode/ui/repl_support.py:167-175` posts `ToolResultDisplay`
- `src/tunacode/ui/app.py:287-297` handles it and writes to `chat_container`

```python
def on_tool_result_display(self, message: ToolResultDisplay) -> None:
    panel = tool_panel_smart(...)
    self.chat_container.write(panel)  # Mounted as Static widget
```

Tool panels are mounted as `Static` widgets to `ChatContainer`, NOT rendered in streaming output.

### ChatContainer.clear() Call Sites

`rich_log.clear()` is only called in two places:
- `src/tunacode/ui/commands/__init__.py:79` - `/clear` command
- `src/tunacode/ui/commands/__init__.py:376` - Loading a session

**Neither is triggered by ESC.**

### Request Cancellation Cleanup

When ESC cancels a running request (`src/tunacode/ui/app.py:213-224`):

```python
except asyncio.CancelledError:
    self.notify("Cancelled")
# ...
finally:
    self.streaming_output.update("")  # Clears streaming output
    self.streaming_output.remove_class("active")
```

This clears `streaming_output` (the streaming text area), NOT the `chat_container` where tool panels live.

### Tool Result Callback Flow

Tool panels are rendered when the orchestrator receives `PART_KIND_TOOL_RETURN` from the stream:

```
Stream → orchestrator.py:68 → tool_result_callback() → post_message(ToolResultDisplay) → on_tool_result_display() → chat_container.write()
```

**Key file:** `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py:68`

The callback is called **synchronously within the streaming loop**. When cancellation occurs:
1. `CancelledError` propagates through the call stack
2. Any pending message processing may be interrupted
3. Messages already in Textual's queue should still be processed (independent event loop)

## Key Patterns / Solutions Found

Based on code analysis, **there is no explicit code that clears tool panels on ESC**.

**Most likely cause:** Race condition in message processing

| Hypothesis | Likelihood | Investigation |
|------------|------------|---------------|
| **Message queue race** | High | Messages posted but not processed before cancel |
| Visual scroll jump | Medium | `scroll_end()` on new content hides panels |
| Textual framework behavior | Medium | How Textual handles pending messages on task cancel |
| Widget mount interrupted | Low | Partial mount state during cancellation |

### Potential Root Cause

The `tool_result_callback` posts messages to Textual's queue. If ESC cancels the task:
1. Tool return is received
2. `post_message(ToolResultDisplay)` is called
3. **ESC cancels task before message is processed**
4. `on_tool_result_display` never runs (or runs but mount is interrupted)
5. Panel never appears (or appears then gets lost)

This could explain why panels seem to "disappear" - they may never have been fully mounted.

## Knowledge Gaps

1. **Textual message queue behavior** - How does Textual handle pending messages when an async task is cancelled?
2. **Widget mount atomicity** - Is `mount()` atomic or can it be interrupted mid-operation?
3. **Exact timing** - Need to trace exact sequence of events during cancellation

## Recommended Next Steps

1. **Add debug logging to trace flow:**
   ```python
   # In orchestrator.py before tool_result_callback
   logger.debug(f"About to post ToolResultDisplay for {tool_name}")

   # In app.py on_tool_result_display
   logger.debug(f"Handling ToolResultDisplay for {message.tool_name}")

   # In chat.py write()
   logger.debug(f"Mounting widget to chat_container, child count before: {len(self.children)}")
   ```

2. **Test message queue behavior:**
   - Add a small delay before cancellation to see if panels persist
   - Check if panels appear briefly then vanish vs never appear

3. **Potential fix approaches:**
   - Buffer tool results and render them in the `finally` block
   - Use `call_later()` to ensure message processing completes
   - Add synchronization to ensure mount completes before task can be cancelled

## References

- `src/tunacode/ui/app.py:71` - ESC binding
- `src/tunacode/ui/app.py:351-363` - `action_cancel_request()` handler
- `src/tunacode/ui/app.py:287-297` - `on_tool_result_display()` handler
- `src/tunacode/ui/widgets/chat.py:83-87` - `ChatContainer.clear()` method
- `src/tunacode/ui/commands/__init__.py:72-99` - `/clear` command
- `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py:68` - `tool_result_callback` invocation
- `src/tunacode/core/agents/main.py:443-482` - Cancellation handling in agent
