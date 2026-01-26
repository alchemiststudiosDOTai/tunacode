# Tunacode Dependency Map

## Purpose

Map the current dependency flow using grimp so architecture constraints are visible
and enforceable.

## Method (grimp)

Built with:

```
uv run --with grimp python
```

Import graph source: `tunacode` package.

## Layer Model (enforced)

```
ui    -> core -> tools -> utils/types
```

## Flow Direction (start/end)
Start: `ui` (entry points: `tunacode.ui.app`, `tunacode.ui.main`, `tunacode.ui.headless`).
End: `utils/types` (shared primitives and helpers: `tunacode.types.*`, `tunacode.utils.*`).

Dependency direction is always downward (imports only flow down):

```
ui     (user interaction, orchestration)
  ↓
core   (agent logic, state, orchestration)
  ↓
tools  (side-effects, system access)
  ↓
utils/types (pure helpers + shared dataclasses)
```

Runtime flow aligns with this direction:

1. UI receives input and calls into core (request orchestration).
2. Core selects tools and executes them (tool dispatcher).
3. Tools rely on utils/types for parsing, safety, and shared structures.
4. Results flow back up as *data*, not imports (core returns to UI).

Key rule: return values can travel upward, imports cannot.

Rules encoded in `tests/architecture/test_layer_dependencies.py` and
`tests/architecture/test_import_order.py`:

- core cannot import ui
- tools cannot import ui or core
- utils/types cannot import ui, core, or tools
- ui may import core/tools/utils/types
- first-party imports are ordered by layer (shared -> tools -> core -> ui)

## Module Counts (by layer)

- ui: 44 modules
- core: 37 modules
- tools: 31 modules
- utils: 18 modules
- types: 8 modules
- total (tunacode): 160 modules

## Direct Import Flow (counts)

Counts below represent direct imports observed via grimp across modules in each
layer.

- ui -> ui: 82
- ui -> core: 9
- ui -> tools: 3
- ui -> utils: 10
- ui -> types: 1

- core -> core: 75
- core -> tools: 17
- core -> utils: 13
- core -> types: 7

- tools -> tools: 45
- tools -> utils: 4

- utils -> utils: 15
- utils -> types: 2

- types -> types: 9

## Current Violations (by policy)

None.

## Notes

- This map is a snapshot; re-run after refactors or new tools.
