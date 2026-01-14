# Research - Glob Tool Bottlenecks and Code Smells

**Date:** 2026-01-14
**Owner:** claude-agent
**Phase:** Research

## Goal

Map out the glob tool implementation to identify potential bottlenecks, code smells, and architectural issues.

## Findings

### File Locations

| File | Purpose |
|------|---------|
| `src/tunacode/tools/glob.py` | Main glob tool implementation |
| `src/tunacode/ui/renderers/tools/glob.py` | UI renderer for glob results |
| `src/tunacode/indexing/code_index.py` | CodeIndex singleton used for fast lookups |
| `src/tunacode/utils/system/ignore_patterns.py` | DEFAULT_EXCLUDE_DIRS definition |

### GitHub Permalinks

- [glob.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/067d8b8d121aeae83c69922e5409cc873d7b1a45/src/tunacode/tools/glob.py)
- [code_index.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/067d8b8d121aeae83c69922e5409cc873d7b1a45/src/tunacode/indexing/code_index.py)
- [ignore_patterns.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/067d8b8d121aeae83c69922e5409cc873d7b1a45/src/tunacode/utils/system/ignore_patterns.py)

---

## Critical Issues Found

### 1. DEAD CODE: `_gitignore_patterns` is Loaded but Never Used

**Severity:** High (code smell, wasted cycles)

**Location:** `glob.py:29, 155-174, 73-74`

```python
# Line 29: Module-level cache defined
_gitignore_patterns: set[str] | None = None

# Line 73-74: Patterns loaded on every call with use_gitignore=True
if use_gitignore:
    await _load_gitignore_patterns(root_path)

# Line 155-174: Load function populates the cache
async def _load_gitignore_patterns(root: Path) -> None:
    global _gitignore_patterns
    if _gitignore_patterns is not None:
        return
    _gitignore_patterns = set()
    # ... reads .gitignore, .ignore, .rgignore files
```

**Problem:** After loading, `_gitignore_patterns` is NEVER READ. The actual exclusion logic at line 66 uses `DEFAULT_EXCLUDE_DIRS` instead:

```python
all_exclude = set(DEFAULT_EXCLUDE_DIRS)
if exclude_dirs:
    all_exclude.update(exclude_dirs)
```

**Impact:**
- Wasted file I/O reading .gitignore files
- Global state pollution
- Misleading `use_gitignore` parameter that does nothing

**Fix:** Either implement gitignore filtering using the loaded patterns, or remove the dead code entirely.

---

### 2. RACE CONDITION: `_gitignore_patterns` Cache Initialization

**Severity:** Medium (thread-safety)

**Location:** `glob.py:158-161`

```python
async def _load_gitignore_patterns(root: Path) -> None:
    global _gitignore_patterns
    if _gitignore_patterns is not None:  # Check
        return
    _gitignore_patterns = set()  # Act - race window here
```

**Problem:** Classic check-then-act race condition. Two concurrent calls could:
1. Both see `_gitignore_patterns is None`
2. Both proceed to initialize
3. One overwrites the other's partial state

**Note:** Currently moot since the patterns are never used, but would be a real bug if the feature were completed.

---

### 3. DEPRECATED API: `asyncio.get_event_loop()`

**Severity:** Medium (deprecation warning in Python 3.10+)

**Location:** `glob.py:295, 312`

```python
# Line 295
return await asyncio.get_event_loop().run_in_executor(None, search_sync)

# Line 312
return await asyncio.get_event_loop().run_in_executor(None, sort_sync)
```

**Same pattern in other files:**
- `grep.py:111, 416`
- `startup.py:35`
- `app.py:210`

**Problem:** `asyncio.get_event_loop()` is deprecated in Python 3.10+. When called from a coroutine, should use:

```python
# Modern pattern (Python 3.7+)
await asyncio.to_thread(func)  # For default executor

# Or explicit running loop
loop = asyncio.get_running_loop()
await loop.run_in_executor(None, func)
```

---

### 4. MINOR: Blocking I/O on Main Thread

**Severity:** Low (microseconds, but violates async best practices)

**Location:** `glob.py:60-64`

```python
root_path = Path(directory).resolve()  # stat() call
if not root_path.exists():  # stat() call
    raise ModelRetry(...)
if not root_path.is_dir():  # stat() call
```

**Problem:** Path validation runs synchronously on the asyncio thread. For local filesystems this is sub-millisecond, but for network mounts or slow storage it could block the event loop.

**Similar pattern in:** `grep.py:101-105`

---

## Non-Issues (Previously Suspected)

### CodeIndex.build_index() Called Every Time

**Location:** `glob.py:111`

```python
index = CodeIndex.get_instance()
index.build_index()  # Called on every glob call
```

**Status:** NOT A PROBLEM

The `build_index()` implementation has an early-exit guard:

```python
# code_index.py:133-135
def build_index(self, force: bool = False) -> None:
    with self._lock:
        if self._indexed and not force:
            return  # O(1) early exit
```

After the first full index build, subsequent calls are essentially free (lock acquisition + boolean check).

### CodeIndex Thread Safety

**Status:** WELL IMPLEMENTED

- Singleton uses double-checked locking with `threading.RLock()`
- All mutable operations protected by instance-level `self._lock`
- `RLock` allows reentrant calls (e.g., `get_all_files()` calling `build_index()`)

---

## Code Smell Inventory

| Issue | Severity | Location | Type |
|-------|----------|----------|------|
| Dead gitignore code | High | `glob.py:29, 155-174` | Dead code |
| Race condition in cache | Medium | `glob.py:158-161` | Thread safety |
| Deprecated `get_event_loop()` | Medium | `glob.py:295, 312` | Deprecation |
| Blocking path validation | Low | `glob.py:60-64` | Async violation |
| `use_gitignore` param does nothing | High | `glob.py:42` | API lie |

---

## Architecture Notes

### Good Patterns

1. **Two-Path Strategy:** Index path for cached lookups, filesystem fallback for edge cases
2. **Brace Expansion:** `_expand_brace_pattern()` handles `*.{py,js,ts}` syntax correctly
3. **Sort Flexibility:** Multiple sort orders (modified, size, alphabetical, depth)
4. **MAX_RESULTS Limit:** Prevents runaway file lists (default 5000)
5. **Renderer Separation:** Clean separation between tool logic and UI rendering

### Data Flow

```
glob() entry
    |
    v
Path validation (blocking)
    |
    v
Build exclude set from DEFAULT_EXCLUDE_DIRS
    |
    v
_load_gitignore_patterns() <- DEAD CODE
    |
    v
[Index available?] --yes--> _glob_with_index()
    |                             |
    no                            v
    |                    CodeIndex.get_all_files()
    v                             |
_glob_filesystem()                v
    |                    Pattern matching
    v                             |
os.scandir() in executor          v
    |                    Early exit at max_results
    v
Pattern matching
    |
    v
Early exit at max_results
    |
    v
_sort_matches() in executor
    |
    v
_format_output()
```

---

## Test Coverage

| Test File | Coverage |
|-----------|----------|
| `tests/test_glob_grep_path_validation.py` | Path error handling |
| `tests/test_tool_conformance.py` | Tool registration |
| `tests/test_base_renderer.py` | Renderer registration |

**Missing Tests:**
- Brace pattern expansion
- Gitignore pattern matching (if implemented)
- Case sensitivity behavior
- Sort order correctness
- MAX_RESULTS truncation
- Index vs filesystem path selection

---

## Recommended Fixes

### Priority 1: Remove Dead Code

Delete `_gitignore_patterns`, `_load_gitignore_patterns()`, and the `use_gitignore` parameter unless implementing actual gitignore filtering.

### Priority 2: Fix Deprecation

Replace:
```python
await asyncio.get_event_loop().run_in_executor(None, func)
```
With:
```python
await asyncio.to_thread(func)
```

### Priority 3: Implement or Remove gitignore

If gitignore support is desired:
1. Use `pathspec` library for proper gitignore matching
2. Add thread-safe caching with proper locking
3. Actually use the patterns in `_glob_filesystem()`

If not needed:
1. Remove `use_gitignore` parameter
2. Remove `_gitignore_patterns` global
3. Remove `_load_gitignore_patterns()` function

---

## References

- `src/tunacode/tools/glob.py` - Main implementation
- `src/tunacode/indexing/code_index.py` - CodeIndex singleton
- `src/tunacode/utils/system/ignore_patterns.py` - DEFAULT_EXCLUDE_DIRS
- `tests/test_glob_grep_path_validation.py` - Existing tests
- Python asyncio docs: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_event_loop
