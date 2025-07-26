# UI Enhanced Visual Feedback Issue - Fixed

## Issue Description
Enhanced visual feedback was displaying even when `/thoughts` command was not activated. Users were seeing parallel execution headers, tool listings, and timing information that should only appear when `show_thoughts` is enabled.

## Root Cause
Found missing `show_thoughts` conditional checks in `src/tunacode/core/agents/main.py`:

1. **Lines 980-1001**: Final batch visual feedback was displayed without checking `show_thoughts`
2. **Lines 1009-1012**: Timing completion message was displayed without checking `show_thoughts`

## Fix Applied
Added proper `show_thoughts` conditional checks:

### Fix 1 - Final Batch Display (lines 980-1001)
```python
# Before: Missing check
await ui.muted("\n" + "=" * 60)
await ui.muted(f"🚀 FINAL BATCH: Executing {len(buffered_tasks)} buffered read-only tools")
# ... tool listing ...

# After: Added check
if state_manager.session.show_thoughts:
    await ui.muted("\n" + "=" * 60)
    await ui.muted(f"🚀 FINAL BATCH: Executing {len(buffered_tasks)} buffered read-only tools")
    # ... tool listing ...
```

### Fix 2 - Timing Display (lines 1009-1012)
```python
# Before: Missing check
await ui.muted(f"✅ Final batch completed in {elapsed_time:.0f}ms...")

# After: Added check
if state_manager.session.show_thoughts:
    await ui.muted(f"✅ Final batch completed in {elapsed_time:.0f}ms...")
```

## Expected Behavior After Fix
- Enhanced visual feedback (batch headers, tool listings, timing) will ONLY show when:
  - User runs `/thoughts on` command
  - Or explicitly enables thoughts mode
- Normal operation will show minimal output without the detailed parallel execution information

## Testing
To verify the fix:
1. Run tunacode without enabling thoughts
2. Execute commands that trigger parallel tool execution
3. Verify no enhanced visual feedback appears
4. Run `/thoughts on`
5. Execute same commands
6. Verify enhanced visual feedback now appears