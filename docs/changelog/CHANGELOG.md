# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Escape key to interrupt running tasks (PR #67) - @mohaidoss
- Recursive task execution feature (PR #53) - @larock22

### Fixed
- Correct pip upgrade command in setup script (PR #70) - @larock22
- Enhanced setup script robustness and improved documentation (PR #69) - @larock22

## [0.0.41] - 2025-01-17

### Added
- Token usage and cost tracking system (PR #45) - @MclPio
- Enhanced todo management with timestamp IDs and validation (PR #50) 
- Todo management functionality (PR #49) - @Lftobs
- Context window management with tiktoken-based token counting (PR #47) - @prudentbird

### Fixed
- Todo feature improvements with timestamp-based IDs and better validation
- High-priority code quality issues post-PR merge
- Test failures after token tracking PR merge

### Changed
- Applied ruff formatting and fixed linting errors
- Removed unused tool confirmation functions and cleaned up interfaces
- Flattened complex nested logic in REPL using TDD
- Removed textual UI components and cleaned up emoji usage

### Development
- Improved code quality and maintainability
- Enhanced parallel execution optimizations for read-only tools
- Better error handling and fallback mechanisms

### Contributors
Special thanks to all contributors for this release:
- @MclPio - Token usage and cost tracking implementation
- @Lftobs - Todo management functionality 
- @prudentbird - Context window management with tiktoken integration

## [0.0.37] - 2025-06-27

### Added

- **Streaming-first UI with token-level display** (#41)
  - Real-time character-by-character display using pydantic-ai's streaming API
  - Rich.Live integration for smooth progressive updates with proper UI coordination
  - Graceful handling of spinner conflicts during streaming
  - New `/streaming` command to toggle streaming on/off
  - Backward compatibility with graceful fallback for older pydantic-ai versions
  - Streaming enabled by default for better user experience
  - Token streaming hooks into pydantic-ai's `is_model_request_node()` mechanism
  - Chunk fallback when token streaming is unavailable
  - New `StreamingAgentPanel` class in `ui/panels.py`
  - Enhanced `process_request()` to support streaming callbacks with token deltas
  - Benefits: Immediate visual feedback during LLM generation, modern UX, responsive interface

## [0.0.35] - 2025-06-25

### Security

- **Critical Security Fix**: Resolved subprocess shell injection vulnerabilities
  - Fixed `subprocess.Popen(shell=True)` vulnerability in `run_command.py` - agent commands now validated for security
  - Fixed `subprocess.run(shell=True)` vulnerability in `repl.py` - user shell commands now validated
  - Created comprehensive security utilities module (`utils/security.py`) with:
    - Command validation with dangerous pattern detection (rm -rf /, sudo rm, disk operations, fork bombs)
    - Safe subprocess wrappers with configurable validation levels
    - Input sanitization using `shlex.quote()`
    - Security logging for all command executions
  - Added complete security test suite (12 tests) covering command injection scenarios
  - Integrated security tests into `make test` command for continuous protection
  - Benefits: Prevents command injection attacks while preserving CLI functionality

- **Fixed B108 security issue** in `read_file_async_poc.py`
  - Replaced hardcoded `/tmp/test_file_{i}.txt` paths with secure `tempfile.NamedTemporaryFile()`
  - Added proper error handling for file cleanup operations
  - Applied Python best practices: using `_` for unused loop variables and `contextlib.suppress()`

### Changed

- **Refactored commands.py into modular package structure**
  - Split monolithic 877-line file into 9 focused modules (largest: 222 lines)
  - Organized commands by logical categories: system, debug, development, model, conversation
  - All files now comply with 500-line limit for better maintainability
  - Maintained full backward compatibility - existing imports still work
  - Benefits: Easier navigation, cleaner git diffs, better testing isolation

## [0.0.34] - 2025-06-22

### Added

- **Context Loading for TUNACODE.md**: Agent now automatically loads project-specific context from TUNACODE.md files
  - Implemented synchronous context injection to avoid event loop issues
  - Context is appended to system prompt on agent creation
  - Handles missing/malformed TUNACODE.md files gracefully
  - Created comprehensive test suite for context injection functionality
  - Benefits: AI assistant now understands project-specific conventions and guidelines automatically

- **Comprehensive characterization tests** for file operations
  - Created extensive test suite achieving high coverage across core tools
  - Added tests for ReadFileTool, WriteFileTool, UpdateFileTool, BashTool, GrepTool, ListDirTool
  - Test coverage: 91% read_file, 89% write_file, 75% bash, 71% update_file
  - Created detailed test plan documentation (CHARACTERIZATION_TEST_PLAN.md)
  - Benefits: Enables safe refactoring with comprehensive regression prevention

### Fixed

- **Configuration persistence bug** when using CLI flags
  - Fixed issue where JSON config file failed to save when `~/.config` directory didn't exist
  - `save_config` function now creates the config directory with proper permissions (0o700) if missing
  - Replaced silent failure with proper error handling that raises ConfigurationError with meaningful messages
  - Updated all callers to handle ConfigurationError exceptions appropriately
  - Added comprehensive tests for directory creation and error scenarios
  - Benefits: Users can now use `tunacode --model "provider:model" --key "api-key"` reliably

## [0.0.33] - 2025-06-21

### Changed

- **Increased default iteration limits** for more complex reasoning tasks
  - Default max_iterations increased from 20 to 40
  - Maximum allowed iterations via `/iterations` command increased from 50 to 100
  - Fixed outdated fallback value (15 → 40) in iterations command display
  - Benefits: Allows AI to handle more complex multi-step tasks without hitting limits

### Added

- Comprehensive characterization tests for iteration limits behavior
- Characterization tests for tool UI behavior capturing read-only tool optimizations

### Fixed

- Aligned all iteration limit defaults across the codebase
  - Updated defaults.py, main.py, and commands.py to use consistent values
  - Fixed discrepancy where commands.py showed 15 as default instead of the actual default

## [0.0.32] - 2025-06-20

### Fixed

- Cleaned up root directory by removing 100+ test files
  - Removed performance test files (perf_test_*.txt)
  - Removed test plan markdown files from root
  - Removed test api/components directories from src
  - Removed various test files (file*.txt, module_*.py, etc.)
  - Kept all legitimate test files in tests/ directory

## [0.0.31] - 2025-06-19

### Added

- New `list_dir` tool for efficient directory listing
  - Uses `os.scandir` for better performance than shell commands
  - Supports pagination with configurable max entries (default 200)
  - Shows file type indicators (/, *, @, ?)
  - Sorts results with directories first, then files alphabetically
  - Optional hidden file display with `show_hidden` parameter
  - Graceful permission error handling
  - Provides a fallback when bash commands aren't available

- System prompt optimizations for better parallel execution
  - Updated prompt to encourage 3-4 tool batches for optimal performance
  - Added clear examples showing why 3-4 tools is the sweet spot
  - Explained performance benefits: balances speed with cognitive load
  - Added "Why 3-4 Tools is Optimal" section with real-world timing examples

### Changed

- **Major Performance Improvement**: Made parallel tool execution truly asynchronous
  - Added `asyncio.to_thread()` to `read_file` and `list_dir` tools to prevent blocking the event loop
  - File operations now run in separate threads, enabling genuine parallel execution
  - Achieved 3-5x performance improvement for multiple file operations
  - Tests confirm multiple threads are used and operations run concurrently
  - Zero breaking changes - just 4 lines of code modified
  - Benefits: 3x faster file reads, non-blocking I/O, better responsiveness
  
  ![Parallel Execution Performance](../assets/parrelel_work_3x.png)

- Refactored command structure to use declarative class-level metadata
  - Modified `SimpleCommand` base class to read properties from class-level `spec` attribute
  - Removed unnecessary `__init__` methods from 11 SimpleCommand subclasses
  - Commands now define their metadata declaratively as class attributes
  - Special handling preserved for `HelpCommand` and `CompactCommand` which require dependency injection
  - Benefits: Cleaner code, better readability, reduced boilerplate

### Removed

- Dead code cleanup in commands system
  - Removed `TunaCodeCommand` class (57 lines) - a fully implemented but disabled BM25 search feature
  - Removed associated TODO comment for the disabled command

## [0.0.30] - 2025-06-14

### Added

- File context visibility improvements
  - Files in context now always display after agent responses (not just when thoughts mode is enabled)
  - Shows only filenames for better readability instead of full paths
  - Tracks files referenced with @ syntax alongside files read through tools
- Enhanced `/thoughts` command display
  - Simplified tool arguments display for common file operations
  - Shows "Reading: filename.py" instead of full JSON for read_file tool
  - Truncates long commands to 60 characters for better readability
  - Maintains detailed JSON display for other tools
  - Added token counting for model responses

### Fixed

- Fixed error when tool arguments were strings instead of dictionaries
- Improved error handling for non-standard tool argument formats
- Fixed aggressive file writing when using @ file references
  - Added clear "FILE REFERENCE" headers to distinguish referenced content from code to write
  - Updated system prompt to understand @ syntax is for providing context, not for file creation
  - Changed model behavior from "TOOLS FIRST, ALWAYS" to "UNDERSTAND CONTEXT" for better interpretation
- Fixed "string indices must be integers" error in fallback responses
  - Improved AgentRunWrapper attribute resolution to properly handle result attribute conflicts
  - Used __getattribute__ instead of __getattr__ to ensure correct attribute precedence
  - Prevents errors when agent reaches max iterations and generates fallback response

## [0.0.29] - 2025-12-06

### Added

- Comprehensive fallback response mechanism when agent reaches maximum iterations without user response (#22)
  - Response state tracking across all agent types (main agent, readonly agent, orchestrator)
  - Configurable fallback verbosity levels (minimal, normal, detailed)
  - Context extraction showing tool calls, files modified, and commands run in fallback responses
- Configuration option `fallback_response` to enable/disable fallback responses
- Automatic synthesis of incomplete task status when max iterations reached

### Fixed

- Orchestrator bug where fallback responses appeared even when tasks produced output (#22)
- Response state tracking to ensure fallback only triggers when no user-visible output exists

### Changed

- Improved fallback response mechanism to handle edge cases across different agent types

## [0.0.28] - 2025-06-08

### Added

- Enhanced `/compact` command with summary visibility:
  - Displays AI-generated summary in a cyan-bordered panel before truncating
  - Shows message count before and after compaction
  - Improved summary extraction logic supporting multiple model response formats
- Streamlined documentation structure:
  - Created FEATURES.md for complete feature reference
  - Created ARCHITECTURE.md for technical details
  - Created DEVELOPMENT.md for contributing guidelines
  - Created ADVANCED-CONFIG.md for detailed configuration

### Changed

- `/compact` command now shows what was summarized instead of operating silently
- README streamlined to focus on quick installation and basic usage
- Moved detailed documentation to separate files for better organization

## [0.0.27] - 2025-06-08

### Changed

- Modified CLI commands processing
- Updated REPL functionality
- Enhanced output display formatting

## [0.0.26] - 2025-01-07

### Fixed

- Resolved 'property result of AgentRun object has no setter' error

## [0.0.25] - 2025-01-07

### Fixed

- Prevent agent from creating files in /tmp directory

## [0.0.24] - 2025-01-07

### Added

- Demo gif to README

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
