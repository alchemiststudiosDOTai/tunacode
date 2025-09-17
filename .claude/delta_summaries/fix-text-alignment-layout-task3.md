# Fix Text Alignment and Layout (TaskMaster Task #3)

**Date**: 2025-07-23
**Task**: Fix text alignment issues in the safety branch warning dialog
**Status**: Completed

## Problem Summary
The TunaCode CLI was displaying formatting issues in UI dialogs:
1. Inconsistent bracket formatting between async/sync versions of tool confirmations
2. "Thinking..." text was hardcoded instead of using the UI constant
3. Inconsistent panel padding across different UI elements

## Changes Made

### 1. Updated `src/tunacode/ui/panels.py`
- **Line 89**: Replaced hardcoded `"Thinking..."` with `UI_THINKING_MESSAGE` constant
- Added import for the constant to ensure consistent formatting

### 2. Updated `src/tunacode/ui/tool_ui.py` (Async Version)
- **Lines 114-116**: Added square brackets to match sync version
  - Changed: `"  1. Yes (default)"` → `"  [1] Yes (default)"`
  - Changed: `"  2. Yes..."` → `"  [2] Yes..."`
  - Changed: `"  3. No..."` → `"  [3] No..."`

### 3. Standardized Panel Padding in `src/tunacode/ui/tool_ui.py` (Sync Version)
- **Lines 148-170**: Updated panel configuration:
  - Used `DEFAULT_PANEL_PADDING` constant for consistent spacing
  - Added `ROUNDED` box style to match other panels
  - Fixed inner content padding to `(0, 1, 0, 1)`
  - Added necessary imports

## Testing
- ✅ Linting passed (auto-formatted by ruff)
- ✅ UI tool confirmation tests passed
- ✅ No ANSI code rendering issues

## Impact
These changes ensure:
- Consistent text alignment across all UI elements
- No visible ANSI escape sequences in output
- Professional appearance matching TunaCode's UI patterns
- Better terminal compatibility

## Related Files
- `src/tunacode/ui/panels.py`
- `src/tunacode/ui/tool_ui.py`
- `src/tunacode/ui/constants.py`
- `src/tunacode/constants.py`
