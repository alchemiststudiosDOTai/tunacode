# AGENTS.md
Last Updated: 2026-04-23

## Repository Orientation
- This is `tunacode-cli`, a terminal AI coding agent with a Textual UI and tiny-agent tool loop.
- Primary source package: `src/tunacode/`.
- Python requirement: 3.11+ (`pyproject.toml`).
- We use UV and .venv


## Start Here
- `docs/modules/index.md` — module layer map and reading order.
- `docs/architecture/dependencies/DEPENDENCY_LAYERS.md` — generated dependency summary.
- `docs/skills/audit-harness/SKILL.md` — strict harness-audit procedure; treat any mismatch or failed gate as critical and run checks manually one by one.
- `docs/modules/ui/commands.md` — command model and command registration notes.
- `docs/workflows/README.md` — accepted development workflows and execution guidance.
- `scripts/check_agents_freshness.py` — validates this file is current.

## Harness Documentation Purpose
- `HARNESS.md` documents the code-quality harness for this repository.
- It captures pre-commit, pre-push, repository rules, and CI/CD checks in one place.
- The goal is to balance developer speed with reliability when programming with code agents.
- Use it as the operational checklist for what runs locally vs what is enforced in CI.

## Git Safety and Non-Destructive Defaults
- Follow `docs/git/practices.md` for local Git workflow and safety rules.
- Use `docs/git/changelog-update.md` when the task is to refresh `CHANGELOG.md` from recently merged PRs.
- Before performing any Git operation (`git status`, `git add`, `git commit`, etc.), read `docs/git/practices.md` in that session.
- Default behavior is non-destructive: never delete or clean untracked files/directories unless explicitly requested by the user.
- If unknown files appear during checks, pause and ask before cleanup.
- During commit-time check failures, do not make architectural/refactor decisions to force a green commit; only apply trivial lint-only fixes, otherwise stop and ask for user instruction.

## Top-Level Layout
- `src/tunacode/` — application code.
- `tests/` — unit and architecture tests.
- `docs/` — module documentation and architecture artifacts.
- `scripts/` — local tooling and validation scripts.
- `.github/workflows/` — CI gates and release workflows.
- `Makefile` — developer-facing command shortcuts.
- `pyproject.toml` — package metadata, deps, lint/type/security settings.

## Entry Points
- App entry: `src/tunacode/ui/main.py` (Typer app at `tunacode` script).
- `pyproject.toml:[project.scripts]` -> `tunacode = "tunacode.ui.main:app"`.
- Developer entry: `Makefile` target `make run` -> `uv run tunacode`.

## Source Structure (high-level)
- `src/tunacode/ui/` — terminal UI, widgets, screens, CSS, command shell, and render-safety helpers for Rich/Textual theme stability.
- `src/tunacode/core/` — agents, compaction, session, prompting, logging.
- `src/tunacode/tools/` — native tinyagent tool implementations (`bash`, `discover`, `read_file`, `hashline_edit`, `web_fetch`, `write_file`) plus supporting helpers.
- `src/tunacode/configuration/` — settings, model registry, API paths, limits, pricing, and ignore patterns.
- `src/tunacode/infrastructure/` — caches and managers.
- `src/tunacode/utils/` — adapters, messaging helpers, token counting, gitignore, system utilities.
- `src/tunacode/types/` — canonical data models, callbacks, protocol types.
- Shared packages: `src/tunacode/constants.py`, `src/tunacode/exceptions.py`, `src/tunacode/skills/`, `src/tunacode/prompts/`.
- Notable sub-packages: `src/tunacode/core/ui_api/` (core→UI bridge), `src/tunacode/tools/lsp/` (LSP client integration).

## Architecture Boundaries
- Documented conceptual stack (bottom-up): `types -> utils -> infrastructure -> configuration -> tools -> core -> ui`.
- Architectural enforcement test: `tests/test_dependency_layers.py`.
  - Allowed import direction: `ui -> core -> tools`, with shared-layer imports from `utils`, `types`, `configuration`, `constants`, `exceptions`.
- Import ordering test: `tests/architecture/test_import_order.py`.
  - Layer order constant includes shared modules (`configuration, constants, exceptions, prompts, skills, types, utils`) then layered modules (`tools, infrastructure, core, ui`).
- Public-init constraint: `tests/architecture/test_init_bloat.py`.
- Dependency map regeneration pipeline: `scripts/grimp_layers_report.py`, committed to `docs/architecture/dependencies/` by workflow.

## Documentation Sources to Trust
- Primary runbook: `README.md`.
- Architectural map: `docs/modules/index.md`.
- Review notes for active PR triage: `docs/reviews/`.
- Debugging and investigation artifacts: `docs/reviews/*-artifact.md`.
- Git workflow and safety practices: `docs/git/practices.md`.
- Changelog refresh procedure for merged PR summaries: `docs/git/changelog-update.md`.
- Workflow guidance: `docs/workflows/README.md` and workflow-specific files such
  as `docs/workflows/REFACTOR.md`.
- Module-specific docs:
  - `docs/modules/core/core.md`
  - `docs/modules/ui/ui.md`
  - `docs/modules/tools/tools.md`
  - `docs/modules/tools/hashline-subsystem.md`
  - `docs/modules/configuration/configuration.md`
  - `docs/modules/configuration/models-registry.md`
  - `docs/modules/infrastructure/infrastructure.md`
  - `docs/modules/types/types.md`
  - `docs/modules/utils/utils.md`
  - `docs/modules/skills/skills.md`
- UI design reference: `docs/ui/css-architecture.md` and generated map at `docs/codebase-map/structure/tree-structure.txt`.

## Routine Commands
- Setup: `make install` (canonical full dev environment bootstrap).
  - Installs repo-managed `pre-commit` and `pre-push` git hooks from `.githooks/`.
- Compatibility alias: `make dev-setup`.
- Run app: `make run`.
- Full tests: `make test`.
- Linters + hooks: `make lint`.
- Focused checks:
  - `uv run pre-commit run --all-files`
  - `uv run pytest`
  - `uv run pytest tests/test_dependency_layers.py -v`
  - `uv run pytest tests/architecture/test_import_order.py`
  - `uv run pytest tests/architecture/test_init_bloat.py`
  - `uv run python scripts/run_gates.py`
  - `uv run python scripts/check_agents_freshness.py`
  - `uv run python scripts/generate_structure_tree.py`

## CI and Release Signals
- Lint/security pipeline: `.github/workflows/lint.yml`.
- Dependency map updates: `.github/workflows/dependency-map.yml`.
- Tech debt scans: `.github/workflows/tech-debt.yml`.
- Version/release checks:
  - `uv run python scripts/generate-release-notes.sh` (auxiliary script usage in repo)
  - release workflows: `release.yml`, `publish-release.yml`.
- Additional hygiene: `.github/workflows/empty-dir-check.yml` for dead directories.

## Quality Constraints (Do not break)
- `README.md` and docs should stay consistent with implementation.
- Keep `AGENTS.md` updated with `Last Updated: YYYY-MM-DD` whenever `src/` or `docs/` changes.
- The 2026-04-13 getattr baseline follow-up reduced the scoped UI/runtime and owned-exception `getattr(...)` usage; the committed ast-grep baseline should stay aligned with those removals.
- Do not add TunaCode-owned message-contract wrappers around tinyagent message types; use tinyagent models directly in memory and keep dict payloads at real boundaries.
- Preserve existing architecture order rules; do not add new imports across forbidden layers.
- Treat current file-length allowlist entries as temporary debt only. Do not add any new file-specific exemptions to the `>600` line rule; fix the enforcement path or split the code instead.
- Do not edit unrelated local changes unless scoped to the task.
- Never delete untracked files/directories (or run destructive cleanup) without explicit user confirmation.
- Avoid adding empty directories or `__init__.py`-only directories.

## Editing Guidance
- Prefer small, scoped changes.
- Keep edits minimal and targeted.
- Prefer existing patterns; mirror command/test naming used in nearby code.
- Treat `src/tunacode/ui/render_safety.py` plus built-in theme wrapping in `src/tunacode/constants.py` as part of the startup/theme stability path; keep Rich default/ANSI color handling local to TunaCode rather than patching Textual.
- Run validation commands before handoff when touching architecture, dependencies, or shared packages.
