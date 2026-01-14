---
title: Semantically Dead Code - Loaded But Never Read
link: semantically-dead-code
type: qa
path: qa/
depth: 1
seams: [M]
ontological_relations:
  - relates_to: [[dead-code-detection]]
  - affects: [[glob-tool]]
  - fixes: [[wasted-cycles, api-lies]]
tags:
  - dead-code
  - static-analysis
  - antipattern
  - glob
created_at: 2026-01-14T12:45:00Z
updated_at: 2026-01-14T12:45:00Z
uuid: 953376a5-10a7-4d6b-8aee-c8468b4d267d
---

## Problem

`glob.py` had a `use_gitignore` parameter that did nothing. The function `_load_gitignore_patterns()` was called, populated a global `_gitignore_patterns`, but that global was never read. The actual filtering used `DEFAULT_EXCLUDE_DIRS` instead.

Static analysis tools (Vulture) reported "no dead code" because the function WAS called and the variable WAS assigned.

## Root Cause

**Syntactic vs semantic dead code.** Static analyzers check "is this symbol referenced?" not "is the result consumed?"

The code path was:
```
use_gitignore=True
  -> _load_gitignore_patterns() called
    -> _gitignore_patterns populated
      -> NEVER READ ANYWHERE
```

All 7 references to `_gitignore_patterns` were writes, zero reads.

## Why It Matters

1. **Wasted I/O** - Reading .gitignore files on every glob call for nothing
2. **API lie** - `use_gitignore` parameter implied functionality that didn't exist
3. **Global state pollution** - Module-level mutable state with no consumer
4. **Race condition** - Cache init had check-then-act bug (moot since never used)

## Detection Method

Static analysis fails. Manual review required:

```bash
# Find all references
grep -n "_gitignore_patterns" src/tunacode/tools/glob.py

# Check for READS (not just assignments)
# Writes: =, .add(), .update()
# Reads: in, if X, for x in X, return X, func(X)
```

If all references are writes, it's dead.

## Prevention

Before shipping code that "loads X":

1. **Grep for reads of X** - Not just references, actual consumption
2. **Trace parameter data flow** - If `use_foo` controls behavior, prove it changes output
3. **Question unused returns** - If a function populates state but nothing reads it, why?

## The Fix

Removed 37 lines:
- `_gitignore_patterns` global
- `_load_gitignore_patterns()` function
- `use_gitignore` parameter
- The call site

Also fixed deprecated `asyncio.get_event_loop()` -> `asyncio.to_thread()`.

## Related

- `memory-bank/research/2026-01-14_12-27-29_glob-tool-bottlenecks.md` - Original research
- `.claude/skills/dead-code-detector/` - Vulture-based detection (syntactic only)
