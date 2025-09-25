# Prompt Toolkit Fuzzy Reintegration

Fuzzy-first matching resumed on 2025-09-24 using prompt_toolkit's native fuzzy completers. Notes below capture the revived implementation plan and historical context for further refinement.

---

## Architecture Analysis (current state)

- `src/tunacode/ui/completers.py:23-74`: `CommandCompleter` wraps registry commands with `FuzzyWordCompleter` for near-miss suggestions.
- `src/tunacode/ui/completers.py:80-164`: `FileReferenceCompleter` blends exact prefix ordering with fuzzy scoring for files then directories.
- `src/tunacode/utils/models_registry.py`: Continues to expose `SequenceMatcher`-based fuzzy similarity for models.

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
