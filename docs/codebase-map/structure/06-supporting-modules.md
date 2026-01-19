---
title: Supporting Modules
path: tunacode
type: directory
depth: 1
description: Indexing, LSP, services, types, utilities, and tutorials
seams: [indexing, lsp, services, types, utils, tutorial, prompts, templates]
---

# Supporting Modules (`src/tunacode/*`)

## Where
Various directories at `src/tunacode/` providing auxiliary functionality.

## What
This document covers the **supporting modules** that enable core TunaCode functionality:
- **`indexing/`** - Code indexing and search infrastructure
- **`lsp/`** - Language Server Protocol client
- **`services/`** - External service integrations
- **`types/`** - Centralized type definitions
- **`utils/`** - General utility functions
- **`tutorial/`** - Interactive tutorial system
- **`prompts/`** - Prompt template library
- **`templates/`** - Code generation templates
- **`tools_utils/`** - Shared tool utilities

## Module Details

### Indexing Module (`src/tunacode/indexing/`)
**Purpose**: Fast code search and navigation.

**Capabilities**:
- Build code indices for project repositories
- Symbol definitions and references tracking
- File content caching for quick access
- Search optimization for large codebases
- Integration with agent context system

**Use Cases**:
- Agent needs to find all usages of a function
- Quick lookup of class definitions
- File discovery by pattern matching
- Context gathering for code analysis

### LSP Module (`src/tunacode/lsp/`)
**Purpose**: Language Server Protocol integration for IDE features.

**Capabilities**:
- Connects to LSP servers (pylsp, gopls, etc.)
- Provides diagnostics (errors, warnings)
- Code completion and hover information
- Symbol navigation (go to definition)
- Refactoring support

**Use Cases**:
- Real-time error detection while coding
- Rich context about code symbols
- Navigation assistance for agents
- Enhanced code understanding

### Services Module (`src/tunacode/services/`)
**Purpose**: External service integrations.

**Capabilities**:
- Git operations (status, diff, commit)
- HTTP client for web requests
- File system watching
- Process management
- Cloud API integrations

**Use Cases**:
- Agent needs to check git status
- Fetching resources from URLs
- Monitoring file changes
- Managing background processes

### Types Module (`src/tunacode/types/`)
**Purpose**: Centralized type definitions.

**Contents**:
- Common type aliases (`FilePath`, `ErrorMessage`, `ToolName`)
- Protocol definitions for interfaces
- TypedDict models for structured data
- Enum definitions for constants

**Benefits**:
- Type consistency across modules
- Single source of truth for common types
- Enhanced IDE autocomplete
- Easier refactoring

### Utils Module (`src/tunacode/utils/`)
**Purpose**: Shared utility functions.

**Subdirectories**:
- **`config/`**: Configuration parsing and validation
- **`messaging/`**: Message formatting and display
- **`parsing/`**: Text parsing and tokenization
- **`system/`**: System operations (paths, processes)
- **`ui/`**: UI-specific utilities

**Utilities**:
- Path manipulation helpers
- String formatting and truncation
- Process spawning and monitoring
- Color and formatting helpers

### Tutorial Module (`src/tunacode/tutorial/`)
**Purpose**: Interactive onboarding and education.

**Contents**:
- Tutorial lessons and exercises
- Interactive examples
- Progress tracking
- Achievement system

**Features**:
- Guided introduction to TunaCode
- Hands-on coding exercises
- Best practices demonstration
- Concept explanations

### Prompts Module (`src/tunacode/prompts/`)
**Purpose**: Prompt template library.

**Structure**:
```
prompts/
├── research/
│   └── sections/        # Research prompt components
└── sections/            # General prompt components
```

**Contents**:
- System prompts for different agent types
- Task-specific prompt templates
- Injection templates for context
- Prompt composition helpers

**Use Cases**:
- Agent system messages
- Code analysis prompts
- Task-specific instructions
- Context formatting

### Templates Module (`src/tunacode/templates/`)
**Purpose**: Code generation templates.

**Contents**:
- Project scaffolding templates
- File templates for different languages
- Code pattern templates
- Configuration file templates

**Use Cases**:
- Bootstrapping new projects
- Generating boilerplate code
- Consistent file structure
- Best practices enforcement

### Tools Utils (`src/tunacode/tools_utils/`)
**Purpose**: Shared utilities for tool implementations.

**Contents**:
- Common tool helper functions
- Shared validation logic
- Tool result formatting
- Error handling utilities

**Benefits**:
- DRY principle for tool code
- Consistent tool behavior
- Simplified tool development
- Centralized tool logic

## Integration Patterns

### Type System
All modules import from `tunacode.types` for consistent typing:
```python
from tunacode.types import FilePath, ErrorMessage, ToolName
```

### Exception Handling
All modules raise exceptions from `tunacode.exceptions`:
```python
from tunacode.exceptions import ToolExecutionError, ValidationError
```

### Constants
All modules use constants from `tunacode.constants`:
```python
from tunacode.constants import MAX_FILE_SIZE, TIMEOUT_SECONDS
```

## Why
**Modularity**: Supporting modules are kept separate for clear organization:
- **Testability**: Each module can be tested independently
- **Maintainability**: Clear boundaries prevent coupling
- **Reusability**: Utilities can be used across the codebase
- **Discoverability**: Easy to locate specific functionality

**Design Principles**:
1. **Single Responsibility**: Each module has one clear purpose
2. **Dependency Direction**: Higher-level modules depend on lower-level
3. **Interface Segregation**: Modules expose minimal interfaces
4. **Dependency Injection**: Modules receive dependencies via parameters

## Code Quality Notes
- **Type Hints**: All modules fully typed
- **Documentation**: Docstrings explain public APIs
- **Testing**: Comprehensive test coverage
- **Linting**: Passes ruff checks
- **Performance**: Efficient algorithms and data structures
