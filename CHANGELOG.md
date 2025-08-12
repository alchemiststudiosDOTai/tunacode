# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Performance

- **Directory Caching System**: Implemented intelligent directory caching using CodeIndex infrastructure
  - Added singleton pattern to CodeIndex with public API and cache freshness tracking
  - Background pre-warming of directory cache during REPL startup (non-blocking)
  - Smart `list_dir` tool integration with CodeIndex cache lookup
  - **50-500x faster** directory operations for cached paths (0.0001s vs 10-200ms)
  - Graceful fallback to filesystem scanning when cache unavailable
  - Automatic cache invalidation with 5-second TTL
  - Memory efficient: ~1-5MB overhead for typical projects

- **System Prompt Caching**: Added file-based caching for system prompts and TUNACODE.md
  - **9x faster** system prompt loading with modification time checking
  - **3-8 second reduction** in agent initialization time
  - Zero-risk automatic cache invalidation on file changes

### Documentation

- Added comprehensive performance optimization documentation
- Created detailed technical documentation for directory caching system
- Updated documentation index with performance optimization guides

## [0.0.56] - 2025-08-11

### Added

- **Plan Mode**: New read-only research phase for implementation planning (#81) - Thanks to **ryumacodes**!
  - `/plan` command to enter Plan Mode for research and planning
  - `/exit-plan` command to manually exit Plan Mode
  - `present_plan` tool for structured plan presentation with user approval
  - Visual indicators in status bar, input prompt, and placeholder text
  - Tool restrictions - only read-only tools available in Plan Mode
  - Shift+Tab keyboard shortcut to toggle Plan Mode
  - Clean UI with "⏸ PLAN MODE ON" indicator above input

### Changed

- **BREAKING**: Migrated from Makefile to Hatch for cross-platform compatibility - Thanks to **ryumacodes**!
- Modified CLI commands processing
- Updated REPL functionality
- Enhanced output display formatting
- Refactored main.py to reduce file size from 691 to 447 lines
- Improved ESC key handling with double-press safety and unified abort behavior
- Added comprehensive ESC key investigation documentation

### Fixed

- Restored Thinking dots animation with faster timing

### Migration Guide

**Makefile → Hatch Command Migration:**

| Old Command | New Command | Notes |
|-------------|-------------|--------|
| `make install` | `hatch run install` | Install dev dependencies |
| `make run` | `hatch run run` | Run TunaCode CLI |
| `make clean` | `hatch run clean` | Clean build artifacts |
| `make lint` | `hatch run lint` | Run linting and formatting |
| `make test` | `hatch run test` | Run test suite |
| `make coverage` | `hatch run coverage` | Run tests with coverage |
| `make build` | `hatch build` | Build distribution packages |
| `make vulture` | `hatch run vulture` | Dead code analysis |
| `make remove-playwright-binaries` | `hatch run remove-playwright` | Remove Playwright cache |

**Benefits:**
- Windows compatibility without WSL or MinGW
- No external make dependency required
- Better Python ecosystem integration
- Consistent cross-platform behavior

### Fixed

- ESC key double-press safety restoration
- Unified ESC and Ctrl+C abort handling in REPL
- Pre-commit hook configuration for file length checks

### Contributors

Special thanks to our community contributors:
- **mohaidoss** - ESC key interrupt functionality (#29)
- **MclPio** - Token cost tracking feature (#17)
- **prudentbird** - Context window management (#17)
- **Lftobs** - Todo tool functionality and @-file-ref enhancements (#17, #2)
- **ColeMurray** - Security fix for B108 vulnerability (#25)
- **ryumacodes** - Plan Mode implementation (#81), Hatch migration for cross-platform support, and RuntimeWarnings fix (#71)

## [0.0.55] - 2025-08-08

### Added
- Activity indicator with animated dots during operations
- Spinner update infrastructure for better tool execution status feedback

### Changed
- Simplified type hint for asyncio.Task in StreamingAgentPanel
- Extracted truncation checking to separate module (node_processor.py reduced to 438 lines)

### Fixed
- JSON string args handling in get_tool_description call
- Debug print statements causing console pollution
- Dynamic spinner messages by keeping spinner running during tool execution

## [0.0.54] - 2025-08-08

### Fixed
- Made publish script idempotent and handle partial completions
- Moved cleanup section after version calculation in publish script

## [0.0.23] - 2025-01-06

### Added

- Fallback response handling for agent iterations

## [0.0.22] - 2025-01-06

### Added

- Control-C handling improvements for smooth exit

## [0.0.21] - 2025-01-06

### Fixed

- Various bug fixes and improvements

## [0.0.19] - 2025-01-06

### Added

- Orchestrator features with planning visibility
- Background manager implementation

### Changed

- Updated README with orchestrator features
- System prompt updates

## [0.0.18] - 2025-01-05

### Fixed

- Circular import in ReadOnlyAgent
- Orchestrator integration to use TunaCode's LLM infrastructure

## [0.0.17] - 2025-01-05

### Changed

- General codebase cleanup

## [0.0.16] - 2025-01-05

### Fixed

- Publish script to use temporary deploy venv
- Improved .gitignore

## [0.0.15] - 2025-01-05

### Added

- Shell command support with `!` prefix
- Updated yolomode message

### Fixed

- Escape-enter keybinding test

## [0.0.14] - 2025-01-04

### Changed

- Various improvements and bug fixes

## [0.0.13] - 2025-01-04

### Changed

- Initial stable release with core features
