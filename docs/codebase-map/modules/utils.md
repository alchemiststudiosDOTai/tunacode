---
title: Utils Module
path: src/tunacode/utils
type: directory
depth: 1
description: Shared utility functions and helpers
exports: [estimate_tokens, parse_json]
seams: [M]
---

# Utils Module

## Purpose
Provides shared utility functions across configuration, messaging, parsing, and system operations.

## Key Components

### Configuration (utils/config/)

**user_configuration.py**
- User config file loading
- Config directory management
- Default value handling
- Config validation

### Messaging (utils/messaging/)

**adapter.py**
- Canonical message conversions (to/from canonical)
- **get_content()** - Content extraction for dicts and canonical messages
- Tool call ID extraction helpers

**token_counter.py**
- **estimate_tokens()** - Token counting for messages
- Supports multiple models (Claude, GPT, etc.)
- Used for context window management

### Parsing (utils/parsing/)

**json_utils.py**
- **parse_json()** - Robust JSON parsing
- Handles malformed JSON
- Provides error messages

**command_parser.py**
- Command string parsing
- Argument extraction
- Command validation

**tool_parser.py**
- Tool call parsing from text
- Argument extraction
- Tool name resolution

**retry.py**
- Retry logic with exponential backoff
- Max retry configuration
- Error handling

### System (utils/system/)

**ignore_patterns.py**
- Shared ignore pattern list for tools and UI
- **is_ignored()** - Pattern matching helper for filesystem traversal

**gitignore.py**
- .gitignore pattern matching
- File filtering based on ignore rules
- Gitignore parsing

**paths.py**
- Path manipulation utilities
- Absolute/relative path conversion
- Path validation

### UI (utils/ui/)

**file_filter.py**
- File filtering for UI components
- Pattern-based filtering
- Extension filtering

**helpers.py**
- UI-specific helper functions
- Text formatting
- Display utilities

## Utility Categories

### Configuration Utilities
- Config loading and merging
- Default value resolution
- Config validation

### Messaging Utilities
- Token estimation
- Content extraction
- Canonical message conversion

### Parsing Utilities
- JSON parsing
- Command parsing
- Tool call parsing
- Retry logic

### System Utilities
- Gitignore integration
- Path manipulation
- File system operations

### UI Utilities
- File filtering
- Text formatting
- Display helpers

## Integration Points

- **core/agents/** - Token counting, message parsing
- **tools/** - JSON parsing
- **ui/** - File filtering, path handling
- **configuration/** - Config loading

## Seams (M)

**Modification Points:**
- Add new parsing utilities
- Create new system helpers
- Add UI formatting functions

**Best Practices:**
- Keep utilities pure (no side effects)
- Provide clear error messages
- Handle edge cases gracefully
- Document complexity
