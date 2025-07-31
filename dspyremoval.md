Here’s what that plan means and how to execute it—clean and safe.

## What & Why

* **Goal:** Remove an unused DSPy experiment (tool-selection optimization) that’s isolated from your main agent flow.
* **Safety:** No imports in core, no dependency in `pyproject.toml`, and no tests rely on it—so deleting won’t break runtime.

## Scope of removal

* **Delete** 6 DSPy-specific files (2 core modules + 2 prompt templates + 2 docs).
* **Edit** 3 places:

  * `defaults.py`: drop `use_dspy_optimization`.
  * `docs/deadcode.md`: remove listed line refs to `dspy_tunacode.py`.
  * `whitelist.py`: remove `_trace = None` (only used by DSPy code).

## Execution order (checklist)

1. **Branch:** `git checkout -b chore/remove-dspy`.
2. **Delete files:** `git rm` the six DSPy files.
3. **Edit config/docs/whitelist** as noted.
4. **Search for stragglers:** `rg -n -S "(dspy|use_dspy_optimization|_trace)" src docs tests`.
5. **Run quality gates:** your usual `pytest`, linter, type checks (e.g., `ruff`, `mypy`).
6. **Build/smoke test:** run the CLI/main agent to confirm normal flows.
7. **PR notes:** call out that DSPy was unused; list removed files and tiny edits.

## Acceptance criteria

* Repo-wide search finds **no** `dspy`, `use_dspy_optimization`, or `_trace` leftovers.
* All tests pass; no import errors; normal agent flows work.
* `pyproject.toml` remains unchanged (no DSPy dep).

## Risks & mitigations

* **Hidden import/side effect:** Mitigate via step 4 (ripgrep) + full test run.
* **Doc cross-links break:** Build docs (if you have a docs build) or run link checker.
* **Type/format drift after deletion:** Run linters/formatters to keep CI green.
