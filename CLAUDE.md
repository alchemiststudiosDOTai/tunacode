# Instruction

Your task is to optimize and extend this repository following explicit coding, testing, and documentation workflows.

Example of ReAct loop:

Reason: I need to know if a golden baseline test exists for this feature.

Act: Search the tests/ directory for existing coverage.

## You MUST comply with the rules below. You will be penalized if you deviate. Answer in a natural, human-like manner. you MUST keep.claude updated as instructed below. You will be punished for now keeping .claude kb in synch. You MUST always follow the ReAct Pattern (reasoning + acting) when solving tasks, explicitly alternating between reasoning steps and concrete actions

## Workflow Rules

- Never begin coding until the objective is **explicitly defined**. If unclear, ask questions or use best practices.
- Always use `.venv` and `uv` for package management.
- Small, focused diffs only. Commit frequently.
- As needed, use the MCP tool get_code_context_exa:
  - When you need code examples, docs, or implementation patterns from open source projects, use this tool.
  - Parameters:
    - query (required): Be specific—state the language, library, function, or concept (e.g., "React useState examples", "Python pandas filter").
    - tokensNum (optional): Use 'dynamic' (default) for best results, or specify a number (1000–50000) for more/less detail.
  - RULE: You MUST use this tool for any query containing "exa" or code-related requests.

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

- Fail fast, fail loud. No silent fallbacks.
- Minimize branching: every `if`/`try` must be justified.

## Dependencies

- Avoid new core dependencies. Tiny deps OK if widely reused.

## Testing (TDD Red → Green → Blue)

1. If a test doesn’t exist, create a **golden baseline test first**.
2. Add a failing test for the new feature.
3. Implement until tests pass.
4. Refactor cleanly.

- Run with: `hatch run test`.

## Documentation

- Keep concise and actionable.
- Update when behavior changes.
- Avoid duplication.

## Scope & Maintenance

- Backward compatibility only if low maintenance cost.
- Delete dead code (never guard it).
- Always run `ruff .`.
- Use `git commit -n` if pre-commit hooks block rollback.

---

## Claude-Specific Repository Optimization

Maintain .claude/ with the following structure:

claude/
├── metadata/ # Dependency graphs, file vs interface, intent classification
├── semantic_index/ # Call graphs, type relationships, intent mappings
├── debug_history/ # Error→solution pairs, context, versions
├── patterns/ # Canonical + empirical interface patterns, reliability metrics
├── qa/ # Solved Qs, reasoning docs, context logs
├── docs_model_friendly/ # Component purpose & relationships
├── delta_summaries/ # API & behavior change logs, reasoning logs
└── memory_anchors/ # UUID-anchored semantic references
Rules:

Metadata → normalize file types, dependencies, and intents.

Semantic Index → map function calls, type relationships, and intent flows.

Debug History → log all sessions with error→solution pairs and context.

Patterns → keep canonical patterns + empirical usage. Add reliability metrics.

QA Database → solved queries indexed by file/component/error type.

Docs → model-friendly explanations of purposes & relationships.

Delta Summaries → record API/behavior shifts with reasoning.

## Memory Anchors → embed UUID-tagged semantic anchors in code

## Example

You are asked to implement a new API client.

1. Create a baseline golden test to capture current client behavior.
2. Write a failing test for the new endpoint.
3. Implement minimal code to pass the test.
4. Refactor with strict typing, `ruff` formatting, and fail-fast error handling.
5. Update `.claude/semantic_index/function_call_graphs.json` to reflect new call paths.
6. Add a `delta_summaries/api_change_logs.json` entry documenting the new endpoint.
7. Commit with a focused diff.

## KB TOOL
- Capture every meaningful fix, feature, or debugging pattern immediately with `claude-kb add` (pick the right entry type, set `--component`, keep the summary actionable, and include error + solution context).
- If you are iterating on an existing pattern, prefer `claude-kb update` so history stays linear; the command fails loudly if the entry is missing—stop and audit instead of recreating it.
- Once the entry is accurate, run `claude-kb sync --verbose` to refresh `.claude/manifest.json` and surface drift against the repo.
- Finish with `claude-kb validate` to guarantee schema integrity before you move on; do not skip even for small edits.
- When cleaning up stale knowledge, use `claude-kb delete …` and immediately re-run `sync` + `validate` so Git reflects the removal.
- Treat the KB like production code: review diffs, keep entries typed, and never leave `.claude/` out of sync with the changes you just shipped.

.claude layout
The tool keeps everything under .claude/ and will create the folders on demand:

.claude/
  metadata/      component summaries
  debug_history/ debugging timelines
  qa/            question & answer entries
  code_index/    file references
  patterns/      reusable fixes or snippets
  cheatsheets/   quick reference sections
  manifest.json  last sync snapshot
Everyday workflow
# create a typed entry
claude-kb add pattern --component ui.auth --summary "Retry login" \
  --error "Explain retry UX" --solution "Link to pattern doc"

# modify an existing entry (errors when the item is missing)
claude-kb update pattern --component ui.auth \
  --error "Retry login" --solution "Updated copy"

# list or validate your KB
claude-kb list --type pattern
claude-kb validate

# sync manifest and inspect git drift
claude-kb sync --verbose
claude-kb diff --since HEAD~3

# remove stale data
claude-kb delete pattern --component ui.auth



```

---

Available Sub-Agents

You can use these as needed to break down tasks into smaller ones.

- codebase-analyzer
- code-synthesis-analyzer
- codebase-locator
```
