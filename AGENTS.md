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

**UI Design Rule:** Always call the next neXTSTEP-ui skill for any UI changes.

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

## Claude-Specific Repository Optimization

Maintain .claude/ with the following structure:

.claude/
├── metadata/        # Component summaries, module overviews, architecture docs
├── debug_history/   # Debugging timelines, incident logs, troubleshooting sessions
├── qa/              # Q&A, learning notes, clarifications, explanations
├── code_index/      # File/module references, code organization maps
├── patterns/        # Reusable fixes, design motifs, recurring solutions
├── cheatsheets/     # Quick references, command lists, how-tos
├── delta/           # API & behavior change logs with reasoning
├── memory_anchors/  # Core concepts, foundational knowledge tracked by UUID
├── plans/           # Implementation plans, roadmaps
└── other/           # Scratch notes, uncategorized content
Rules:

- **Metadata** → component summaries, architecture decisions, module overviews
- **Debug History** → log all sessions with error→solution pairs and context
- **QA** → solved queries indexed by file/component/error type
- **Code Index** → file references, call graphs, type relationships
- **Patterns** → canonical patterns + empirical usage with reliability metrics
- **Cheatsheets** → quick references and command lists
- **Delta** → record API/behavior shifts with reasoning after each PR
- **Memory Anchors** → core concepts tracked by UUID for stable references

kb-claude init – create the .claude/ layout in a repo.
kb-claude new "Title" – guided prompt for new entries; handles tags, relations, timestamps, UUIDs, and file placement.
kb-claude search keyword – case-insensitive search across titles, tags, relations, and body text.
kb-claude validate [--strict] – parse every entry, confirm required metadata, and flag inconsistencies (e.g., slug mismatch).
kb-claude manifest – rebuild .claude/manifest.md, a table summarizing every document.
kb-claude link source target – insert reciprocal relations between two slugs.

If kb-claude CLI is not installed, write the md files to the .claude/ folder manually following the entry format.

We are currently in the middle of a large rewrite few test exist and documentation and that is okay. We will build the test and documentation as we go.
