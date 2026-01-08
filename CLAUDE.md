## Tunacode

This project is tunacode, much like you! It's a TUI code agent that can be used to code and debug code or general agentic tasks.

src/tunacode/ui is the TUI interface that is used to interact with the user.
src/tunacode/core is the core agent that is used to code and debug code or general agentic tasks.
src/tunacode/tools is the tools that are used to code and debug code or general agentic tasks.

Tests are located in the `tests/` directory covering tool decorators, tool conformance, compaction, and tool retry logic.

## Design Philosophy

The TUI design is heavily inspired by the classic **NeXTSTEP** user interface. This choice reflects a commitment to **"the next step of uniformity"**.

- **Uniformity:** The interface should provide a consistent and predictable experience across all interactions.
- **User Informed:** A core tenet is to keep the user constantly informed of the agent's state, actions, and reasoning. No "magic" should happen in the background without visual feedback.
- **Aesthetic:** The look should be professional, clean, and retro-modern, echoing the clarity and object-oriented nature of the NeXTSTEP environment.

**UI Design Rule:** Always call the neXTSTEP-ui skill for any UI changes.

**Skill Location:** `.claude/skills/neXTSTEP-ui/`

- `SKILL.md` - Design philosophy and guidelines
- `NeXTSTEP_User_Interface_Guidelines_Release_3_Nov93.pdf` - Original 198-page reference
- `read_pdf.py` - Chunked PDF reader (`uv run python read_pdf.py --help`)

## Workflow Rules

- Never begin coding until the objective is **explicitly defined**. If unclear, ask questions or use best practices.
- Always use `.venv` and `uv` for package management.
- Small, focused diffs only. Commit frequently.

## Code Style & Typing

- Enforce `ruff check --fix .` before PRs.
- Use explicit typing. `cast(...)` and `assert ...` are OK.
- `# type: ignore` only with strong justification.
- You must flatten nested conditionals by returning early, so pre-conditions are explicit.
- If it is never executed, remove it. You MUST make sure what we remove has been committed before in case we need to rollback.
- Normalize symmetries: you must make identical things look identical and different things look different for faster pattern-spotting.
- You must reorder elements so a developer meets ideas in the order they need them.
- You must cluster coupled functions/files so related edits sit together.
- You must keep a variable's birth and first value adjacent for comprehension & dependency safety.
- Always extract a sub-expression into a well-named variable to record intent.
- Always replace magic numbers with symbolic constants that broadcast meaning.
- Never use magic literals; symbolic constants are preferred.
- ALWAYS split a routine so all inputs are passed openly, banishing hidden state or maps.

## Error Handling

- Fail fast, fail loud. No silent fallbacks. This is one of the most important rules to follow.
- Minimize branching: every `if`/`try` must be justified.

## Dependencies

- Avoid new core dependencies. Tiny deps OK if widely reused.
- Run tests with: `uv run pytest`.

## Scope & Maintenance

- Backward compatibility only if low maintenance cost.
- Delete dead code (never guard it).
- Always run `ruff .`.
- Use `git commit -n` if pre-commit hooks block rollback.

---

## Card Format

Bugs, docs, and module cards all use this unified structure.

### Frontmatter

```yaml
---
title: <Short human-readable title>
link: <stable-slug-for-links>
type: <delta | doc | module>
path: <relative path, for modules/docs>
depth: <nesting level, 0 = root>
seams: <[A] architecture | [E] entry | [M] module | [S] state | [D] data>
ontological_relations:
  - relates_to: [[<primary-system-or-area>]]
  - affects: [[<component-or-module>]]
  - fixes: [[<bug-or-failure-mode>]] # for deltas
tags:
  - <area>
  - <symptom>
  - <tool-or-feature>
created_at: <ISO-8601 timestamp>
updated_at: <ISO-8601 timestamp>
uuid: <generated-uuid>
---
```

### Body Sections

- **Summary** - One paragraph, what and why, readable in a year
- **Context** - Optional, where it lives, how it surfaced
- **Root Cause** - For bugs: mechanism, not blame
- **Changes** - Bullet list of concrete changes
- **Behavioral Impact** - What users notice, what didn't change
- **Related Cards** - `[[links]]` to other cards

### Bug Rules

- Fix it, we don't care who caused it
- Document: what? where? when? why?
- No shims, fix at root
- Document how we missed it and how to prevent it

---

## Quality Gates

These are another layer to prevent slop, not pre-commit hooks.

### Gate 0: No Shims

Never use shims. It is a mortal sin to allow shims.

Instead, fix the interface. In some cases, it may be better to create a new interface for examples:

- If 19 files use an interface and our new work has a problem with it, the interface is not the problem
- If only two files use the interface and it's giving us issues, write it correctly
- The interface must be written in proper idiomatic way
- 99% of the time we don't need a unique interface; if a unique situation calls for one, it must be strongly justified with anchor comments

### Gate 1: Coupling and Cohesion (Constantine)

**High cohesion** = everything in a module serves one purpose
**Low coupling** = modules don't need to know each other's internals

Before writing or modifying code, answer:

- **What single responsibility does this module have?** If you can't state it in one sentence, the module is doing too much. Split until each piece has one job.
- **Can I change this module without changing others?** If no, you have a coupling problem.
- **Dependencies should flow one direction:** ui → core → tools → utils/types. Never reach backward (core importing from ui).
- **How many dots?** `state_manager.session.tool_handler._policy.rules[0].name = "allow"` coupling points. Each `.` is a place where changes can break you. More than 2 dots = smell; refactor to hide the chain.
- **What does this module hide?** "Every module hides a design decision that could change." If a module exposes its internals, it will churn when those internals change. UI hides Textual, core hides agent orchestration, tools hide system access.

**Example:** If a file gets touched more than 5 times in a month, it has a cohesion problem. Stop adding to it. Split it.

**Wrong:**

```
src/tunacode/ui/main.py  →  Textual UI + agent orchestration + tool execution + persistence
```

**Right:**

```
src/tunacode/ui/main.py              →  Textual UI concerns only
src/tunacode/core/agents/main.py     →  agent orchestration only
src/tunacode/tools/*.py              →  tool execution only
src/tunacode/core/state.py           →  persistence and session state only
```

### Gate 2: Dependency Direction (Martin)

Dependencies flow inward, never backward.

```
ui → core → tools → utils/types
  ↓
infrastructure (filesystem, shell, network)
```

**Rules:**

- Inner layers know nothing about outer layers
  - core/ never imports from ui/
  - tools/ never imports from ui/
  - utils/ and types/ import from nothing
- Infrastructure is a plugin
  - Filesystem, shell, network = details
  - Core logic doesn't know or care which system provider
- Depend on abstractions, not concretions
  - Pass interfaces, not implementations
  - Makes testing trivial, swapping backends trivial

**Example:** If core needs UI state, you're violating the boundary. Extract what you need and pass it as a plain argument.

**Wrong:**

```python
from tunacode.ui.app import TunaCodeApp

def run_agent(app: TunaCodeApp):
    app.notify_status("Running")  # core knows about UI layer
```

**Right:**

```python
from collections.abc import Callable

def run_agent(notify_status: Callable[[str], None]):
    notify_status("Running")  # core only knows about a callable
```

### Gate 3: Design by Contract (Meyer)

Every function is a contract with three parts:

- **Preconditions** - what must be true before calling
- **Postconditions** - what will be true after
- **Invariants** - what's always true

**Rules:**

- Caller guarantees preconditions - don't check inside what should be guaranteed outside
- Function guarantees postconditions - if it returns, the promise is kept
- Fail immediately if contract violated - no limping along with bad state

**Example:** If a tool expects a valid directory, don't silently return an empty result. That's a contract violation - raise.

**Wrong:**

```python
def list_dir(directory: str) -> str | None:
    if not Path(directory).exists():
        return None  # silent failure, caller doesn't know why
    return _render_dir(Path(directory))
```

**Right:**

```python
def list_dir(directory: str) -> str:
    """Precondition: directory exists and is a directory."""
    path = Path(directory)
    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")
    return _render_dir(path)
```

### Gate 4: Documentation is Code (Knuth)

Docs and code are one system. If they diverge, the docs are lying.

**Rules:**

- **Code changes = doc changes**
  - If you change a module's behavior, update its codebase-map doc in the same PR
  - If you add a tool, update docs/codebase-map/modules/tools-overview.md
  - If you add a UI component, update docs/codebase-map/modules/ui-overview.md
- **Docs describe the system that exists, not the system you wish existed**
  - No aspirational docs ("we plan to...")
  - No stale docs ("this used to...")
  - Only current truth
- **The /docs/codebase-map folder mirrors src/tunacode**
  - Structure matches structure
  - When code moves, docs move
  - When code dies, docs die

**Example:** If you delete src/tunacode/tools/grep.py, you must also remove its entry from docs/codebase-map/modules/tools-overview.md in the same commit.

**Wrong:**

```
PR #263: "chore: remove unused grep tool"
  - deletes src/tunacode/tools/grep.py
  - leaves docs/codebase-map/modules/tools-overview.md still referencing it
```

**Right:**

```
PR #263: "chore: remove unused grep tool"
  - deletes src/tunacode/tools/grep.py
  - updates docs/codebase-map/modules/tools-overview.md to remove grep section
  - single atomic commit, code and docs together
```

---

## KB Directory

Maintain a `.claude/` directory with:

- **metadata/** — dependency graphs, file classifications, error pattern database
- **code_index/** — function call graphs, type relationships, interface mappings
- **debug_history/** — error-solution pairs indexed by component/error type
- **patterns/** — canonical implementation examples for this codebase
- **cheatsheets/** — quick-reference guides per component with gotchas
- **qa/** — solved problems database with reasoning
- **delta/** — semantic changelogs explaining changes

Select the most semantically correct directory and create a card in it.

### Continuous Learning

Dump bugs, smells, issues here as you encounter them. Raw is fine. A skill will organize this into proper kb entries later.

Format: `[date] [type] description`

---

We are currently in the middle of a large rewrite few test exist and documentation and that is okay. We will build the test and documentation as we go
