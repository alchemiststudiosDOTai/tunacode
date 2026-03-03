---
title: Make Ruff import sorting deterministic across local and CI
type: delta
link: ruff-import-order-determinism
path: pyproject.toml
depth: 1
seams: [M]
ontological_relations:
  - affects: [[tooling]]
  - affects: [[ci]]
  - affects: [[imports]]
tags:
  - ruff
  - pre-commit
  - ci
  - import-order
created_at: 2026-03-03T04:30:00+00:00
updated_at: 2026-03-03T04:30:00+00:00
uuid: 1563860a-585a-49eb-a57a-52eb721c5912
---

# Make Ruff import sorting deterministic across local and CI

## Summary

Added `src = ["src"]` under `[tool.ruff]` so Ruff/isort classifies first-party modules from `src/` only.

This prevents local environment differences (for example, an untracked `tinyAgent/` directory) from changing how `tinyagent` imports are grouped.

Re-applied import sorting in files that were flipping between local and CI:

- `src/tunacode/core/agents/agent_components/agent_config.py`
- `src/tunacode/core/agents/main.py`
- `src/tunacode/tools/decorators.py`
- `tests/benchmarks/bench_discover.py`

## Why

PR #407 was failing the `pre-commit` GitHub check because Ruff auto-fixed imports in CI and exited with code 1.
Local pre-commit passed after fixes, but CI still re-sorted imports due different module classification.

## Validation

- `uv run pre-commit run --all-files` ✅
- `uv run pytest tests/integration/core/test_minimax_execution_path.py tests/integration/core/test_mtime_caches_end_to_end.py tests/system/cli/test_repl_support.py tests/unit/tools/test_tinyagent_tool_adapter.py -q` ✅
