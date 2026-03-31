---
name: audit-harness
description: Use when auditing HARNESS.md, pre-commit hooks, pre-push hooks, architecture gates, or CI workflows for tunacode-cli. This skill treats any mismatch, skipped gate, or failing check as a critical failure and requires manual one-by-one execution rather than make targets, batch wrappers, or summary-only audits.
---

# Audit Harness

`HARNESS.md` is mission-critical. Audit it with zero tolerance.

## Trigger

Use this skill when the user asks to:

- audit `HARNESS.md`
- verify harness accuracy
- run pre-commit or pre-push hooks manually
- confirm architecture or CI gates
- explain what actually enforces the harness

## Hard Rules

- Treat any mismatch, omission, skipped gate, auto-fix, or failing check as a critical failure.
- Never describe results as "mostly passing", "just one failure", or equivalent minimization.
- State the exact failure first.
- Explain the finding before changing code or docs.
- Do not proceed with a fix until the user tells you to proceed.
- During harness audits, never use `make check`, `scripts/run_gates.py`, or any loop/script wrapper as the primary audit path.
- Run checks manually, one by one, in the same order they appear in the source-of-truth config.
- If a hook modifies files, report the exact files immediately.
- Do not revert hook changes unless the user explicitly asks.

## Source Of Truth Order

Read these first:

1. `HARNESS.md`
2. `.pre-commit-config.yaml`
3. `Makefile`
4. `tests/test_dependency_layers.py`
5. `scripts/grimp_layers_report.py`
6. `.github/workflows/*.yml`
7. `docs/git/practices.md`
8. `AGENTS.md`

## Manual Audit Procedure

### Pre-commit

1. Enumerate the active pre-commit hooks from `.pre-commit-config.yaml`.
2. Start at the top.
3. Run each hook manually:

```bash
uv run pre-commit run <hook-id> --all-files
```

4. After each hook:
   state `Passed`, `Failed`, `Skipped`, or `Modified files`.
5. If a hook fails, stop and explain why before proposing a fix.

### Pre-push

1. Enumerate the active pre-push hooks from `.pre-commit-config.yaml`.
2. Run each one manually, one by one:

```bash
uv run pre-commit run <hook-id> --hook-stage pre-push --all-files
```

3. Treat any failure as critical.

### Architecture

- `tests/test_dependency_layers.py` is the source of truth for `grimp` enforcement.
- `scripts/grimp_layers_report.py` is report generation only.
- `scripts/run_gates.py` is supplemental only and not canonical.

### CI/CD

For each workflow, label it clearly as one of:

- local source of truth
- local supplemental check
- CI enforcement
- CI artifact generation
- CI report / issue automation

If wording in `HARNESS.md` hides an important behavior, call that a critical documentation failure.

## Response Style

- Be short.
- Be exact.
- One failure is a critical failure.
- Do not soften language.
