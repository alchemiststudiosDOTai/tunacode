This project uses a CLI ticket system for task management. Run `tk help` when you need to use it.

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
- **Mypy Status (2026-01-27):** 50 errors in 17 files. Gate 2 dependency direction work complete (PR #316). Use `git commit -n` to bypass pre-commit hooks if blocked. Do NOT introduce new type errors.
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

See `docs/agent-docs/card-format.md` for frontmatter spec and body sections when writing cards.

---

## Quality Gates

See `docs/agent-docs/quality-gates.md` for Gates 0-6 (shims, coupling, dependency direction, contracts, docs, indirection, exception paths).

---

## KB Directory

Maintain a `.claude/` directory with:

- Do not use `.claude/markdown`; the seven folders below are the source of truth.

- **metadata/** — dependency graphs, file classifications, error pattern database
- **code_index/** — function call graphs, type relationships, interface mappings
- **debug_history/** — error-solution pairs indexed by component/error type
- **patterns/** — canonical implementation examples for this codebase
- **cheatsheets/** — quick-reference guides per component with gotchas
- **qa/** — solved problems database with reasoning
- **delta/** — semantic changelogs explaining changes

Select the most semantically correct directory and create a card in it.

See `.claude/debug_history/continuous-learning.md` for bug/pattern/lesson entries.

---

We are currently in the middle of a large rewrite few test exist and documentation and that is okay. We will build the test and documentation as we go

We are in the middle of ripping out pydantic-ai. Expect some turbulence.

The new agent loop is https://github.com/alchemiststudios.ai/tinyAgent
