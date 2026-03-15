# AGENTS.md
Last Updated: 2026-03-15

## Repository Orientation
- This is `tunacode-cli`, a terminal AI coding agent with a Textual UI and tiny-agent tool loop.
- Primary source package: `src/tunacode/`.
- Python requirement: 3.11+ (`pyproject.toml`).

## Start Here
- `README.md` — user-facing setup, supported features, and command usage.
- `docs/modules/index.md` — module layer map and reading order.
- `docs/architecture/dependencies/DEPENDENCY_LAYERS.md` — generated dependency summary.
- `docs/modules/ui/commands.md` — command model and command registration notes.
- `scripts/check_agents_freshness.py` — validates this file is current.

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
- `src/tunacode/ui/` — terminal UI, widgets, screens, CSS, command shell.
- `src/tunacode/core/` — agents, compaction, session, prompting, logging.
- `src/tunacode/tools/` — tool implementations exposed to the model (bash, glob, read/write, web fetch, etc.).
- `src/tunacode/configuration/` — settings, model registry, API paths, limits, pricing, feature flags.
- `src/tunacode/infrastructure/` — caches and managers.
- `src/tunacode/utils/` — adapters, messaging helpers, token counting, gitignore, system utilities.
- `src/tunacode/types/` — canonical data models, callbacks, protocol types.
- Shared packages: `src/tunacode/constants.py`, `src/tunacode/exceptions.py`, `src/tunacode/skills/`, `src/tunacode/prompts/`.
- Additional packages: `src/tunacode/lsp/`, `src/tunacode/indexing/`, `src/tunacode/core/ui_api/`.

## Architecture Boundaries
- Documented conceptual stack (bottom-up): `types -> utils -> infrastructure -> configuration -> tools -> core -> ui`.
- Architectural enforcement test: `tests/test_dependency_layers.py`.
  - Allowed import direction: `ui -> core -> tools -> lsp`, with shared-layer imports from `utils`, `types`, `configuration`, `constants`, `exceptions`.
- Import ordering test: `tests/architecture/test_import_order.py`.
  - Layer order constant includes shared modules (`configuration, constants, exceptions, lsp, prompts, skills, types, utils`) then layered modules (`tools, infrastructure, core, ui`).
- Public-init constraint: `tests/architecture/test_init_bloat.py`.
- Dependency map regeneration pipeline: `scripts/grimp_layers_report.py`, committed to `docs/architecture/dependencies/` by workflow.

## Documentation Sources to Trust
- Primary runbook: `README.md`.
- Architectural map: `docs/modules/index.md`.
- Module-specific docs:
  - `docs/modules/core/core.md`
  - `docs/modules/ui/ui.md`
  - `docs/modules/tools/tools.md`
  - `docs/modules/configuration/configuration.md`
  - `docs/modules/infrastructure/infrastructure.md`
  - `docs/modules/types/types.md`
  - `docs/modules/utils/utils.md`
  - `docs/modules/skills/skills.md`
- UI design reference: `docs/ui/css-architecture.md` and generated map at `docs/codebase-map/structure/tree-structure.txt`.

## Routine Commands
- Setup: `make dev-setup`.
- Install/update dependencies: `make install`.
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
- Preserve existing architecture order rules; do not add new imports across forbidden layers.
- Do not edit unrelated local changes unless scoped to the task.
- Avoid adding empty directories or `__init__.py`-only directories.

## Editing Guidance
- Prefer small, scoped changes.
- Keep edits minimal and targeted.
- Prefer existing patterns; mirror command/test naming used in nearby code.
- Run validation commands before handoff when touching architecture, dependencies, or shared packages.
