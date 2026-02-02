# Research - ESC Key Logic Flow in TUI Conversation

**Date:** 2026-02-02
**Owner:** agent
**Phase:** Research

## Goal

Map the complete ESC key logic flow when a user is in conversation with the agent, including how chat disappears and panel dismissal behavior.

## Findings

### ESC Key Binding Location

- `src/tunacode/ui/app.py:65` - Global ESC binding with priority flag
  ```python
  Binding("escape", "cancel_request", "Cancel", show=False, priority=True)
  ```

### Main ESC Handler - Priority Cascade

**File:** `src/tunacode/ui/app.py:343-356`

```
User presses ESC
       |
       v
action_cancel_request() executes
       |
       v
Cascading checks (first match wins):
       |
       +---> 1. Active request task? --> Cancel asyncio task, RETURN
       |
       +---> 2. Shell command running? --> Cancel shell subprocess, RETURN
       |
       +---> 3. Editor has content/paste buffer? --> Clear editor input
```

**Code Flow:**

1. **Cancel Running Agent Request** (lines 345-347):
   - Checks `self._current_request_task is not None`
   - Calls `self._current_request_task.cancel()` - cancels asyncio task
   - Returns immediately (no fallthrough)

2. **Cancel Shell Command** (lines 349-352):
   - Checks `shell_runner.is_running()`
   - Calls `shell_runner.cancel()` to terminate subprocess
   - Shell runner at `src/tunacode/ui/shell_runner.py:119-137`
   - Returns immediately

3. **Clear Editor Input** (lines 354-355):
   - Checks `self.editor.value or self.editor.has_paste_buffer`
   - Calls `editor.clear_input()` at `src/tunacode/ui/widgets/editor.py:110-113`

### Modal Screen ESC Handling

Modal screens intercept ESC before the app-level handler:

| Screen | File | Binding Line | Action |
|--------|------|--------------|--------|
| ProviderPickerScreen | `screens/model_picker.py` | 94 | Two-phase: clear filter first, then dismiss |
| ModelPickerScreen | `screens/model_picker.py` | 212 | Two-phase: clear filter first, then dismiss |
| SessionPickerScreen | `screens/session_picker.py` | 55 | Dismiss with None |
| ThemePickerScreen | `screens/theme_picker.py` | 48 | Revert theme, dismiss with None |
| UpdateConfirmScreen | `screens/update_confirm.py` | 46 | Dismiss with False |
| SetupScreen | `screens/setup.py` | 29 | Skip setup, dismiss with False |

### Two-Phase ESC in Picker Modals

**File:** `src/tunacode/ui/screens/model_picker.py:160-164`

```
ESC pressed in Model/Provider Picker
       |
       v
Filter has text? ----YES----> Clear filter input, rebuild options
       |                      event.stop() prevents propagation
       NO                     (User must press ESC again to close)
       |
       v
action_cancel() called
       |
       v
self.dismiss(None) --> Modal closes, callback receives None
```

### Chat Container Behavior

**File:** `src/tunacode/ui/widgets/chat.py`

- ChatContainer is **always visible** - no show/hide toggle mechanism
- Has `clear()` method (lines 83-87) but no visibility state
- Cannot be "dismissed" - it's a permanent part of the main layout
- ESC does NOT hide the chat container

### Editor Clear Logic

**File:** `src/tunacode/ui/widgets/editor.py:110-113`

```python
def clear_input(self) -> None:
    self.value = ""
    self._clear_paste_buffer()
    self.scroll_to(x=0, y=0, animate=False, immediate=True)
```

## Key Patterns / Solutions Found

- **Priority Binding**: `priority=True` ensures ESC takes precedence over widget-level bindings
- **Cascade Pattern**: Handler uses if-return cascade for clear priority ordering
- **Event Propagation Control**:
  - `event.prevent_default()` stops widget's default behavior
  - `event.stop()` prevents propagation to parent/bindings
- **Screen Dismissal**: All modals use Textual's `self.dismiss(value)` pattern
- **No Hidden State**: No panel visibility toggles or state flags - modals are pushed/popped from screen stack

## Visual Flow Diagram

```
+-------------------+
|  User presses ESC |
+--------+----------+
         |
         v
+--------+----------+     YES    +----------------------+
| Modal screen      +----------->| Modal's on_key()     |
| on screen stack?  |            | or action_cancel()   |
+--------+----------+            +----------+-----------+
         | NO                               |
         v                                  v
+--------+----------+            +----------+-----------+
| App binding:      |            | screen.dismiss()     |
| action_cancel_    |            | pops screen stack    |
| request()         |            +----------------------+
+--------+----------+
         |
         v
+--------+----------+     YES    +----------------------+
| Request task      +----------->| task.cancel()        |
| running?          |            | RETURN               |
+--------+----------+            +----------------------+
         | NO
         v
+--------+----------+     YES    +----------------------+
| Shell command     +----------->| shell_runner.cancel()|
| running?          |            | RETURN               |
+--------+----------+            +----------------------+
         | NO
         v
+--------+----------+     YES    +----------------------+
| Editor has        +----------->| editor.clear_input() |
| content?          |            +----------------------+
+--------+----------+
         | NO
         v
+--------+----------+
| No action taken   |
+-------------------+
```

## Knowledge Gaps

- No documentation on why chat container uses always-visible pattern vs modal approach
- No explicit "panel save" functionality found - sessions are managed via StateManager, not visible panels

## References

- `src/tunacode/ui/app.py` - Main application, ESC binding and handler (lines 65, 343-356)
- `src/tunacode/ui/screens/model_picker.py` - Two-phase ESC pattern (lines 160-164, 289-293)
- `src/tunacode/ui/widgets/editor.py` - Editor clear logic (lines 110-113)
- `src/tunacode/ui/shell_runner.py` - Shell cancellation (lines 119-137)
- `src/tunacode/ui/widgets/chat.py` - Chat container (always visible)
