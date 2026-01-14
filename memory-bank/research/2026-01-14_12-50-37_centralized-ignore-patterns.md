# Research - Centralized Ignore Patterns for Tools

**Date:** 2026-01-14
**Owner:** Claude
**Phase:** Research

## Goal

Design a centralized, standardized approach for gitignore-aware file filtering across all tools. The dead `_gitignore_patterns` code in glob.py was removed, but the concept is valid - tools SHOULD respect .gitignore and common exclusions.

## Findings

### Current State

**Primary centralized source exists:**
- `src/tunacode/utils/system/ignore_patterns.py` - 50+ patterns, the canonical list

**Three tools consume it:**

| Tool | Import | Mechanism |
|------|--------|-----------|
| `glob.py` | `DEFAULT_EXCLUDE_DIRS` | Fast set membership (directory names only) |
| `list_dir.py` | `DEFAULT_IGNORE_PATTERNS` + `is_ignored()` | Full pattern matching |
| `grep.py` (via `file_filter.py`) | `DEFAULT_EXCLUDE_DIRS` | Fast set membership |

**Duplication problem:**
- `src/tunacode/indexing/constants.py` has separate `IGNORE_DIRS` set (~35 dirs)
- Nearly identical to DEFAULT_EXCLUDE_DIRS but maintained separately
- Violates DRY principle

**No tool reads actual .gitignore:**
- Only `src/tunacode/utils/ui/file_filter.py` uses `pathspec` library
- Only used for UI autocomplete, not tools
- Tools ignore project-specific .gitignore files entirely

### Key Patterns in ignore_patterns.py

```python
DEFAULT_IGNORE_PATTERNS = (
    ".git/", ".hg/", ".svn/",           # VCS
    "__pycache__/", ".pytest_cache/",   # Python cache
    "node_modules/", "bower_components/", # JS deps
    ".venv/", "venv/", "env/",          # Virtual envs
    "build/", "dist/", "_build/",       # Build outputs
    ".idea/", ".vscode/",               # IDE
    # ... ~50 total patterns
)

DEFAULT_EXCLUDE_DIRS = frozenset(...)   # Derived, dirs only
```

### Industry Best Practices (from ripgrep, fd, ag)

1. **Use pathspec.GitIgnoreSpec** - handles Git's actual behavior, not just documented
2. **Load patterns during traversal** - read .gitignore as you descend directories
3. **Cache compiled PathSpec objects** - key by (directory, mtime)
4. **Skip excluded dirs entirely** - don't recurse, massive perf win
5. **Provide override flags** - ripgrep uses `-u/-uu/-uuu` for progressive disable

## Proposed Design

### Tool Classification: Discovery vs Direct Access

**Discovery tools** - SHOULD filter by default:
| Tool | Why |
|------|-----|
| `glob` | Finding files by pattern - don't want 10k results from node_modules |
| `list_dir` | Listing contents - noise reduction |
| `grep` | Searching content - same as ripgrep behavior |

**Direct access tools** - should NOT filter:
| Tool | Why |
|------|-----|
| `read_file` | User explicitly requested this file |
| `write_file` | User explicitly wants to write here |
| `update_file` | User explicitly wants to edit this |

The principle: explicit file paths are intentional. Pattern-based discovery needs filtering.

This matches ripgrep's model:
- `rg "foo"` respects .gitignore (discovery)
- `cat .venv/foo.py` works fine (direct access)

### Location

Create `src/tunacode/tools/ignore.py` - tools-specific ignore handling.

Why tools/ not utils/:
- Tools have specific requirements (perf, per-operation loading)
- Clean separation from UI autocomplete use case
- Tools can share without circular imports

### Architecture

```
src/tunacode/tools/ignore.py
├── IgnoreManager (class)
│   ├── __init__(root: Path, respect_gitignore: bool = True)
│   ├── should_ignore(path: Path) -> bool
│   ├── filter_paths(paths: Iterable[Path]) -> Iterator[Path]
│   └── _load_gitignore(directory: Path) -> PathSpec | None
│
├── DEFAULT_PATTERNS (from utils/system/ignore_patterns.py)
├── get_ignore_manager(root: Path) -> IgnoreManager (cached factory)
└── clear_cache() -> None
```

### Key Design Decisions

**1. PathSpec for gitignore parsing:**
```python
import pathspec

spec = pathspec.GitIgnoreSpec.from_lines(patterns)
```

**2. Hierarchical loading (like ripgrep):**
- Load root .gitignore first
- As traversal descends, load child .gitignore files
- Child patterns take precedence

**3. Caching strategy:**
```python
_cache: dict[Path, tuple[float, IgnoreManager]] = {}

def get_ignore_manager(root: Path) -> IgnoreManager:
    gitignore = root / ".gitignore"
    mtime = gitignore.stat().st_mtime if gitignore.exists() else 0

    if root in _cache and _cache[root][0] == mtime:
        return _cache[root][1]

    manager = IgnoreManager(root)
    _cache[root] = (mtime, manager)
    return manager
```

**4. Two-tier filtering (like current split):**
- Fast path: Directory name in DEFAULT_EXCLUDE_DIRS -> skip immediately
- Slow path: Full PathSpec match for everything else

**5. Opt-in gitignore:**
```python
async def glob_files(
    pattern: str,
    root: str,
    respect_gitignore: bool = True,  # NEW: default on
    exclude_dirs: list[str] | None = None,
) -> list[str]:
```

### Migration Plan

**Phase 1: Create ignore.py**
- New IgnoreManager class
- Re-export DEFAULT_EXCLUDE_DIRS, DEFAULT_IGNORE_PATTERNS
- Add pathspec-based gitignore loading

**Phase 2: Update discovery tools only**
- glob.py: Use IgnoreManager
- list_dir.py: Use IgnoreManager
- grep.py/file_filter.py: Use IgnoreManager

**NOT touched:** read_file, write_file, update_file (direct access tools)

**Phase 3: Consolidate duplicates**
- Remove indexing/constants.py IGNORE_DIRS
- Have indexing import from tools/ignore.py

**Phase 4: Add override flags**
- `--no-ignore` flag to bypass all filtering
- Progressive disable like ripgrep

## Knowledge Gaps

- Performance impact of pathspec vs current fnmatch
- Whether to cache per-file results or just PathSpec objects
- Handling nested .gitignore in subdirectories (may be complex)

## Anti-Patterns to Avoid

From the dead code lesson:
- Don't load patterns that nothing consumes
- Trace data flow: load -> store -> read -> use
- If `respect_gitignore` param exists, it must actually change behavior

## References

- `src/tunacode/utils/system/ignore_patterns.py` - Current patterns
- `src/tunacode/utils/ui/file_filter.py` - Only pathspec user
- `src/tunacode/indexing/constants.py` - Duplicate to consolidate
- [pathspec docs](https://pypi.org/project/pathspec/)
- [ripgrep GUIDE.md](https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md)
