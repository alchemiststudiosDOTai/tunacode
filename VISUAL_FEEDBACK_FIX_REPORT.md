# Visual Feedback Fix Report

## Issue Description
The codebase had several instances of unconditional visual feedback that bypassed the `show_thoughts` check, causing users to see debug information and startup messages even when they had not enabled thoughts mode with `/thoughts on`.

## Root Causes Found

### 1. REPL Startup Messages (src/tunacode/cli/repl.py)
- **Lines 388-389**: Model/Context display and "Ready to assist" message shown unconditionally during startup
- **Line 468**: Model/Context display shown after processing commands without checking show_thoughts

### 2. Recursive Executor Logging (src/tunacode/core/recursive/executor.py)
- **Lines 131-133**: "Decomposing complex task (score: X.XX)" logged without checking show_thoughts
- **Lines 138-140**: "Executing task directly (score: X.XX)" logged without checking show_thoughts  
- **Line 260**: "Executing subtask X/Y: ..." logged without checking show_thoughts

### 3. Recursive Progress UI
- The helper functions were already properly gated by show_thoughts checks in the executor
- Direct console.print calls in RecursiveProgressUI class were not being used in practice

## Fixes Applied

### 1. REPL Startup Messages Fix
```python
# Before: Unconditional display
await ui.muted(f"• Model: {model_name} • {context_display}")
await ui.success("Ready to assist")
await ui.line()

# After: Conditional display (first run or thoughts enabled)
if state_manager.session.show_thoughts or not hasattr(state_manager.session, '_startup_shown'):
    await ui.muted(f"• Model: {model_name} • {context_display}")
    await ui.success("Ready to assist")
    await ui.line()
    state_manager.session._startup_shown = True
```

### 2. REPL Command Context Display Fix
```python
# Before: Unconditional display
await ui.muted(f"• Model: {state_manager.session.current_model} • {context_display}")

# After: Conditional display
if state_manager.session.show_thoughts:
    await ui.muted(f"• Model: {state_manager.session.current_model} • {context_display}")
```

### 3. Recursive Executor Logging Fixes
```python
# Before: Unconditional logging
logger.info(f"Decomposing complex task (score: {complexity_result.complexity_score:.2f})")

# After: Conditional logging
if self.state_manager.session.show_thoughts:
    logger.info(f"Decomposing complex task (score: {complexity_result.complexity_score:.2f})")
```

Applied the same pattern to all three logging statements in the recursive executor.

## Testing Updates

### Updated Existing Test
- Modified `test_repl_initialization_basic` to use `show_thoughts = True` since it was testing the startup message display functionality

### Added New Test
- Added `test_repl_initialization_no_thoughts_no_startup_messages` to verify that startup messages are hidden when `show_thoughts = False`

## Expected Behavior After Fix

### With `/thoughts off` (default):
- No startup model/context information displayed
- No "Ready to assist" message on subsequent startups
- No recursive task decomposition messages
- Clean, minimal output focused on user requests

### With `/thoughts on`:
- All debug information displayed as before
- Startup messages shown
- Recursive task progress and decomposition messages visible
- Enhanced visual feedback for parallel tool execution

## Verification

All existing tests pass, including:
- Visual parallel feedback tests
- REPL characterization tests  
- Error handling tests
- Input validation tests

The fix ensures that users only see detailed execution information when they explicitly enable it, providing a cleaner default experience while preserving all debugging capabilities for when they're needed.

## Files Modified
- `src/tunacode/cli/repl.py` - Startup message fixes
- `src/tunacode/core/recursive/executor.py` - Logging message fixes
- `tests/characterization/repl/test_repl_initialization.py` - Test updates

## Files Verified
- `src/tunacode/ui/recursive_progress.py` - Already properly gated
- All existing tests continue to pass