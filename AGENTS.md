
###Instruction###
Your task is to optimize and extend this repository following explicit coding, testing, and documentation workflows.

Example of ReAct loop:

Reason: I need to know if a golden baseline test exists for this feature.

Act: Search the tests/ directory for existing coverage.

You MUST comply with the rules below. You will be penalized if you deviate. Answer in a natural, human-like manner. you MUST keep.claude updated as instructed below. You will be punished for now keeping .claude kb in synch. You MUST always follow the ReAct Pattern (reasoning + acting) when solving tasks, explicitly alternating between reasoning steps and concrete actions.
---

### Workflow Rules
* Never begin coding until the objective is **explicitly defined**. If unclear, ask questions or use best practices.
* Always use `.venv` and `uv` for package management.
* Small, focused diffs only. Commit frequently.

### Code Style & Typing

* Enforce `ruff check --fix .` before PRs.
* Use explicit typing. `cast(...)` and `assert ...` are OK.
* `# type: ignore` only with strong justification.

### Error Handling

* Fail fast, fail loud. No silent fallbacks.
* Minimize branching: every `if`/`try` must be justified.

### Dependencies

* Avoid new core dependencies. Tiny deps OK if widely reused.

### Testing (TDD Red → Green → Blue)

1. If a test doesn’t exist, create a **golden baseline test first**.
2. Add a failing test for the new feature.
3. Implement until tests pass.
4. Refactor cleanly.

* Run with: `hatch run test`.

### Documentation

* Keep concise and actionable.
* Update when behavior changes.
* Avoid duplication.

### Scope & Maintenance

* Backward compatibility only if low maintenance cost.
* Delete dead code (never guard it).
* Always run `ruff .`.
* Use `git commit -n` if pre-commit hooks block rollback.

---
Claude-Specific Repository Optimization

Maintain .claude/ with the following structure:

claude/
├── metadata/                # Dependency graphs, file vs interface, intent classification
├── semantic_index/          # Call graphs, type relationships, intent mappings
├── debug_history/           # Error→solution pairs, context, versions
├── patterns/                # Canonical + empirical interface patterns, reliability metrics
├── qa/                      # Solved Qs, reasoning docs, context logs
├── docs_model_friendly/     # Component purpose & relationships
├── delta_summaries/         # API & behavior change logs, reasoning logs
└── memory_anchors/          # UUID-anchored semantic references


Rules:

Metadata → normalize file types, dependencies, and intents.

Semantic Index → map function calls, type relationships, and intent flows.

Debug History → log all sessions with error→solution pairs and context.

Patterns → keep canonical patterns + empirical usage. Add reliability metrics.

QA Database → solved queries indexed by file/component/error type.

Docs → model-friendly explanations of purposes & relationships.

Delta Summaries → record API/behavior shifts with reasoning.

Memory Anchors → embed UUID-tagged semantic anchors in code.
---

### Example##\#

You are asked to implement a new API client.

1. Create a baseline golden test to capture current client behavior.
2. Write a failing test for the new endpoint.
3. Implement minimal code to pass the test.
4. Refactor with strict typing, `ruff` formatting, and fail-fast error handling.
5. Update `.claude/semantic_index/function_call_graphs.json` to reflect new call paths.
6. Add a `delta_summaries/api_change_logs.json` entry documenting the new endpoint.
7. Commit with a focused diff.

###RAG TOOl###
in llm-agent-tools/rag_modules/ a tool exist to search the .claude/ directory via RAG

./rag-cli.sh index              # Index .claude/ directory
./rag-cli.sh index --full       # Full reindex
./rag-cli.sh search "query"     # Search across .claude/
./rag-cli.sh stats              # Show index stats

# Filtered / formatted search
./rag-cli.sh search "query" --category dev --format json --limit 5

You MUST call this tool at least once per session to ground context.
Use it heuristically before answering tasks that require repo knowledge. You will be punished for not using it to find relevant context before answering questions.
---
