# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Core Agent**: Migrated from pydantic-ai to [tinyagent](https://github.com/alchemiststudios.ai/tinyAgent) as the core agent loop
- **Text Selection**: Copy-on-select functionality - automatically copies highlighted text to clipboard on mouse release
- **Visual Styling**: SelectableRichVisual for text selection in Rich renderables
- **CSS-Based Theming**: Textual CSS styling system with 5 stylesheet files (panels, theme-nextstep, layout, widgets, modals)
- **NeXTSTEP Theme**: 3D bevel borders with light top/left and dark bottom/right for raised effect
- **Cache Infrastructure**: CacheManager singleton with typed accessors for agents, context, ignore manager, ripgrep, and XML prompts
- **Cache Strategies**: MtimeStrategy for file-based cache invalidation (AGENTS.md, .gitignore, XML prompts)
- **Testing**: End-to-end tests for mtime-driven caches
- **Context Management**: Context compaction system with overflow retry capabilities
- **Token Tracking**: OpenRouter token usage tracking for streaming responses
- **UI Components**: Theme variable contract tests and architecture documentation

### Changed
- **BREAKING**: Agent session persistence uses dict messages only - existing sessions may not load correctly
- **BREAKING**: Tool execution is now sequential (was parallel via custom orchestrator)
- Replaced Rich Panel wrappers with CSS-based PanelMeta pattern
- Migrated all lru_cache decorators to CacheManager layer with typed accessors
- Agent creation now constructs tinyagent.Agent with AgentOptions
- Revamped theme architecture with CSS variable-based theming system
- Updated layout, panels, and widget styles for improved visual consistency

### Removed
- Orchestrator and tool dispatcher components (tinyagent handles tool execution)
- Streaming components (pydantic-ai specific)
- Tool executor (tinyagent owns tool execution)
- Token pruning/compaction features
- Rolling summaries
- Parallel tool execution support
- pydantic-ai dependency (replaced with tiny-agent-os==1.1.0)

### Fixed
- Satisfied pre-commit dead code checks
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
