# Technical Debt Tracking

This document describes how TODO/FIXME items are tracked and managed in the codebase.

## Overview

The project uses a custom scanner (`scripts/todo_scanner.py`) to detect and track technical debt markers in the codebase. This integrates with CI to prevent debt accumulation and generate reports.

## Debt Markers

The scanner recognizes these marker types:

| Marker | Priority | Usage |
|--------|----------|-------|
| `TODO` | Normal | Planned work that should be done |
| `FIXME` | High | Known bugs or broken code needing repair |
| `HACK` | High | Temporary workarounds requiring proper solutions |
| `XXX` | Critical | Dangerous code or urgent attention needed |

## Format

Use this format for debt markers:

```python
# TODO(scope): description [TUN-XXXX]
# FIXME(core): handle edge case when input is None [TUN-1234]
# HACK(ui): temporary workaround for layout bug [TUN-5678]
```

- **scope**: The component or module affected
- **description**: Clear explanation of what needs to be done
- **TUN-XXXX**: Optional ticket reference from the `tk` system

## CI Integration

### Pull Request Checks

The `tech-debt.yml` workflow runs on every PR:

1. Scans for all debt markers
2. Compares against `scripts/todo_baseline.json`
3. **Fails if debt increases** from baseline

### Weekly Reports

Scheduled runs (Sundays at 00:00 UTC):

1. Generate full debt report
2. Upload artifact for analysis
3. Create/update GitHub issue if debt found

## Managing Debt

### View Current Debt

```bash
# Text report
uv run python scripts/todo_scanner.py --format text

# Include test files
uv run python scripts/todo_scanner.py --format text --include-tests

# JSON output
uv run python scripts/todo_scanner.py --format json
```

### Update Baseline

If you've intentionally added or removed debt items:

```bash
uv run python scripts/todo_scanner.py --output scripts/todo_baseline.json
```

Commit the updated baseline:

```bash
git add scripts/todo_baseline.json
git commit -m "chore: update tech debt baseline"
```

### Fail on New Debt

To enforce zero debt (fails if any markers found):

```bash
uv run python scripts/todo_scanner.py --fail-on-new
```

## Baseline File

`scripts/todo_baseline.json` represents the **accepted** debt level. CI compares current scans against this baseline:

- **Below baseline**: OK (debt reduced)
- **At baseline**: OK (no change)
- **Above baseline**: **FAIL** (debt increased)

## Exclusions

These paths are excluded from scanning:

- `.git/`, `__pycache__/`, `.venv/`
- `build/`, `dist/`, `*.egg-info/`
- `pyproject.toml`, `.pre-commit-config.yaml`
- Markdown files (`*.md`)
- Test files (unless `--include-tests` flag used)

## Related Tools

- **Ruff**: Already configured with `FIX` and `TD` rules for TODO/FIXME detection
- **tk CLI**: Use for ticket management alongside debt markers
- **Quality Gates**: See `quality-gates.md` for broader quality standards

## Workflow Example

1. **Add a TODO** while coding:
   ```python
   # TODO(parser): add validation for nested tags [TUN-1234]
   ```

2. **Create ticket** with `tk`:
   ```bash
   tk add "Add validation for nested tags in parser"
   ```

3. **Update baseline** after PR merge:
   ```bash
   uv run python scripts/todo_scanner.py --output scripts/todo_baseline.json
   ```

4. **Track progress** via weekly reports or:
   ```bash
   uv run python scripts/todo_scanner.py --format text
   ```
