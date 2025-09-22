# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-09-22

### Added
- **Enhanced File Reference Completion** - Fuzzy-first matching for @mentions with smart directory browsing
- **Fuzzy CLI Command Matching** - CLI suggests closest commands when no exact/prefix match
- **Models Registry Pydantic Conversion** - Complete conversion to Pydantic BaseModel with validation
- **RAG Tooling** - SQLite FTS5 index for .claude/ knowledge base search and indexing
- **Comprehensive Validation Tests** - Added golden baseline tests and validation edge cases

### Changed
- **File Reference Ordering** - New priority: exact files > fuzzy files > exact dirs > fuzzy dirs
- **Bare Directory Browsing** - Type `@dir` (without trailing slash) to browse directory contents
- **Code Style Guidelines** - Updated CLAUDE.md with improved coding patterns and best practices
- **Models Registry Validation** - Added constraints for non-negative costs and positive limits

### Fixed
- **Unused Import Removal** - Removed unused Iterable import from fuzzy_utils.py
- **Validation Edge Cases** - Enhanced registry validation for model loading scenarios

## [0.0.76.2] - 2025-09-19

### Added
- **React Tool Auto-Snapshot System** - Comprehensive refactoring with automatic snapshot every 2 iterations (max 5)
- **ReAct Shim Support** - Added metadata, semantic indexing, and memory anchors for ReAct coordination
- **Enhanced Session State** - Added react_forced_calls counter and react_guidance tracking
- **Model-Friendly Documentation** - Created comprehensive component documentation in .claude/docs_model_friendly/

### Changed
- **React Tool Integration** - Removed from registered tool list, now forced automatically with LLM guidance injection
- **Repository Structure** - Removed redundant agents.md submodule and restructured TODO.md
- **Agent Configuration** - Enhanced context loading with react_guidance injection and system prompt updates

### Fixed
- **React Scratchpad Consistency** - Ensured consistent maintenance without requiring explicit LLM tool selection
- **Documentation Clarity** - Improved readability and removed confusing submodule references

## [0.0.76] - 2025-09-12

### Added
- Implemented enum-based state machine for agent completion detection
- Added comprehensive CLI tool testing framework
- Enhanced agent loop architecture with robust state transition validation
- Created memory-bank plan and research files for configuration dashboard

### Changed
- Enhanced model selection with auto-persistence to user config
- Improved setup wizard with actionable configuration validation guidance
- Extracted wizard to separate module for better code organization
- Updated documentation with model selection info and quickstart guide

### Fixed
- Fixed model selection persistence across all selection methods
- Improved error handling for configuration permissions
- Enhanced UX with clear success/error messaging for model operations
- Fixed test assertions to match updated system prompt text

## [0.0.75] - 2025-09-12

### Changed
- Removed fallback PyPI auth method from CI workflow
- Bumped version to 0.0.75

### Fixed
- Fixed version check in CI pipeline
- Updated publish workflow constants for version 0.0.73

## [0.0.74] - 2025-09-11

### Added
- Implemented enum-based state machine for agent completion detection
- Added Claude command executor documentation and test guides

### Changed
- Enhanced agent loop architecture

## [0.0.73] - 2025-09-11

### Changed
- Made tool strict validation configurable in tunacode.json
- Enhanced /model command with multi-source routing and models.dev integration

### Fixed
- Added strict=False parameter to Tool constructors to prevent validation issues
- Replaced invalid bright_white with ansiwhite in model selector
- Updated model command tests to match new models.dev integration behavior

## [0.0.72] - 2025-09-10

### Changed
- Refactored agent and command documentation structure
- Improved wizard UX and fixed API key loading

### Fixed
- Prevent crash when API key is missing for configured model
- Prevent config reset on startup by loading config before initialization

## [0.0.71] - 2025-08-25

### Added
- Comprehensive TunaCode tool system documentation
- Local models configuration guide

### Changed
- Refactored tool system and cleaned up obsolete tools
- Excluded llm-agent-tools from pre-commit hooks and file checks

## [0.0.70] - 2025-08-23

### Added
- Enhanced /update command with UV tool installation support
- Improved venv detection for UV-created environments
- Added emoji prohibition to system prompt

### Changed
- Changed default model to OpenRouter GPT-4.1
- Migrated to UV for dependency management with Hatch integration
- Enhanced install script with config file creation and setup guidance

### Fixed
- Improved venv installation detection for /update command
- Added defusedxml dependency and fixed typer compatibility

## [0.0.69] - 2025-08-21

### Summary
This release includes comprehensive command system documentation, updated model configurations, and builds upon recent community contributions including the slash command system by @Lftobs (#85) and onboarding improvements by @ryumacodes (#88).

### Changed
- Updated OpenRouter GPT model reference from `gpt-4o` to `gpt-4.1` in setup configuration

### Added
- Additional development documentation in `.claude/` directory
  - Model updates documentation
  - Slash commands documentation
  - Onboarding improvements documentation

## [0.0.68] - 2025-08-21

### Added
- **Comprehensive Command System Documentation**
  - Created `command-system-architecture.md` with technical overview of command infrastructure
  - Created `creating-custom-commands.md` with step-by-step guide for developers
  - Updated user documentation with slash command information
  - Added `/command-reload` command documentation

### Fixed
- Removed broken link to non-existent `templates.md` file in documentation

## [0.0.67] - 2025-08-14

### Added
- Added UV tool installation support to /update command
- Added venv manual update option to error message
- Added emoji prohibition to system prompt

### Fixed
- Improved venv detection for UV-created environments
- Added venv installation detection for /update command

## [0.0.66] - 2025-08-14

### Fixed
- Replaced aggressive retry messaging with constructive guidance

## [0.0.65] - 2025-08-14

### Added
- Implemented robust uninstall script with comprehensive detection
- Implemented robust update logic for Linux installer

### Changed
- Changed default model to OpenRouter GPT-4.1
- Enhanced install script with config file creation and setup guidance

### Fixed
- Added missing print helper functions to install script

## [0.0.64] - 2025-08-14

### Added
- Implemented UV and Hatch support to installation scripts
- Added comprehensive UV+Hatch setup documentation

### Changed
- Migrated to UV for dependency management
- Optimized pre-commit hooks for Hatch+UV integration

### Fixed
- Properly configured Hatch with UV installer
- Added defusedxml dependency and fixed typer compatibility

## [0.0.63] - 2025-08-14

### Added
- Phase 5 - Tool Prompt Micro-Injection System

### Fixed
- Fixed agent initialization performance with strategic caching
- Added exception for glob.py in file length check

## [0.0.62] - 2025-08-14

### Added
- **Major Performance Optimizations & JSON Recovery System** (#82)
- Phase 1 - Ripgrep binary management foundation

### Changed
- Complete UV+Hatch integration with dependency fixes

## [Unreleased] - 2025-08-20

### Added

- **Comprehensive Onboarding Experience Improvements** (#88) - Thanks to **@ryumacodes**!
  - Enhanced user onboarding flow and setup experience
  - Improved first-time user guidance and documentation
  - Streamlined installation and configuration process
  - Resolved issue #55

### Recent Pull Requests

- **Slash Command System for Custom Automation Workflows** (#85) - Thanks to **@Lftobs**!
  - Implemented flexible slash command infrastructure
  - Enabled custom automation workflows
  - Extended CLI capabilities with user-defined commands

- **User Documentation and README Index** (#83) - Thanks to **@MclPio**!
  - Added comprehensive user documentation
  - Updated main README with organized index
  - Improved documentation structure and accessibility

### Contributors

Special thanks to our recent contributors:
- **@ryumacodes** - Onboarding improvements and multiple feature implementations
- **@Lftobs** - Slash command system and workflow automation
- **@MclPio** - Documentation improvements and organization
