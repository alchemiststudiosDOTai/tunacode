# Context Characterization Tests

This directory contains characterization tests for AGENTS.md context loading and injection functionality.

## Test Files

- `test_context_acceptance.py` - High-level acceptance tests for context injection (currently skipped due to pydantic_ai stubbing): Edit fixed? need to open a issue but I AM COOKED time wise
- `test_context_integration.py` - Integration tests verifying context loading and agent creation
- `test_context_loading.py` - Unit tests for context loading edge cases and behaviors

## Key Test Scenarios

### Context Loading
- Walking up directory tree to find AGENTS.md files
- Handling empty and malformed files
- Loading large context files
- Merging multiple AGENTS.md files from parent directories

### Agent Integration
- Agent loads AGENTS.md on creation
- Context is appended to system prompt
- Graceful handling when AGENTS.md is missing
- Sync file I/O to avoid event loop issues

## Related Components
- `/init` command tests are in `../commands/test_init_command.py`
- Main implementation in `src/tunacode/core/agents/main.py`
- Context utilities in `src/tunacode/context.py`
