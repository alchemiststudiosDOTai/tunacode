---
title: Harness
summary: Repository code-quality harness for hooks, CI checks, and local enforcement.
when_to_read:
  - When auditing pre-commit or pre-push hooks
  - When checking local and CI enforcement behavior
last_updated: "2026-04-13"
---

# HARNESS.md

## Pre-commits

Source of truth: `.pre-commit-config.yaml`

Git hook entrypoints are repo-managed wrappers in `.githooks/`, installed into `.git/hooks/` as relative symlinks by `scripts/install-git-hooks.sh`. This keeps hook execution tied to the checkout's local `.venv` after the repository directory moves.

### Global pre-commit settings
- Python runtime: `python3`
- Global exclude regex:
  - `venv/`, `build/`, `dist/`, `.git/`, `__pycache__/`, `*.egg-info/`
  - `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.uv-cache/`, `.uv_cache/`
  - `htmlcov/`, `.coverage`, `reports/`, `llm-agent-tools/`, `.tickets/`, `tinyAgent/`

### Active pre-commit hooks (organized by purpose)

#### File hygiene and repo safety
- `trailing-whitespace` (repo: `pre-commit/pre-commit-hooks`)
- `end-of-file-fixer` (repo: `pre-commit/pre-commit-hooks`, excludes `models_registry.json`)
- `mixed-line-ending` (repo: `pre-commit/pre-commit-hooks`, args: `--fix=lf`)
- `check-added-large-files` (repo: `pre-commit/pre-commit-hooks`, args: `--maxkb=1000`)
- `check-case-conflict` (repo: `pre-commit/pre-commit-hooks`)
- `check-merge-conflict` (repo: `pre-commit/pre-commit-hooks`)
- `check-executables-have-shebangs` (repo: `pre-commit/pre-commit-hooks`)
- `check-shebang-scripts-are-executable` (repo: `pre-commit/pre-commit-hooks`)

#### Config and syntax validity
- `check-yaml` (repo: `pre-commit/pre-commit-hooks`, args: `--allow-multiple-documents`)
- `check-json` (repo: `pre-commit/pre-commit-hooks`)
- `check-toml` (repo: `pre-commit/pre-commit-hooks`)
- `check-ast` (repo: `pre-commit/pre-commit-hooks`)
- `check-docstring-first` (repo: `pre-commit/pre-commit-hooks`)
- `debug-statements` (repo: `pre-commit/pre-commit-hooks`)

#### Python linting, typing, and formatting
- `ruff` (repo: `astral-sh/ruff-pre-commit`, args: `--fix --show-fixes`)
- `ruff-format` (repo: `astral-sh/ruff-pre-commit`, excludes `models_registry.json`)
- `dead-imports` (repo: `local`, entry: `scripts/run-dead-imports.sh`, files: `\.py$`)
- `stale-symbol-surfaces` (repo: `local`, entry: `uv run python scripts/check_stale_symbol_surfaces.py`, stage: `pre-push`)
  - Detects public symbols that survive only via package `__init__` re-exports or same-module annotation scaffolding.
- `vulture-changed` (repo: `local`, entry: `uv run vulture --min-confidence 80 scripts/utils/vulture_whitelist.py`, files: `^src/.*\.py$`, exclude: `tests/|test_`)
- `naming-conventions` (repo: `local`, entry: `uv run python scripts/check-naming-conventions.py`, files: `^src/.*\.py$`, exclude: `tests/|scripts/`)
- `defensive-slop` (repo: `local`, entry: `uv run python scripts/check-defensive-slop.py`, files: `^src/.*\.py$`, stages: `pre-commit`, `pre-push`)
- `check-file-length` (repo: `local`, entry: `scripts/check-file-length.sh`, files: `\.py$`, exclude: `tests/`)
  - Current behavior: enforces the `>600` line rule for non-test Python files only. All files under `tests/` are intentionally excluded from this gate.

#### Security and safeguards
- `bandit` (repo: `PyCQA/bandit`, args: `-c pyproject.toml`, dep: `bandit[toml]`)
- `security-check` (repo: `local`, grep for `PRIVATE|SECRET|PASSWORD|TOKEN` in `src/**/*.py`)
- `no-print-statements` (repo: `local`, grep for `print(` in `src/**/*.py`, ignores `# noqa` and `# pragma`)
- `unused-constants` (repo: `local`, entry: `uv run python scripts/check-unused-constants.py`)

#### Architecture and docs
- `dependency-layers` (repo: `local`, entry: `uv run pytest tests/test_dependency_layers.py -v`)
  - Source of truth for import-layer enforcement: `tests/test_dependency_layers.py` uses `grimp.build_graph("tunacode")` to detect illegal cross-layer imports.
  - Dependency report generation: `scripts/grimp_layers_report.py` uses `grimp` to generate `docs/architecture/dependencies/DEPENDENCY_LAYERS.*`.
  - Supplemental only: `scripts/run_gates.py` also uses `grimp`, but it is not the canonical architecture check.
- `tests/architecture/test_import_order.py` enforces first-party import layer ordering.
- `tests/architecture/test_init_bloat.py` enforces thin `__init__.py` modules.
- `scripts/check_agents_freshness.py` validates `AGENTS.md` freshness against recent `src/` and `docs/` changes.
- `doc8` (repo: `pycqa/doc8`, args: `--max-line-length=120`)
  - Current behavior: the hook is configured, but `pre-commit run doc8 --all-files` skips in this repository because no matching doc8-supported files are selected.

### Currently disabled in config
- `isort` (commented out; replaced by Ruff import sorting)
- `markdownlint` (commented out; noted Node.js v23 compatibility issue)

## Pre-push

Pre-push hooks run from `.pre-commit-config.yaml` with stage `pre-push`.

### Active pre-push hooks
- `mypy` (local, `uv run mypy --ignore-missing-imports --no-strict-optional`, scoped to `src/**/*.py`)
- `stale-symbol-surfaces` (local, `uv run python scripts/check_stale_symbol_surfaces.py`)
- `defensive-slop` (local, `uv run python scripts/check-defensive-slop.py`, scoped to `src/**/*.py`)
- `pylint-duplicates` (local, duplicate-code check)
- `pytest` (local, `uv run pytest -x -q`)
- `ast-grep-getattr-ratchet` (local, `scripts/run_ast_grep_checks.sh`, scoped to `src/**/*.py`, `rules/ast-grep/**`, and ast-grep helper scripts)
  - Validates the ast-grep rule file, runs the rule test, then scans all of `src/` for `getattr(...)` and fails only on findings not present in the committed baseline.
- `empty-dir-check` (local, `uv run python scripts/utils/check_empty_dirs.py`)
- `markdown-frontmatter` (local, `uv run python scripts/check_markdown_frontmatter.py`, scoped to repo-root/docs markdown except `AGENTS.md` and root `README.md`)

### Run hooks manually
- Canonical local harness entrypoint: `make check`
- Pre-commit stage: `uv run pre-commit run --hook-stage pre-commit --all-files`
- Pre-push stage: `uv run pre-commit run --hook-stage pre-push --all-files`
- Combined shortcut: `make check`

## Rules

- Internal typed paths must stay direct.
- Do not add Protocol+stub indirection for concrete runtime model methods.
- Do not add runtime re-validation after boundary validation (e.g., post-`model_dump` dict shape checks).
- `scripts/check-defensive-slop.py` is a blocking guard for these patterns.

## CI/CD

- Local source of truth: `make check` runs the full pre-commit and pre-push hook stages across all files, plus the CI enforcement checks for full dead-code scan, orphan-module detection, and `deptry`.
- Local supplemental check: `uv run python scripts/run_gates.py` is a subset spot-check and does not mirror the full local or CI harness.
- CI enforcement: pre-commit and pre-push remain the first enforcement line before CI.
- CI enforcement: `.github/workflows/lint.yml` runs `pre-commit`, full dead-code checks, stale symbol surface detection, orphan-module detection, and a separate `deptry` job.
- CI enforcement: `.github/workflows/empty-dir-check.yml` enforces the empty-directory / `__init__.py`-only directory rule in CI.
- CI artifact generation: `.github/workflows/dependency-map.yml` runs on pushes to `main`/`master`, regenerates `docs/architecture/dependencies/DEPENDENCY_LAYERS.*`, and pushes changes to `automation/dependency-map` for PR review.
- CI report / issue automation: `.github/workflows/tech-debt.yml` scans TODO/FIXME-style debt and the scheduled report job can open or update a GitHub issue.
