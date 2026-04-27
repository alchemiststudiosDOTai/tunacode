---
title: Changelog
summary: Release history for TunaCode versions and notable changes.
when_to_read:
  - When preparing a release note
  - When reviewing past changes or version history
last_updated: "2026-04-27"
---

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-04-27

### Added
- Added a stale-symbol surface checker, related unit coverage, and lint/pre-push enforcement to catch dead re-export and annotation-only APIs.

### Changed
- Simplified stream orchestration and interrupted-stream cleanup by moving the stream loop into a dedicated module, tracking per-stream baselines, and tightening callback typing.
- Removed dead agent component helpers and legacy dangling-tool-call patching paths from the runtime cleanup flow.
- Documented explicit `bug:`/`refactor:` style labels for issues and PRs and clarified that the repository root `README.md` is exempt from markdown frontmatter requirements.
- Updated release-gate enums to `StrEnum` and restored tmux marker selection for the release E2E test.

### Fixed
- Fixed abort-time tool reconciliation so completed tool results are preserved and interrupted tool calls are patched with explicit error results instead of rolling history back.
- Fixed Textual startup and theme-switch rendering crashes by hardening built-in theme colors and normalizing Rich dim/default styles before Textual filtering.

## [0.2.0] - 2026-04-02

### Changed
- Cached conversation total token counts and improved request debug flow.
- Hardened the harness audit workflow.
- Documented the deployment flow and refreshed workflow action references.

## [0.1.101] - 2026-03-30

### Added
- Added a manual GitHub Actions PyPI publish workflow that verifies the requested version, builds artifacts, runs `twine check`, and uploads with the repository `PYPI_API_TOKEN` secret.
- Vendored a local `pypi-release` skill to document and automate the repository's release flow.

### Changed
- Aligned the vendored release skill and helper scripts with the repository's new workflow-dispatch publication path.
- Updated documentation to match the current configuration and UI behavior.
- Switched user configuration loading to typed config models and continued simplifying registry-backed metadata loading.
- Cleaned up ignore-pattern handling and removed additional unused packaging and runtime surface area.

### Fixed
- Restored ignore-file fallback behavior and added related regression coverage.
- Applied release-gate lint cleanups required for the vendored publish skill scripts.

## [0.1.100] - 2026-03-25

### Added
- Added provider stream lifecycle tracing for debug sessions.

### Changed
- Documented validation of the tiny-agent-os 1.2.27 GIL hotfix release.

## [0.1.99] - 2026-03-25

### Added
- Threaded request execution to move LLM processing off the UI thread for improved input responsiveness.
- RequestUiBridge for thread-safe callback adaptation between background workers and the Textual UI.
- Thread-safe UI message types for cross-thread event propagation.
- UI-thread delta flush timer and drain helper for batched stream updates.

### Changed
- Reduced the internal thinking-text buffer from 20k chars to 2.4k chars to minimize memory churn during live thought updates.
- Made thought refresh cadence adaptive: 100 ms normally, 300 ms while the editor contains an in-progress draft.
- Raised the detached-widget drafting-time thought throttle from 250 ms to 275 ms for improved stability.

### Fixed
- Fixed request cancellation and tmux test gating.
- Broadened ESC cancellation contract for threaded worker handles.
- Made TUI logger callback thread-safe via message posting.

## [0.1.98] - 2026-03-24

### Fixed
- Show the loading indicator immediately after submit so the TUI provides prompt feedback while requests are in flight.

## [0.1.97] - 2026-03-24

### Added
- Added a minimal tmux-backed hello integration test for end-to-end CLI validation.

### Changed
- Completed the move to the native tinyagent tool surface by keeping only `bash`, `discover`, `read_file`, `hashline_edit`, `web_fetch`, and `write_file` in active runtime and UI documentation.
- Removed remaining legacy tool-surface references from the UI/tool docs and README.
- Simplified tinyagent message typing flow.
- Bumped `tiny-agent-os` dependency to `1.2.26`.

### Fixed
- Clamped the command autocomplete dropdown within the viewport to prevent overflow.
- Fixed trailing whitespace in generated artifacts.

### Removed
- Removed the leftover legacy compatibility surface for retired tool names such as `update_file`, `glob`, `grep`, and `list_dir` instead of translating them through a normalizer.

## [0.1.96] - 2026-03-21

### Changed
- Added models registry workflow guide documentation.
- Added tmux suite validation artifact for release validation.

### Fixed
- Fixed MiniMax registry normalization after upstream refresh.
- Cleaned up documentation inconsistencies and added empty dir prevention.

## [0.1.95] - 2026-03-18

### Changed
- Bumped `tiny-agent-os` from 1.2.9 to 1.2.11.
- Added the v0.1.94 release run artifact to capture the full publication workflow.

### Fixed
- Skipped the live alchemy integration test when the binding is unavailable.
- Applied small `isinstance(..., X | Y)` cleanups required by the current Ruff rules.

## [0.1.94] - 2026-03-17

### Changed
- Enforced strict config source validation and updated quality harness documentation.
- Added git safety practices documentation and updated agent guidance.
- Removed stale worktree metadata and unused state machine infrastructure.
- Cleaned up defensive logic and tightened TUI cold-start paths.

### Fixed
- Fixed remaining typing issues and tool argument validation.
- Corrected tinyagent imports and split agent configuration for better modularity.
- Fixed CodeRabbit agent feedback issues.
- Stabilized headless tinyagent serialization.

## [0.1.93] - 2026-03-16

### Changed
- Reduced TUI cold-start overhead by tightening command-registry and package import loading paths.
- Cleaned up stale project artifacts by removing outdated `.claude/` and `.tickets/` repository files.

## [0.1.92] - 2026-03-14

### Changed
- Added clipboard copy support for selected UI text and extracted agent-text streaming into a dedicated UI module.


### Fixed
- Relaxed clipboard copy verification so successful copies no longer fail when verification is unavailable.
- Stabilized tmux system tool coverage by making discover stats and skill-load confirmations explicit and by deflaking tmux wait logic around persistent evidence.

## [0.1.91] - 2026-03-13

### Changed
- Hardcoded `AGENTS.md` as the guide file path and removed guide-file configurability.
- Cleaned up obsolete docs and removed the unused `memory-bank/` directory.

### Fixed
- Retried `/update` installs against the active Python interpreter when `uv tool upgrade` cannot locate the current install.
- Added regression coverage for the `uv tool` update fallback flow.

## [0.1.90] - 2026-03-09

### Changed
- Smoothed the model picker flow and hardened model selection state handling in the TUI.

### Fixed
- Stabilized tmux system startup by waiting for the editor prompt before sending end-to-end tool commands.
- Added explicit coverage for the loaded-skills panel title so the skills UI contract is tested outside tmux.

## [0.1.89] - 2026-03-07

### Changed
- Removed the bottom status bar from the TUI and flattened the editor border to match the panel design.

### Fixed
- Removed tmux system test dependence on the status bar so the end-to-end tool coverage stays stable after the UI cleanup.

## [0.1.88] - 2026-03-06

### Added
- Added tmux system coverage that loads a local skill and verifies the agent uses its referenced file end-to-end.

### Changed
- Consolidated skill lookup, loading, and selected-skill summary resolution onto a single registry-backed path.

### Fixed
- Preserved missing selected skills in UI summary surfaces while keeping prompt-building fail-loud for unresolved skill loads.
- Kept skill catalog and summary views limited to skill names and descriptions while direct selected-skill loads still inject full `SKILL.md` content plus absolute file paths.

## [0.1.87] - 2026-03-06

### Changed
- Increased the default shell tool timeout to two minutes to reduce premature command termination in normal workflows.

### Fixed
- Removed a flaky headless CLI system test from the release train.
- Stabilized tmux discover-tool system coverage by waiting for rendered scan stats before asserting output.

## [0.1.86] - 2026-03-06

### Added
- Introduced prompt context injection for actively loaded skills so selected skill guidance is surfaced to the agent runtime.

### Changed
- Refined skills UI styling and load behavior to improve local/global skill discovery ergonomics.

### Fixed
- Resolved selected-skill path handling to use discovered absolute paths reliably across local and global skill locations.
- Included absolute skill paths in prompt context to prevent path-resolution drift when rendering skill metadata.

## [0.1.85] - 2026-03-06

### Fixed
- Made `/skills` autocomplete prefer the most relevant skill match instead of fuzzy-reordering short prefixes.
- Isolated slash-command autocomplete to command names so `/skills` navigation and Enter selection no longer get hijacked by hidden command suggestions.

## [0.1.84] - 2026-03-06

### Fixed
- Improved skills loading UX and restored slash-command submit behavior.

## [0.1.83] - 2026-03-06

### Added
- Introduced a first-class skills subsystem with discovery, loading, session persistence, prompt rendering, and cache-backed registry support.
- Added `/skills` catalog, search, clear, and loaded-skill management commands in the TUI.

### Changed
- Exposed selected skills in the session inspector and included available/selected skill context in agent prompt construction.

### Fixed
- Restored compatibility with legacy markdown-only `SKILL.md` files that do not start with YAML frontmatter.
- Fixed local-over-global precedence for case-insensitive skill name collisions.
- Prevented invalid discovered skill summaries from crashing agent creation for unrelated sessions.

## [0.1.82] - 2026-03-05

### Changed
- Bumped the packaged TunaCode version to `0.1.82` to cut a new PyPI release.

## [0.1.81] - 2026-03-04

### Changed
- Migrated the live alchemy usage-contract integration test to the typed chutes flow for stricter runtime contract coverage.
- Refined tinyagent typing and compaction boundaries to tighten type-safety and reduce ambiguity in session compaction behavior.
- Removed residual `__all__` shim exports to satisfy Gate 0 and enforce direct exports only.
- Refreshed README screenshots to match the current UI.

### Fixed
- Declared `pydantic` as a direct project dependency to satisfy dependency analysis and prevent missing-direct-dependency failures.

## [0.1.80] - 2026-03-03

### Fixed
- Aligned the `bash` tool timeout contract to seconds across prompt docs and runtime validation to prevent repeated millisecond-based tool failures.
- Hardened `bash` timeout bounds handling by rejecting `timeout=0` and added regression tests for timeout validation and prompt contract drift.

## [0.1.79] - 2026-03-03

### Added
- Added a full prompt-versioning pipeline with computed hashes, mtime-aware caching, and agent-level observability hooks.

### Fixed
- Fixed `original_query` being reset on every request instead of preserved across multi-turn sessions.
- Hid internal tool validation errors from user-facing output.
- Fixed typing issues in the thinking panel widget and constants module.
## [0.1.78] - 2026-02-26

### Changed
- Removed dead NeXTSTEP UI tool renderer modules for retired tools (`glob`, `grep`, `list_dir`) and cleaned renderer exports/tests to match the tinyagent-only tool surface.

## [0.1.77] - 2026-02-25

### Changed
- Tightened the session inspector presentation and removed a redundant compaction field to reduce TUI chrome noise.

## [0.1.75] - 2026-02-23

### Added
- Tool panel CSS flow with status-based classes (running/completed/failed)
- Compaction awareness indicator in context panel
- CSS tint styling for file tool states (read/update)
- Parallel tool lifecycle coverage: capped-concurrency execution test, RequestOrchestrator parallel batch tests, and status-bar callback sequencing tests

### Changed
- Enhanced `/compact` command with error handling and user feedback
- Updated read_file renderer to support new hashline format (1:ab|content)
- Improved tool panel rendering with semantic CSS classes
- Bumped `tiny-agent-os` dependency to `>=1.2.5` and refreshed lockfile resolution
- Enforced max 3 in-flight tool executions via shared tool semaphore wrapping
- Hardened RequestOrchestrator tool-start arg normalization and made batch-mode duration reporting explicit (suppressed for multi-tool batches)
- Updated status bar running-state behavior to stay coherent while multiple tools are active

## [0.1.74] - 2026-02-21

### Changed
- Rewrite system prompt to describe tools by purpose, not signature
- Clean up discover.py (remove section comments and inline comments)

### Fixed
- Normalize @mentions to absolute paths in UI

## [0.1.73] - 2026-02-20

### Changed
- Extracted thinking state and lifecycle management from app.py into dedicated classes
- System prompt tooling refresh
- Temporarily disabled live text streaming; default thoughts ON
- Removed rich_log alias and enforced full cutover
- Trimmed app.py docstrings to stay under 600-line hook limit

### Fixed
- Eliminated blank space between chat content and streaming output

### Removed
- Dead code: unused openai_response_validation.py
- Added orphan module detection to CI and removed dead code from agent_helpers

## [0.1.72] - 2026-02-20

### Fixed
- `/update` command now works for global installs (`pipx`, `uv tool`). Version check uses PyPI JSON API instead of shelling out to `pip`. Upgrade detects tool-managed venvs and runs the correct upgrade command.

## [0.1.71] - 2026-02-20

### Added
- `discover` tool: unified code discovery replacing manual glob/grep/read chains with a single natural-language query

### Improved
- Replaced the synthetic `discover` benchmark with a real-repo harness in `tests/benchmarks/bench_discover.py` comparing single-call `discover` against the legacy `list_dir -> glob -> grep -> read_file` chain
- Benchmark output now reports end-to-end metrics that matter for agent workflows: cold/warm latency (including p50/p95), tool-call count, output token footprint, file/symbol recall, and actionability
- Current baseline run on TunaCode shows `discover` at 1.0 average tool calls vs 6.0 for legacy (6x fewer round trips), ~4.2x fewer output tokens (~3.1k vs ~12.9k), ~9% lower latency (cold: 2587ms vs 2811ms, warm: 2597ms vs 2832ms), and higher retrieval quality/actionability

### Removed
- `glob` tool (replaced by `discover`)
- `grep` tool and `grep_components/` module (replaced by `discover`)
- `list_dir` tool (replaced by `discover` + `bash`)

## [0.1.70] - 2026-02-19

### Improved
- API key UX: environment variable fallback, inline entry screen, and better error surfacing

## [0.1.69] - 2026-02-19

### Added
- Inline API key entry screen for model-selection flow when provider credentials are missing
- Unit coverage for API key entry behavior and authentication error rendering

### Changed
- Model command now reuses a named provider/model delimiter constant for provider parsing
- MiniMax provider endpoints normalized to `/v1` contract paths in integration/unit coverage

### Fixed
- API key save flow now raises user-facing errors for filesystem write failures without swallowing unexpected exceptions
- Headless-mode background task handling now shields request task execution and avoids timeout-driven cancellation races


## [0.1.67] - 2026-02-19

### Added
- First-class MiniMax alchemy routing for coding-plan and default execution paths
- MiniMax provider contract coverage in integration and unit tests

### Changed
- Updated provider defaults and models registry to expose MiniMax API-key contract entries
- Pinned `tiny-agent-os` dependency to `>=1.2.1` to support MiniMax provider routing


## [0.1.66] - 2026-02-17

### Added
- Thinking content streaming for extended thinking models (Claude 3.5+ with thinking enabled)
- `/thoughts` command to toggle thinking panel visibility
- Thinking panel renderer with truncation and collapsible display
- Tests for thinking stream routing, response extraction, and panel rendering

### Changed
- Updated bundled models registry from models.dev (92 providers)

## [0.1.65] - 2026-02-16

### Added
- Slopgotchi pet widget in context inspector with click interaction and ASCII art cycling
- Context panel with model/token/cost summary and edit tracking
- Codebase structure tree documentation
- `/cancel` command for request cancellation
- `/exit` command and refresh UI command docs/tests
- Dead-code CI checks (`unimport`, `vulture`) in lint workflow
- Unit test for context panel summary

### Changed
- Renamed tamagochi module to slopgotchi
- Side-by-side diff view uses explicit Before/After captions and visible change lane
- Context rail border title set to "Session Inspector" with theme-colored accent
- Reduced core agents main module to 600 lines via helpers extraction
- Updated README interface section and clarified tool execution

### Removed
- Dead tools parsing module (`src/tunacode/tools/parsing/`)

### Fixed
- Pre-commit file-length hook performance
- Chat container tuple write issue

## [0.1.64] - 2026-02-12

### Fixed
- Allow manual compaction below threshold
- Keep streaming updates and remove tint crash path

### Changed
- Updated theme architecture handoff and CSS architecture documentation

## [0.1.63] - 2026-02-12

### Added
- Live integration test for tinyagent alchemy usage contract (`tests/integration/core/test_tinyagent_alchemy_usage_contract_live.py`)
- Dedicated debug usage/resource lifecycle tracing module (`src/tunacode/core/debug/usage_trace.py`)
- Unit coverage for strict session usage schema loading and resource bar session cost propagation
- Research map documenting TunaCode Rust-only tinyagent migration path (`.claude/metadata/research/2026-02-12-tinyagent-rust-only-migration-map.md`)

### Changed
- Migrated TunaCode agent runtime stream path to tinyagent Rust alchemy stream (`stream_alchemy_openai_completions`)
- Migrated compaction summary generation stream path to tinyagent Rust alchemy stream
- Updated usage model to strict canonical tinyagent contract (`input/output/cache_read/cache_write/total_tokens/cost`)
- Bumped `tiny-agent-os` to `1.1.5`

### Fixed
- Enforced fail-loud behavior when assistant usage payload is missing or violates canonical contract
- Resource bar session cost now reads canonical `session_total_usage.cost.total`

## [0.1.62] - 2026-02-11

### Added
- **Core Agent**: Migrated from pydantic-ai to [tinyagent](https://github.com/alchemiststudios.ai/tinyAgent) as the core agent loop
- **Text Selection**: Added Rich-renderable mouse selection support in chat panels
- **Visual Styling**: SelectableRichVisual for text selection in Rich renderables
- **CSS-Based Theming**: Textual CSS styling system with 5 stylesheet files (panels, theme-nextstep, layout, widgets, modals)
- **NeXTSTEP Theme**: 3D bevel borders with light top/left and dark bottom/right for raised effect
- **Context Management**: Context compaction system with overflow retry capabilities
- **Token Tracking**: OpenRouter token usage tracking for streaming responses
- **Models Registry**: Expanded models_registry.json with full provider catalog and API URL routing
- **Provider Routing**: Native TinyAgent `OpenRouterModel(base_url)` for provider API URL routing

### Changed
- **BREAKING**: Agent session persistence uses dict messages only - existing sessions may not load correctly
- **BREAKING**: Tool execution is now sequential (was parallel via custom orchestrator)
- Replaced Rich Panel wrappers with CSS-based PanelMeta pattern
- Agent creation now constructs tinyagent.Agent with AgentOptions
- Revamped theme architecture with CSS variable-based theming system
- Updated layout, panels, and widget styles for improved visual consistency
- Bumped tiny-agent-os to v1.1.3 (includes Rust bindings)

### Removed
- Orchestrator and tool dispatcher components (tinyagent handles tool execution)
- Streaming components (pydantic-ai specific)
- Tool executor (tinyagent owns tool execution)
- pydantic-ai dependency (replaced with tiny-agent-os)

### Fixed
- Restored status bar content row with top bevel

## [0.1.61] - 2026-02-06

### Added
- End-to-end tests for mtime-driven caches
- Typed cache accessors for agents, context, and ignore manager
- Strict cache infrastructure with strategies

### Changed
- Migrated remaining lru_cache caches into CacheManager layer
- Refactored agent_config to use typed cache accessors
- Cache accessor now used for ignore manager; removed global ignore cache
- Reduced McCabe complexity to ≤10 for 14 functions
- Reduced cognitive complexity of 13 functions to under 10
- Re-enabled Ruff mccabe complexity check (max 10)

### Fixed
- Satisfied pre-commit dead code checks
