# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- **Text Selection**: Copy-on-select functionality - automatically copies highlighted text to clipboard on mouse release
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
