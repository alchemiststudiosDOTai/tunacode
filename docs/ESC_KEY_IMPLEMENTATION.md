# ESC Key Double-Press Cancellation Implementation

## Overview

This document describes the implementation of the ESC key double-press cancellation feature in TunaCode. The feature allows users to cancel running operations by pressing ESC twice within a 3-second window, providing immediate feedback and robust operation cancellation.

## Problem Statement

### Initial Issues
1. **ESC key not working**: The original ESC handler only cancelled asyncio tasks but didn't provide user feedback or handle cases where no task was running
2. **Missing double-press functionality**: No state tracking for ESC key presses to implement the "press ESC again to stop" behavior
3. **Lack of visual feedback**: Users had no indication that ESC was working or what it accomplished
4. **Incomplete cancellation**: Operations continued running even after ESC messages were displayed

### Root Cause Analysis
- ESC handler only accessed `state_manager.session.current_task` but provided no visual feedback
- No tracking of ESC press count in session state
- ESC handler didn't differentiate between first press (show message) and second press (abort)
- KeyboardInterrupt raised from key handler only aborted input prompt, not the actual running operations
- Missing system-wide cancellation coordination between key handler and processing functions

## Solution Architecture

### 1. Session State Enhancement
**File**: `/root/tunacode/src/tunacode/core/state.py`

Added ESC tracking fields to the `SessionState` class:
```python
# ESC key tracking for double-press functionality
esc_press_count: int = 0
last_esc_time: Optional[float] = None
operation_cancelled: bool = False
```

- `esc_press_count`: Tracks number of consecutive ESC presses
- `last_esc_time`: Timestamp for timeout logic (3-second window)
- `operation_cancelled`: System-wide cancellation flag for coordination

### 2. Enhanced ESC Key Handler
**File**: `/root/tunacode/src/tunacode/ui/keybindings.py`

#### Imports Added
```python
import asyncio
import time
```

#### Core Logic Implementation
```python
@kb.add("escape")
def _escape(event):
    """Handle ESC key with double-press logic: first press warns, second cancels."""
    if not state_manager:
        logger.debug("Escape key pressed without state manager")
        return

    current_time = time.time()
    session = state_manager.session
    
    # Reset counter if too much time has passed (3 seconds timeout)
    if session.last_esc_time and (current_time - session.last_esc_time) > 3.0:
        session.esc_press_count = 0
    
    session.esc_press_count += 1
    session.last_esc_time = current_time
    
    logger.debug(f"ESC key pressed: count={session.esc_press_count}, time={current_time}")
    
    if session.esc_press_count == 1:
        # First ESC press - show warning message
        from ..ui.output import warning
        asyncio.create_task(warning("Hit ESC again within 3 seconds to cancel operation"))
        logger.debug("First ESC press - showing warning")
    else:
        # Second ESC press - cancel operation
        session.esc_press_count = 0  # Reset counter
        logger.debug("Second ESC press - initiating cancellation")
        
        # Mark the session as being cancelled to prevent new operations
        session.operation_cancelled = True
        
        current_task = session.current_task
        if current_task and not current_task.done():
            logger.debug(f"Cancelling current task: {current_task}")
            try:
                current_task.cancel()
                logger.debug("Task cancellation initiated successfully")
            except Exception as e:
                logger.debug(f"Failed to cancel task: {e}")
        else:
            logger.debug(f"No active task to cancel: current_task={current_task}")
        
        # Force exit the current input by raising KeyboardInterrupt
        # This will be caught by the prompt manager and converted to UserAbortError
        logger.debug("Raising KeyboardInterrupt to abort current operation")
        raise KeyboardInterrupt()
```

#### Key Features
- **3-second timeout**: Counter resets if too much time passes between presses
- **Immediate feedback**: First ESC shows warning message
- **Comprehensive cancellation**: Second ESC sets cancellation flag, cancels task, and raises KeyboardInterrupt
- **Enhanced logging**: Debug output shows exactly what's happening during cancellation
- **Error handling**: Graceful handling of task cancellation failures

### 3. System-wide Cancellation Checks
**File**: `/root/tunacode/src/tunacode/cli/repl.py`

#### Multiple Cancellation Checkpoints

**Before Processing Starts**:
```python
async def process_request(text: str, state_manager: StateManager, output: bool = True):
    """Process input using the agent, handling cancellation safely."""
    
    # Check for cancellation before starting (only if explicitly set to True)
    operation_cancelled = getattr(state_manager.session, 'operation_cancelled', False)
    if operation_cancelled is True:
        logger.debug("Operation cancelled before processing started")
        raise CancelledError("Operation was cancelled")
```

**Before Tool Execution**:
```python
async def _tool_handler(part, state_manager: StateManager):
    """Handle tool execution with separated business logic and UI."""
    # Check for cancellation before tool execution (only if explicitly set to True)
    operation_cancelled = getattr(state_manager.session, 'operation_cancelled', False)
    if operation_cancelled is True:
        logger.debug("Tool execution cancelled")
        raise CancelledError("Operation was cancelled")
```

**Before Agent Processing**:
```python
# Check for cancellation before proceeding with agent call (only if explicitly set to True)
operation_cancelled = getattr(state_manager.session, 'operation_cancelled', False)
if operation_cancelled is True:
    logger.debug("Operation cancelled before agent processing")
    raise CancelledError("Operation was cancelled")
```

#### State Cleanup
**After Operation Completion**:
```python
finally:
    await ui.spinner(False, state_manager.session.spinner, state_manager)
    state_manager.session.current_task = None
    # Reset cancellation flag when task completes (if attribute exists)
    if hasattr(state_manager.session, 'operation_cancelled'):
        state_manager.session.operation_cancelled = False
```

**Before New Operations**:
```python
# Reset cancellation flag for new operations (if attribute exists)
if hasattr(state_manager.session, 'operation_cancelled'):
    state_manager.session.operation_cancelled = False
```

### 4. UI Text Updates
**File**: `/root/tunacode/src/tunacode/ui/input.py`

Updated placeholder text to reflect new behavior:
```python
placeholder = formatted_text(
    (
        "<darkgrey>"
        "<bold>Enter</bold> to submit • "
        "<bold>Esc + Enter</bold> for new line • "
        "<bold>Esc twice</bold> to cancel • "
        "<bold>/help</bold> for commands"
        "</darkgrey>"
    )
)
```

## Technical Implementation Details

### 1. Async Coordination
- Uses `asyncio.create_task()` to show warning messages without blocking key handler
- KeyboardInterrupt raised from key handler propagates through prompt session
- Multiple async cancellation checkpoints ensure responsive cancellation

### 2. Test Compatibility
- Uses explicit `is True` checks instead of truthy evaluation to handle MagicMock objects in tests
- Graceful attribute checking with `getattr()` and `hasattr()` for backward compatibility
- Maintains existing error handling and exception flow

### 3. State Management
- Cancellation flag is session-scoped and persists across function calls
- Proper cleanup ensures flag doesn't interfere with subsequent operations
- Timeout logic prevents accidental cancellations from stale ESC presses

### 4. Error Handling
- Enhanced logging provides debugging visibility into cancellation flow
- Graceful degradation when state manager or session attributes are missing
- Exception wrapping maintains existing error handling patterns

## User Experience Flow

### Single ESC Press
1. User presses ESC once
2. Warning message displays: "Hit ESC again within 3 seconds to cancel operation"
3. ESC counter increments to 1
4. Timestamp recorded for timeout logic
5. Operation continues normally

### Double ESC Press (within 3 seconds)
1. User presses ESC second time
2. ESC counter increments to 2
3. System sets `operation_cancelled = True`
4. Current asyncio task cancelled (if running)
5. KeyboardInterrupt raised to abort input
6. Multiple checkpoints detect cancellation flag and abort processing
7. User sees "Operation cancelled by user" message
8. ESC counter resets to 0
9. Cancellation flag reset when operation completes

### Timeout Behavior
1. If more than 3 seconds pass between ESC presses
2. ESC counter automatically resets to 0
3. Next ESC press treated as first press (shows warning)

## Debugging and Monitoring

### Debug Logging
The implementation includes comprehensive debug logging:
```python
logger.debug(f"ESC key pressed: count={session.esc_press_count}, time={current_time}")
logger.debug("First ESC press - showing warning")
logger.debug("Second ESC press - initiating cancellation")
logger.debug(f"Cancelling current task: {current_task}")
logger.debug("Task cancellation initiated successfully")
logger.debug("Operation cancelled before processing started")
logger.debug("Tool execution cancelled")
logger.debug("Operation cancelled before agent processing")
```

### Error Recovery
- Task cancellation failures are logged but don't prevent other cancellation mechanisms
- Missing session attributes are handled gracefully
- MagicMock compatibility for test environments

## Testing

### Test Suite Compatibility
- All existing tests pass without modification
- Uses `is True` checks to avoid MagicMock truthy evaluation issues
- Graceful attribute handling prevents test failures with mock objects

### Manual Testing Scenarios
1. **Basic cancellation**: Start operation, press ESC twice, verify cancellation
2. **Timeout behavior**: Press ESC, wait 4 seconds, press ESC again (should show warning)
3. **No running task**: Press ESC twice when no operation is running
4. **Tool execution**: Cancel during tool confirmation dialogs
5. **Streaming mode**: Cancel during streaming agent responses

## File Changes Summary

| File | Changes | Purpose |
|------|---------|---------|
| `src/tunacode/core/state.py` | Added 3 fields to SessionState | ESC tracking and cancellation coordination |
| `src/tunacode/ui/keybindings.py` | Enhanced ESC handler with double-press logic | Core cancellation functionality |
| `src/tunacode/cli/repl.py` | Added cancellation checks at 3 key points | System-wide cancellation enforcement |
| `src/tunacode/ui/input.py` | Updated placeholder text | User experience clarity |

## Future Enhancements

### Potential Improvements
1. **Configurable timeout**: Allow users to adjust the 3-second timeout
2. **Visual progress indicators**: Show countdown during the 3-second window
3. **Cancellation scope**: Fine-grained control over what gets cancelled
4. **Recovery mechanisms**: Better handling of partial cancellations

### Extensibility
The implementation provides hooks for future enhancements:
- Additional cancellation checkpoints can be added easily
- Timeout logic can be made configurable
- Error handling can be extended for specific operation types
- Logging can be enhanced for better observability

## Conclusion

The ESC key double-press cancellation feature provides a robust, user-friendly way to cancel running operations in TunaCode. The implementation balances immediate responsiveness with safety, ensuring operations can be cancelled quickly while preventing accidental cancellations. The system-wide coordination ensures cancellation works regardless of what phase the operation is in, from input processing to tool execution to agent communication.