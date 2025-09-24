# Archived Issue

Fuzzy-first @-mention matching plan was rolled back on 2025-09-24 after removing the fuzzy utilities and tests for tech debt cleanup. Notes below are preserved for potential future reimplementation.

---

## Architecture Analysis (historical reference)

- `src/tunacode/ui/completers.py:70-128`: Current `FileReferenceCompleter` uses basic `startswith()` matching.
- `src/tunacode/cli/commands/registry.py:305-327`: Previously provided fuzzy fallback via `difflib.get_close_matches` (removed 2025-09-24).
- `src/tunacode/utils/models_registry.py`: Still offers advanced fuzzy matching using `difflib.SequenceMatcher`.

---

## Minimal Implementation Strategy (archived plan)

1. **Create Shared Fuzzy Utility**
   - File: `src/tunacode/utils/fuzzy_utils.py`
   - Reuse existing `difflib.get_close_matches` pattern
   - Export `find_fuzzy_matches()` function with same 0.75 cutoff as commands

2. **Modify FileReferenceCompleter**
   - File: `src/tunacode/ui/completers.py:70-128`
   - Add fuzzy-first logic:
     - Separate files vs directories in scan
     - Apply fuzzy matching to files first (higher priority)
     - Apply fuzzy matching to directories second
     - Preserve existing behavior for exact prefixes
     - Sort results: exact files > fuzzy files > exact dirs > fuzzy dirs

3. **Integration Points**
   - Reuses existing `difflib.get_close_matches` (already imported in `registry.py`)
   - No new dependencies
   - Follows same pattern as command fuzzy matching
   - Preserves all existing security/validation logic

---

## Expected Behavior

- `@testexampl.py` → finds `test_example.py` (fuzzy file match)
- `@testexamp` → shows both files and directories with fuzzy priority
- `@src/` → preserves current directory browsing behavior
- Maintains all existing validation, security, and size limits

---

**Code Changes:** ~30 lines total (new utility + modified completer logic)
