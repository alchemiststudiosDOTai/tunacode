# Duplication and Pattern Analysis Report

Generated: 2025-12-14

## Critical Duplications Found

### 1. Duplicate FileFilter Class

**Location 1:** `/home/tuna/tunacode/src/tunacode/utils/ui/file_filter.py`
- Lines: 31-136
- Last modified: 2025-12-05 (refactor clean up AI slop)
- Uses: pathspec library for gitignore-aware filtering
- Purpose: File autocomplete in TUI

**Location 2:** `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py`
- Lines: 28-94
- Last modified: 2025-12-06 (grep decomposition)
- Uses: fnmatch for fast globbing
- Purpose: Grep tool file filtering

**Evidence:**
Both classes named `FileFilter` with different implementations:
- utils/ui version: Uses pathspec, has `is_ignored()`, `complete()` methods
- grep_components version: Uses fnmatch, has `fast_glob()` static method

**Suggested Action:**
DELETE `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py` (94 lines)
- The grep tool should use the more mature pathspec-based FileFilter from utils/ui
- The grep_components version is a simpler reimplementation with overlapping EXCLUDE_DIRS

---

### 2. Duplicate Gitignore Pattern Handling

**Location 1:** `/home/tuna/tunacode/src/tunacode/utils/system/gitignore.py`
- Lines: 1-156
- Last modified: 2025-12-08
- Has: `_load_gitignore_patterns()`, `_is_ignored()`, `list_cwd()`, DEFAULT_IGNORE_PATTERNS

**Location 2:** `/home/tuna/tunacode/src/tunacode/utils/ui/file_filter.py`
- Lines: 10-28, 38-43
- Has: DEFAULT_IGNORES list, gitignore reading in `_build_spec()`

**Evidence:**
Three overlapping ignore pattern lists:
```python
# utils/system/gitignore.py
DEFAULT_IGNORE_PATTERNS = {"node_modules/", "env/", "venv/", ".git/", "build/", "dist/", "__pycache__/", ...}

# utils/ui/file_filter.py
DEFAULT_IGNORES = [".git/", ".venv/", "venv/", "env/", "node_modules/", "__pycache__/", ...]

# tools/grep_components/file_filter.py
EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ...}
```

**Suggested Action:**
DELETE the ignore pattern lists in `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py` (lines 13-25)
DELETE the ignore pattern list in `/home/tuna/tunacode/src/tunacode/utils/ui/file_filter.py` (lines 10-28)
- Keep only the canonical DEFAULT_IGNORE_PATTERNS in utils/system/gitignore.py

---

### 3. Duplicate _truncate_line() Functions

**Multiple identical implementations across 5 files:**

**Location 1:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/web_fetch.py`
- Lines: 69-73
```python
def _truncate_line(line: str) -> str:
    """Truncate a single line if too wide."""
    if len(line) > MAX_PANEL_LINE_WIDTH:
        return line[: MAX_PANEL_LINE_WIDTH - 3] + "..."
    return line
```

**Location 2:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/read_file.py`
- Lines: 121-125
- Identical to Location 1

**Location 3:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/grep.py`
- Lines: 114-118
- Identical to Location 1

**Location 4:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/bash.py`
- Lines: 91-95
- Identical to Location 1

**Location 5:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/list_dir.py`
- Lines: 88-92
- Nearly identical but uses `MAX_PANEL_LINE_WIDTH` without subtracting 3:
```python
def _truncate_line(line: str) -> str:
    """Truncate a single line if too wide."""
    if len(line) > MAX_PANEL_LINE_WIDTH:
        return line[:MAX_PANEL_LINE_WIDTH] + "..."  # BUG: should be MAX_PANEL_LINE_WIDTH - 3
    return line
```

**Suggested Action:**
DELETE `_truncate_line()` from these 5 files:
- `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/web_fetch.py` (lines 69-73)
- `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/read_file.py` (lines 121-125)
- `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/grep.py` (lines 114-118)
- `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/bash.py` (lines 91-95)
- `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/list_dir.py` (lines 88-92)

Note: `/home/tuna/tunacode/src/tunacode/utils/ui/helpers.py` already has a `truncate()` function at line 19 that could replace these.

---

### 4. Duplicate Truncation Logic for Content

**Multiple similar implementations:**

**Location 1:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/web_fetch.py`
- Lines: 76-84
- Function: `_truncate_content(content: str) -> tuple[str, int, int]`

**Location 2:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/bash.py`
- Lines: 98-106
- Function: `_truncate_output(output: str) -> tuple[str, int, int]`

**Location 3:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/list_dir.py`
- Lines: 95-101
- Function: `_truncate_tree(content: str) -> tuple[str, int, int]`

**Location 4:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/update_file.py`
- Lines: 91+ (needs verification)
- Function: `_truncate_diff(diff: str) -> tuple[str, int, int]`

**Evidence:**
All follow same pattern:
1. Split content into lines
2. Check if total lines exceed MAX_PANEL_LINES
3. Return tuple of (truncated_content, shown_lines, total_lines)
4. Call _truncate_line() on each line

**Suggested Action:**
DELETE these 4 truncation functions:
- `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/web_fetch.py` `_truncate_content()` (lines 76-84)
- `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/bash.py` `_truncate_output()` (lines 98-106)
- `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/list_dir.py` `_truncate_tree()` (lines 95-101)
- `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/update_file.py` `_truncate_diff()` (lines 91+)

---

### 5. Duplicate MAX_RESULTS / MAX_GLOB Constants

**Location 1:** `/home/tuna/tunacode/src/tunacode/tools/glob.py`
- Line: 13
- `MAX_RESULTS = 5000`

**Location 2:** `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py`
- Line: 11
- `MAX_GLOB = 5_000  # Hard cap - protects memory & tokens`

**Evidence:**
Same value (5000), same purpose (limit file results), different names.

**Suggested Action:**
DELETE `MAX_GLOB = 5_000` from `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py` (line 11)
- Both should use a constant from constants.py or reference glob.py's MAX_RESULTS

---

### 6. Duplicate EXCLUDE_DIRS Sets

**Location 1:** `/home/tuna/tunacode/src/tunacode/tools/glob.py`
- Lines: 14-30
```python
EXCLUDE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".tox",
    "target", ".next", ".nuxt", "coverage", ".coverage",
}
```

**Location 2:** `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py`
- Lines: 13-25
```python
EXCLUDE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".tox", "target",
}
```

**Evidence:**
Nearly identical sets with glob.py having a few more entries (.next, .nuxt, coverage, .coverage).

**Suggested Action:**
DELETE `EXCLUDE_DIRS` from `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py` (lines 13-25)
- Import from glob.py or constants.py instead

---

### 7. Duplicate GLOB_BATCH Constant (Unused)

**Location:** `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py`
- Line: 12
- `GLOB_BATCH = 500  # Streaming batch size`

**Evidence:**
Searched entire file - this constant is defined but never used in the code.

**Suggested Action:**
DELETE `GLOB_BATCH = 500` from `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py` (line 12)
- Dead code, no references found

---

### 8. Duplicate _truncate_path() Function

**Location:** `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/glob.py`
- Lines: 105+
- Function: `_truncate_path(path: str) -> str`

**Evidence:**
This is functionally similar to the `_truncate_line()` duplicates but specialized for paths.

**Suggested Action:**
DELETE `_truncate_path()` from `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/glob.py`
- Should use the common truncate utility instead

---

### 9. Duplicate Tool Output Formatting

**Location 1:** `/home/tuna/tunacode/src/tunacode/tools/bash.py`
- Function: `_format_output(command, exit_code, stdout, stderr, cwd)` (line found in grep)

**Location 2:** `/home/tuna/tunacode/src/tunacode/tools/glob.py`
- Function: `_format_output(pattern, matches, max_results, source)` (line found in grep)

**Evidence:**
Different signatures but both named `_format_output` and create formatted string output for tools.

**Note:** These may not be true duplicates due to different purposes, but the naming collision suggests refactoring opportunity. Monitor for deletion if they share common formatting logic.

---

## Summary Statistics

### Duplications by Category

1. File Filtering Logic: 3 implementations (FileFilter class + gitignore pattern lists)
2. Line Truncation: 5 identical `_truncate_line()` functions
3. Content Truncation: 4 similar truncation functions
4. Constants: 3 duplicated constants (MAX_RESULTS/MAX_GLOB, EXCLUDE_DIRS, GLOB_BATCH)
5. Format Functions: 2 `_format_output()` functions (naming collision)

### Total Lines to Delete

Estimated: 250-300 lines of duplicate code

### Files with Most Duplications

1. `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py` - Entire file (94 lines) is duplicate
2. `/home/tuna/tunacode/src/tunacode/ui/renderers/tools/` - Multiple truncation duplicates across 5 files
3. `/home/tuna/tunacode/src/tunacode/utils/ui/file_filter.py` - Overlapping ignore patterns

---

## Deprecated Patterns

No deprecated callback patterns or old async patterns found. The codebase uses modern async/await consistently.

---

## Recommendations

Priority 1 (Delete immediately):
1. Delete `/home/tuna/tunacode/src/tunacode/tools/grep_components/file_filter.py` entirely
2. Delete all 5 `_truncate_line()` functions
3. Delete unused GLOB_BATCH constant

Priority 2 (Consolidate):
1. Consolidate ignore pattern lists into single source
2. Consolidate content truncation functions

Priority 3 (Monitor):
1. Review `_format_output()` naming collision
