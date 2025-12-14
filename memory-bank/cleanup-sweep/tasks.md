# Cleanup Tasks - Prioritized List

**Generated:** 2025-12-14
**Total Tasks:** 12
**Estimated Impact:** ~300 lines to DELETE

---

## Task 1: Remove Empty TYPE_CHECKING Block
**Type:** import
**Files:** `/home/tuna/tunacode/src/tunacode/core/agents/agent_components/state_transition.py`
**Actions:**
  - DELETE lines 6 (`from typing import TYPE_CHECKING`)
  - DELETE lines 10-11 (`if TYPE_CHECKING: pass`)
**Estimated Time:** 1 minute
**Risk:** low
**Verification:** `uv run ruff check src/tunacode/core/agents/agent_components/state_transition.py`

---

## Task 2: Remove Unused Tool Import
**Type:** import
**Files:** `/home/tuna/tunacode/src/tunacode/core/agents/main.py`
**Actions:**
  - DELETE lines 18-19 (TYPE_CHECKING block with unused Tool import)
**Estimated Time:** 1 minute
**Risk:** low
**Verification:** `uv run ruff check src/tunacode/core/agents/main.py`

---

## Task 3: Remove check_query_satisfaction Dead Code
**Type:** dead-code
**Files:**
  - `/home/tuna/tunacode/src/tunacode/core/agents/main.py`
  - `/home/tuna/tunacode/src/tunacode/core/agents/__init__.py`
**Actions:**
  - DELETE lines 516-523 from main.py (function definition)
  - DELETE `"check_query_satisfaction"` from `__all__` in main.py (line 41)
  - DELETE import in `__init__.py` line 18
  - DELETE `"check_query_satisfaction"` from `__all__` in `__init__.py` (line 36)
**Estimated Time:** 3 minutes
**Risk:** low
**Verification:** `uv run pytest && uv run ruff check src/tunacode/core/agents/`

---

## Task 4: Remove Unused GLOB_BATCH Constant
**Type:** dead-code
**Files:** `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py`
**Actions:**
  - DELETE line 12 (`GLOB_BATCH = 500  # Streaming batch size`)
**Estimated Time:** 1 minute
**Risk:** low
**Verification:** `uv run ruff check src/tunacode/tools/grep_components/file_filter.py`

---

## Task 5: Remove Duplicate _truncate_line() from web_fetch.py
**Type:** duplication
**Files:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/web_fetch.py`
**Actions:**
  - DELETE lines 69-73 (`_truncate_line()` function)
  - UPDATE callers to use `from tunacode.utils.ui.helpers import truncate`
**Estimated Time:** 3 minutes
**Risk:** medium
**Verification:** `uv run pytest tests/ -k web_fetch`

---

## Task 6: Remove Duplicate _truncate_line() from read_file.py
**Type:** duplication
**Files:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/read_file.py`
**Actions:**
  - DELETE lines 121-125 (`_truncate_line()` function)
  - UPDATE callers to use `from tunacode.utils.ui.helpers import truncate`
**Estimated Time:** 3 minutes
**Risk:** medium
**Verification:** `uv run pytest tests/ -k read_file`

---

## Task 7: Remove Duplicate _truncate_line() from grep.py
**Type:** duplication
**Files:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/grep.py`
**Actions:**
  - DELETE lines 114-118 (`_truncate_line()` function)
  - UPDATE callers to use `from tunacode.utils.ui.helpers import truncate`
**Estimated Time:** 3 minutes
**Risk:** medium
**Verification:** `uv run pytest tests/ -k grep`

---

## Task 8: Remove Duplicate _truncate_line() from bash.py
**Type:** duplication
**Files:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/bash.py`
**Actions:**
  - DELETE lines 91-95 (`_truncate_line()` function)
  - UPDATE callers to use `from tunacode.utils.ui.helpers import truncate`
**Estimated Time:** 3 minutes
**Risk:** medium
**Verification:** `uv run pytest tests/ -k bash`

---

## Task 9: Remove Duplicate _truncate_line() from list_dir.py
**Type:** duplication
**Files:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/list_dir.py`
**Actions:**
  - DELETE lines 88-92 (`_truncate_line()` function - note: has bug, doesn't subtract 3)
  - UPDATE callers to use `from tunacode.utils.ui.helpers import truncate`
**Estimated Time:** 3 minutes
**Risk:** medium
**Verification:** `uv run pytest tests/`

---

## Task 10: Remove Unused key_descriptions Functions
**Type:** dead-code
**Files:** `/home/tuna/tunacode/src/tunacode/configuration/key_descriptions.py`
**Actions:**
  - DELETE lines 212-214 (`get_key_description()`)
  - DELETE lines 217-226 (`get_service_type_for_api_key()`)
  - DELETE lines 229-234 (`get_categories()`)
  - DELETE lines 237-268 (`get_configuration_glossary()`)
**Estimated Time:** 5 minutes
**Risk:** low
**Verification:** `uv run ruff check src/tunacode/configuration/`

---

## Task 11: Remove ModelRequest Self-Assignment
**Type:** import
**Files:** `/home/tuna/tunacode/src/tunacode/types.py`
**Actions:**
  - DELETE line 22 (`ModelRequest = ModelRequest  # type: ignore[misc]`)
  - ADD `"ModelRequest"` to `__all__` if it should be re-exported
**Estimated Time:** 2 minutes
**Risk:** medium
**Verification:** `uv run pytest && uv run mypy src/tunacode/types.py`

---

## Task 12: Consolidate Duplicate Ignore Patterns (Complex)
**Type:** duplication
**Files:**
  - `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py`
  - `/home/tuna/tunacode/src/tunacode/utils/ui/file_filter.py`
  - `/home/tuna/tunacode/src/tunacode/utils/system/gitignore.py`
  - `/home/tuna/tunacode/src/tunacode/tools/glob.py`
**Actions:**
  - Keep canonical DEFAULT_IGNORE_PATTERNS in utils/system/gitignore.py
  - DELETE duplicate EXCLUDE_DIRS from grep_components/file_filter.py (lines 13-25)
  - UPDATE glob.py to import from canonical location
  - UPDATE utils/ui/file_filter.py to use canonical patterns
**Estimated Time:** 5+ minutes
**Risk:** medium
**Verification:** `uv run pytest && uv run ruff check .`

---

## Summary by Priority

### Priority 1: Safe Single-Line Deletions (Tasks 1, 2, 4)
- 3 tasks
- ~4 lines to delete
- Risk: LOW
- Can run in parallel branches

### Priority 2: Dead Code Removal (Tasks 3, 10)
- 2 tasks
- ~70 lines to delete
- Risk: LOW
- Independent changes

### Priority 3: Truncation Function Consolidation (Tasks 5-9)
- 5 tasks
- ~25 lines to delete (5 functions x 5 lines)
- Risk: MEDIUM
- Should batch these together

### Priority 4: Type/Import Cleanup (Task 11)
- 1 task
- ~1 line to change
- Risk: MEDIUM
- Needs type checking verification

### Priority 5: Pattern Consolidation (Task 12)
- 1 task
- ~50 lines affected
- Risk: MEDIUM
- Larger refactor, do last

---

## Quick Stats

| Category | Count | Lines to DELETE |
|----------|-------|-----------------|
| Unused imports | 3 | ~8 |
| Dead code | 3 | ~80 |
| Duplications | 6 | ~80 |
| **Total** | **12** | **~168** |

---

## Execution Order Recommendation

1. **First PR:** Tasks 1, 2, 4 (safest, fastest)
2. **Second PR:** Task 3 (dead code function)
3. **Third PR:** Tasks 5-9 batched (truncation consolidation)
4. **Fourth PR:** Task 10 (key_descriptions cleanup)
5. **Fifth PR:** Tasks 11, 12 (type/pattern cleanup)

All tasks are independent and can run in parallel branches.
