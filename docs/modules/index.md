---
title: Module Documentation Index
summary: Reading order and layer map for tunacode's architecture.
read_when: Starting work on the codebase or orienting after time away.
depends_on: []
feeds_into: []
---

# Module Documentation

TunaCode is structured in seven layers. Dependencies flow downward only.

```
ui              Textual TUI, widgets, renderers, screens
  |
core            Agent loop, compaction, session, logging, state machine
  |
tools           Tool implementations exposed to the LLM
  |
configuration   Settings, model registry, paths, limits, pricing
  |
infrastructure  Cache manager, invalidation strategies, named caches
  |
utils           Message conversion, token estimation, gitignore file listing
  |
types           Base aliases, callback protocols, canonical message model
```

## Reading Order

Start from the bottom if you need to understand the type system.
Start from the top if you need to change the UI.
Start from `core.md` if you need to understand how a user prompt becomes an LLM response.

| Layer           | Document                                 | Key concern                          |
|-----------------|------------------------------------------|--------------------------------------|
| types           | [types.md](types.md)                     | Aliases, protocols, canonical model  |
| utils           | [utils.md](utils.md)                     | Message adapter, token estimation    |
| infrastructure  | [infrastructure.md](infrastructure.md)   | Thread-safe caching                  |
| configuration   | [configuration.md](configuration.md)     | User config, model registry          |
| tools           | [tools.md](tools.md)                     | LLM-callable tool implementations    |
| core            | [core.md](core.md)                       | Agent loop, compaction, session      |
| ui              | [ui.md](ui.md)                           | Textual app, widgets, theming        |

## Root-Level Files

These files live directly under `src/tunacode/` and do not belong to any sub-package.

| File              | Purpose                                                         |
|-------------------|-----------------------------------------------------------------|
| `__init__.py`     | Package marker (empty).                                         |
| `constants.py`    | Global constants: version, color palettes, theme builders, tool names, UI sizing. |
| `exceptions.py`   | Exception hierarchy rooted at `TunaCodeError`. Every custom exception lives here. |
