# Startup Banner Panel Refresh

**Date**: 2025-10-01
**Component**: `src/tunacode/ui/output.py`

## Change
- Replaced the multiline ASCII banner padding with a Rich `Panel` helper using a rounded box and themed border color.
- Centered the TunaCode fish art within the panel and added explicit padding constants for consistent spacing.

## Impact
- CLI startup now presents a framed, easier-to-read banner without altering downstream messaging behavior.

## Verification
- `ruff check --fix .`
