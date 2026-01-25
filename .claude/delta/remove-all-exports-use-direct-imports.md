---
title: Remove __all__ Exports, Use Direct Imports
link: remove-all-exports-use-direct-imports
type: delta
path: src/tunacode
depth: 0
seams: [A, M]
ontological_relations:
  - relates_to: [[tunacode]]
  - affects: [[module-structure, imports]]
tags:
  - refactoring
  - imports
  - exports
  - modern-python
created_at: 2025-01-25T02:07:10Z
updated_at: 2025-01-25T02:07:10Z
uuid: 41e2ff01-30d6-4d07-bb79-d0972c2cf2cc
---

## Summary

Remove all `__all__` exports from internal modules and convert to direct imports. Modern Python practice (2024-2025) is that `__all__` creates false public API and is only useful for wildcard imports (`from module import *`), which should be avoided entirely. Direct imports are clearer, more explicit, and work better with static analysis tools.

## Context

Current codebase has 262+ exports in `__all__` across many `__init__.py` files. Most are re-exports from submodules, creating "false public API" — things that look public but aren't part of any stable interface. This violates Gate 1 (Coupling and Cohesion) by exposing implementation details through re-export chains.

Example problem:
```python
# tunacode/core/__init__.py
from tunacode.tools.authorization import ToolHandler
__all__ = ["ToolHandler"]

# But actual usage:
from tunacode.tools.authorization.handler import ToolHandler  # Direct import
```

The `__all__` export suggests `ToolHandler` should be imported via `tunacode.core`, but nothing actually uses it that way.

## Root Cause

Historical overuse of `__init__.py` re-exports for "convenience" that became:
1. Unmaintainable — 262 exports to track
2. Misleading — exports aren't actually used via re-export paths
3. Brittle — static analysis can't detect true usage patterns

## Changes

**Phase 1: Remove `__all__` from internal modules**
- Delete `__all__` from all `__init__.py` files except true public API entry points
- Keep `__all__` only in: `tunacode/__init__.py` (if CLI exposes anything), `tunacode/types/__init__.py` (type exports)

**Phase 2: Convert to direct imports**
- Replace: `from tunacode.core import ToolHandler`
- With: `from tunacode.tools.authorization.handler import ToolHandler`
- Apply systematically across all modules

**Phase 3: Verify no breakage**
- Run tests: `uv run pytest`
- Run type checker: `uv run mypy src/`
- Run linter: `uv run ruff check --fix .`

## Behavioral Impact

**Internal code:** Import statements become longer but more explicit — developers see exactly where things come from.

**External users (if any):** Must use direct imports instead of `from tunacode.core import *`. This is a breaking change but aligns with modern best practices.

**Tooling:** Static analysis (mypy, ruff, vulture) becomes more accurate since imports are explicit.

## Related Cards

- [[quality-gates]] — Gate 1: Coupling and Cohesion, Gate 2: Dependency Direction
- [[claude-md]] — Modern Python practices section

## Implementation Checklist

- [ ] Phase 1: Remove `__all__` from internal `__init__.py` files
- [ ] Phase 2: Convert all internal imports to direct paths
- [ ] Phase 3: Run tests and fix any breakage
- [ ] Phase 4: Run static analysis and verify
- [ ] Phase 5: Update CLAUDE.md with new import conventions
