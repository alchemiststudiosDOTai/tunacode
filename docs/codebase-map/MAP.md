# TunaCode Codebase Map

**Generated:** 2026-01-04
**Project:** TunaCode - TUI Code Agent
**Source Directory:** src/tunacode/
**Version:** 0.1.20
**Python Version:** 3.11-3.13

---

## Statistics

| Metric | Value |
|--------|-------|
| Total Python files analyzed | 134 |
| Documentation files generated | 28 |
| Documentation size | ~196 KB |
| SEAMS analysis dimensions | Structure, Architecture, Modules, State |
| Analysis depth | 0 (root-level) |
| Analysis tool | Gemini MCP (gemini-2.5-flash, gemini-2.5-pro) |

---

## Structure Overview

```
src/tunacode/
├── ui/                     # Presentation layer (Textual TUI)
│   ├── app.py             # Main TextualReplApp
│   ├── screens/           # Modal dialogs (setup, picker, confirm)
│   ├── widgets/           # Custom widgets (Editor, ResourceBar)
│   ├── renderers/         # Output formatting (tools, panels)
│   ├── commands/          # UI command handlers (/help, /model)
│   ├── headless/          # Non-interactive mode
│   └── styles/            # CSS and theming
│
├── core/                   # Agent orchestration & business logic
│   ├── agents/            # AI agent implementations
│   │   ├── main.py        # Primary agent (process_request)
│   │   ├── research_agent.py
│   │   └── agent_components/
│   │       ├── agent_config.py     # get_or_create_agent()
│   │       ├── node_processor.py   # Response processing
│   │       ├── tool_executor.py    # Parallel execution
│   │       └── state_transition.py # Agent state machine
│   ├── state.py           # StateManager, SessionState
│   ├── prompting/         # Prompt construction
│   ├── setup/             # Setup wizard
│   ├── background/        # Async tasks
│   └── token_usage/       # Cost tracking
│
├── tools/                  # Agent capabilities & system interactions
│   ├── bash.py            # Shell execution
│   ├── grep.py            # Content search (smart/ripgrep/python)
│   ├── glob.py            # File pattern matching
│   ├── read_file.py       # File reading
│   ├── write_file.py      # File creation
│   ├── update_file.py     # File editing (fuzzy matching)
│   ├── list_dir.py        # Directory listing
│   ├── web_fetch.py       # HTTP requests
│   ├── react.py           # ReAct pattern support
│   ├── todo.py            # TODO management
│   ├── decorators.py      # @base_tool, @file_tool
│   ├── authorization/     # Permission system
│   │   ├── handler.py     # ToolHandler
│   │   ├── policy.py      # AuthorizationPolicy
│   │   └── rules.py       # ReadOnly, YoloMode, etc.
│   ├── grep_components/   # Search implementation
│   └── tools_utils/       # Shared utilities
│
├── configuration/          # Settings, models, pricing
│   ├── settings.py        # User preferences
│   ├── models.py          # Model registry
│   ├── models_registry.json
│   ├── pricing.py         # Cost tracking
│   └── defaults.py        # Factory defaults
│
├── cli/                    # Command-line interface
│   ├── commands/          # Slash commands
│   └── repl_components/   # REPL building blocks
│
├── indexing/               # Fast codebase indexing
│   ├── code_index.py      # CodeIndex class
│   └── constants.py       # Indexing thresholds
│
├── lsp/                    # Language Server Protocol client
│   └── client.py          # LSPClient, diagnostics
│
├── services/               # External service integrations
│   └── (currently empty)
│
├── types/                  # Type definitions
│   ├── base.py            # ModelName, ToolName aliases
│   ├── dataclasses.py     # UserConfig, AgentRun
│   ├── state.py           # MessageHistory, ToolArgs
│   └── callbacks.py       # Callback types
│
├── utils/                  # Shared utilities
│   ├── config/            # User configuration loading
│   ├── messaging/         # Token counting, message utils
│   ├── parsing/           # JSON, command parsing
│   ├── security/          # Command validation
│   ├── system/            # Gitignore, paths
│   └── ui/                # File filtering
│
├── templates/              # Template management system
│   └── loader.py          # TemplateLoader
│
├── prompts/                # Modular prompt sections
│   ├── sections/          # agent_role.md, critical_rules.md
│   └── research/sections/ # Research-specific prompts
│
├── tutorial/               # Interactive tutorials
├── tools_utils/            # Shared tool utilities
├── exceptions.py           # Custom exception hierarchy
├── constants.py            # Global constants, UI themes
└── py.typed                # PEP 561 compliance marker
```

---

## Detailed Module Index

### Core Modules

| Module | Purpose | Key Exports | Seams |
|--------|---------|-------------|-------|
| **core/agents** | AI agent orchestration | process_request, RequestOrchestrator, get_or_create_agent | M, D |
| **core/state** | Session state management | StateManager, SessionState | M |
| **core/prompting** | System prompt composition | PromptingEngine, SectionLoader | M, D |
| **ui/** | Textual TUI interface | TextualReplApp, screens, renderers | M, D |
| **tools/** | Agent capabilities | base_tool, file_tool, ToolHandler, bash, grep, read_file | M, D |

### Supporting Modules

| Module | Purpose | Key Exports | Seams |
|--------|---------|-------------|-------|
| **configuration/** | Settings & models | load_user_config, ModelRegistry, get_pricing | M |
| **types/** | Type definitions | UserConfig, MessageHistory, ModelName, ToolCallback | M |
| **utils/** | Shared utilities | estimate_tokens, parse_json, validate_command | M |
| **indexing/** | Fast codebase indexing | CodeIndex, index_files, search_files | M |
| **lsp/** | Language Server Protocol | LSPClient, get_diagnostics | M |
| **templates/** | Template management | TemplateLoader | M |
| **prompts/** | Prompt templates | agent_role.md, critical_rules.md | M |
| **cli/** | Command-line interface | REPL commands, slash commands | M, D |
| **exceptions.py** | Exception hierarchy | TunaCodeError, ToolExecutionError | M |
| **constants.py** | Global constants | UI_COLORS, TOOL_NAMES, themes | M |

---

## SEAMS Summary

### Structure Analysis

The Structure Agent completed a comprehensive **depth 0 analysis** of the TunaCode source code:

**Key Findings:**
- **Layered Architecture**: Clean separation between Presentation (UI/CLI), Business Logic (Core), Capabilities (Tools), and Configuration
- **Modular Organization**: High cohesion, low coupling, single responsibility principle
- **Type Safety**: Full type annotation coverage with centralized type definitions
- **Error Handling**: Rich exception hierarchy with actionable recovery guidance
- **NeXTSTEP Design**: Consistent UI/UX following classic interface guidelines

**Design Patterns Identified:**
1. Agent Pattern (Core) - Specialized agents with delegation
2. Decorator Pattern (Tools) - Cross-cutting concerns via decorators
3. Builder Pattern (Prompting) - Dynamic prompt construction
4. Component Pattern (UI) - Reusable widgets and screens
5. Strategy Pattern (Configuration) - Multiple configuration sources
6. Observer Pattern (UI/Core) - Callback-based communication
7. Composite Pattern (Delegation) - Agents as tools
8. Policy Pattern (Authorization) - Composable authorization rules

### Entry Points

**Primary Entry Point:** `/Users/tuna/Desktop/tunacode/src/tunacode/ui/main.py`
- Instantiates global StateManager singleton
- Launches TextualReplApp

**CLI Entry:** `/Users/tuna/Desktop/tunacode/src/tunacode/cli/`
- Command-line interface via Typer
- REPL mode with slash commands

**Note:** Entry analysis was not explicitly documented. Manual inspection reveals the above entry points.

### Architecture Analysis

**Architectural Pattern:** Pragmatic layered architecture with strong component-based design

**Key Architectural Decisions:**
1. **UI/Core Decoupling**: Callback-based communication enables headless execution
2. **Modular System Prompts**: Composable prompt sections for maintainability
3. **Agent as Iterator**: Pull-based model for consuming agent execution
4. **Centralized State Management**: Single source of truth in StateManager
5. **Tool Authorization System**: Policy-based safety with user control

**Data Flow:**
```
USER INPUT → UI Capture → Request Queue → process_request()
  → Agent.iter() → LLM API → Tool Selection → Authorization
  → Tool Execution → Response Rendering → State Update
```

**Circular Dependency Note:** Core ↔ Tools have a circular dependency:
- Core imports tool functions for agent configuration
- Tools import from Core for state management and delegation

### Modules Summary

**Core Agent Orchestration:**
- `process_request()` in main.py creates RequestOrchestrator
- Agent components: agent_config, node_processor, tool_executor, tool_buffer
- Delegation system: research_agent with read-only tools
- State machine: AgentStateMachine with valid transitions
- ReAct pattern: ReactSnapshotManager for thought process

**UI Module:**
- TextualReplApp with screens, widgets, renderers
- Screen management: ModelPicker, SessionPicker, Setup, ThemePicker
- Renderer system: RichPanelRenderer with 4-zone NeXTSTEP layout
- Specialized tool renderers: bash, glob, grep, read_file, etc.
- Custom widgets: Editor, ResourceBar, StatusBar

**Tools Module:**
- Decorator system: @base_tool, @file_tool with XML prompt files
- Authorization: ToolHandler, AuthorizationPolicy, composable rules
- Tool implementations: bash, grep (4 strategies), glob, read_file, write_file, update_file
- Fuzzy matching: line-trimmed, indentation-flexible, block-anchor
- Todo tools: todowrite, todoread, todoclear
- ReAct tools: scratchpad management

### State Summary

**Multi-Layered State Management:**
1. **Central Session Store:** StateManager.session as single source of truth
2. **Layered Caching:** Module-level caches for prompts, agents, models
3. **Explicit State Machines:** AgentStateMachine for controlled lifecycle
4. **Persistent Sessions:** JSON-based save/load with auto-save
5. **Flexible Configuration:** Merged defaults + user config
6. **Component-Level State:** Encapsulated UI widget state
7. **Environment-Aware:** Dynamic API key and base URL resolution

**State Stores:**
- StateManager: Central session orchestrator
- SessionState: Conversation, config, tool, agent, UI, metadata, metrics
- Agent orchestration state: AgentConfig, RequestContext, IterationManager
- UI state containers: TextualReplApp, widget-specific state

**Caching Strategies:**
- Module-level in-memory caches (prompts, agents, tunacode content)
- Models registry cache
- Token counter memoization (lru_cache)
- Tool buffer for read-only batching

---

## Design Philosophy

**NeXTSTEP-Inspired UI Design**

TunaCode's interface design is heavily inspired by the classic **NeXTSTEP User Interface Guidelines (1993)**:

### Core Principles
1. **Uniformity** - Consistent, predictable experience across all interactions
2. **User Informed** - Agent state and actions always visible (no magic background operations)
3. **Professional Aesthetic** - Clean, retro-modern look with clarity
4. **Object-Oriented** - Component-based architecture

### Evidence in Codebase
- Two complete UI themes: "TunaCode" (default) and "NeXTSTEP"
- NeXTSTEP-style panel layouts (4-zone: header, context, viewport, status)
- Bevel and shadow effects in CSS styling
- High contrast for readability
- Clear information hierarchy
- Real-time feedback for all operations

---

## Key Integration Points

### Modification Seams (M)
Primary files where behavior can be modified:

| Module | Key Files | Purpose |
|--------|-----------|---------|
| Root | `constants.py`, `exceptions.py` | Foundation used everywhere |
| Core | `agents/main.py`, `state.py` | Agent orchestration |
| UI | `app.py`, `main.py`, `renderers/` | Presentation layer |
| Tools | `decorators.py`, individual tools | Agent capabilities |
| Configuration | `settings.py`, `models.py` | Settings management |
| CLI | `commands/`, `repl_components/` | Command-line interface |

### Extension Seams (D)
Points where new functionality can be added:

| Module | Extension Points |
|--------|------------------|
| Core | New agent types, custom agent factories, specialized tool executors |
| UI | New screens, custom widgets, renderer strategies, REPL commands |
| Tools | New tool implementations, custom authorizers, validation logic |
| Configuration | New config options, model registry extensions |

### Important Cross-Module Seams
- **core ↔ tools**: Circular dependency (shared interfaces)
- **ui → core**: Callback-based communication (streaming_callback, tool_callback)
- **all → types**: Centralized type definitions
- **all → exceptions**: Rich error handling hierarchy

---

## Technical Debt & Anti-Patterns

### Known Issues
1. **Circular Dependency**: Core ↔ Tools
   - Impact: Difficult to test in isolation, complex initialization
   - Potential solutions: Extract shared interfaces, use dependency injection

2. **Entry Point Analysis Incomplete**
   - Manual inspection required for CLI entry documentation

### Best Practices Followed
- Explicit over implicit
- Fail fast, fail loud
- DRY principle (Don't Repeat Yourself)
- Separation of concerns
- Dependency injection
- Async/await for non-blocking operations

---

## Testing Strategy

### Current Test Coverage
Located in `/Users/tuna/Desktop/tunacode/tests/`:
- Tool decorator tests
- Tool conformance tests
- Compaction tests
- Tool retry logic tests

### Testing Challenges
1. Circular dependency makes unit testing difficult
2. Async code requires pytest-asyncio
3. UI code requires Textual framework testing

### Recommended Approach
1. Unit tests for tools in isolation
2. Integration tests for core orchestration with mock tools
3. E2E tests for full request flow
4. UI tests using textual-dev

---

## Extension Guide

### Adding a New Tool
1. Create tool function in `/Users/tuna/Desktop/tunacode/src/tunacode/tools/`
2. Decorate with `@file_tool` or `@base_tool`
3. Add XML prompt file in `tools/prompts/`
4. Add to tools list in `agent_config.py`
5. Optionally create custom renderer in `ui/renderers/tools/`

### Adding a New Agent Type
1. Create prompt sections in `/Users/tuna/Desktop/tunacode/src/tunacode/prompts/sections/`
2. Compose prompt using `compose_prompt()`
3. Configure tools for agent type
4. Add agent factory logic in `agent_config.py`

### Adding a New UI Screen
1. Create screen class in `/Users/tuna/Desktop/tunacode/src/tunacode/ui/screens/`
2. Integrate with `TextualReplApp`
3. Add navigation logic

---

## Code Quality Metrics

### Strengths
- Comprehensive type hints (PEP 484)
- Extensive documentation (docstrings, comments)
- Consistent naming conventions (snake_case, CamelCase, UPPER_SNAKE_CASE)
- Error handling with actionable guidance
- Modular architecture enabling testing
- Clear integration points (seams)
- Lazy loading for performance
- Theme consistency

### External Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| textual | ^4.0.0 | TUI framework |
| pydantic-ai | ^1.18.0 | AI agent framework |
| pydantic | ^2.12.4 | Data validation |
| typer | ^0.15.0 | CLI framework |
| rich | ^14.2.0 | Terminal formatting |
| pathspec | ^0.12.1 | Gitignore patterns |
| html2text | ^2024.2.26 | HTML conversion |

---

## Documentation Navigation

### Structure Documents
- **[structure/](./structure/)** - Directory organization and file structure
  - [00-root-overview.md](./structure/00-root-overview.md) - Constants, exceptions
  - [01-ui-directory.md](./structure/01-ui-directory.md) - TUI components
  - [02-core-directory.md](./structure/02-core-directory.md) - Agent orchestration
  - [03-tools-directory.md](./structure/03-tools-directory.md) - Tool implementations
  - [04-configuration-directory.md](./structure/04-configuration-directory.md) - Settings
  - [05-cli-directory.md](./structure/05-cli-directory.md) - Command-line interface
  - [06-supporting-modules.md](./structure/06-supporting-modules.md) - Auxiliary modules

### Architecture Documents
- **[architecture/architecture.md](./architecture/architecture.md)** - System design, patterns, data flow

### Module Documents
- **[modules/](./modules/)** - Detailed module documentation
  - [00-overview.md](./modules/00-overview.md) - Package structure
  - [core-agents.md](./modules/core-agents.md) - Agent orchestration
  - [core-state.md](./modules/core-state.md) - State management
  - [core-prompting.md](./modules/core-prompting.md) - Prompt composition
  - [ui-overview.md](./modules/ui-overview.md) - UI components
  - [tools-overview.md](./modules/tools-overview.md) - Tool system
  - [configuration.md](./modules/configuration.md) - Configuration
  - [types.md](./modules/types.md) - Type definitions
  - [utils.md](./modules/utils.md) - Utilities
  - [indexing.md](./modules/indexing.md) - Code indexing
  - [lsp.md](./modules/lsp.md) - Language Server Protocol
  - [templates.md](./modules/templates.md) - Templates
  - [prompts.md](./modules/prompts.md) - Prompt sections
  - [exceptions.md](./modules/exceptions.md) - Exception hierarchy
  - [constants.md](./modules/constants.md) - Global constants

### State Documents
- **[state/state.md](./state/state.md)** - State management, caching, persistence

---

## Analysis Metadata

**SEAMS Agents:**
- Structure Agent - Directory organization and file structure
- Architecture Agent - System design and patterns
- Modules Agent - Detailed component documentation
- State Agent - State management and data flow

**Analysis Tool:** Gemini MCP (gemini-2.5-flash, gemini-2.5-pro)

**Analysis Date:** 2026-01-04

**Output Location:** `/Users/tuna/Desktop/tunacode/docs/codebase-map/`

---

## Conclusion

TunaCode demonstrates **excellent software engineering practices**:

- Well-organized with clear module boundaries
- Highly maintainable with consistent patterns
- Type-safe with comprehensive annotations
- User-focused with rich error messages
- Extensible with plugin-style tools and agents
- Documented with clear docstrings and comments

The **depth 0 analysis** provides a solid foundation for deeper codebase understanding and future development work. The primary technical debt (core ↔ tools circular dependency) should be addressed in future refactoring to improve testability and maintainability.
