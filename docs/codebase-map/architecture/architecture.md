# Tunacode Architecture Documentation

## Overview

Tunacode is a TUI (Terminal User Interface) code agent built with a **layered, component-based architecture**. The system is designed with clear separation of concerns between the presentation layer (UI), the core agent logic, tool capabilities, and configuration management.

**File**: `/Users/tuna/Desktop/tunacode/src`

**Version**: 0.1.20

**Python Version**: 3.11-3.13

---

## 1. Architectural Pattern

The project follows a **pragmatic layered architecture** with strong component-based design principles:

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
│                    (src/tunacode/ui/)                        │
│  Built with Textual framework - handles user interaction     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│                   (src/tunacode/core/)                       │
│  Agent orchestration, request processing, state management   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                       Domain Layer                           │
│                    (src/tunacode/tools/)                     │
│  Tool functions - bash, grep, read_file, etc.               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                       │
│  (src/tunacode/configuration/, indexing/, lsp/, utils/)      │
│  Configuration, indexing, LSP integration, utilities        │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Principles

1. **UI/Core Decoupling**: The core agent logic is completely independent of the Textual UI, enabling headless execution and testing
2. **Callback-based Communication**: Layers communicate through callbacks rather than direct dependencies
3. **Centralized State Management**: A `StateManager` holds all session state, avoiding scattered state management
4. **Modular Tool System**: Tools are self-contained functions with clear interfaces
5. **Composable System Prompts**: Prompts are composed from smaller sections for maintainability

---

## 2. Component Relationships

### Major Components

```
┌──────────────────────────────────────────────────────────────────┐
│                         UI Layer                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  TextualApp  │  │   Screens    │  │  Renderers   │          │
│  │  (app.py)    │  │ (setup,      │  │  (tools,     │          │
│  │              │  │  picker)     │  │   panels)    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└──────────────────────────────────────────────────────────────────┘
         │                      │                      │
         │ requests             │ renders             │ callbacks
         ▼                      ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│                        Core Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Agent      │  │ Request      │  │  State       │          │
│  │  Config      │  │Orchestrator  │  │  Manager     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└──────────────────────────────────────────────────────────────────┘
         │                      │                      │
         │ configures           │ orchestrates        │ manages
         ▼                      ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Tools Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    Bash      │  │    Grep      │  │  Read File   │          │
│  │   Tool       │  │    Tool      │  │    Tool      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    Glob      │  │Authorization │  │   Decorators │          │
│  │   Tool       │  │    Handler   │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└──────────────────────────────────────────────────────────────────┘
         │                      │                      │
         │ reads                │ uses                │ provides
         ▼                      ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Configuration Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Models     │  │   Defaults   │  │   Settings   │          │
│  │  Registry    │  │              │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└──────────────────────────────────────────────────────────────────┘
```

### Dependency Graph

```
                    ┌─────────────┐
                    │    UI       │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌───────────┐    ┌───────────┐    ┌───────────┐
    │   Core    │───▶│   Tools   │    │    LSP    │
    └─────┬─────┘    └─────┬─────┘    └───────────┘
          │                │
          └────────┬───────┘
                   ▼
            ┌──────────────┐
            │Configuration │
            └──────────────┘
```

**Note**: Dependency direction is one-way here:
- `core` imports tool functions for orchestration
- tools do not import from `core`

---

## 3. Data Flow

### Complete Request Lifecycle

```
USER INPUT
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ 1. INPUT CAPTURE (UI Layer)                                   │
│    - User types in Editor widget (ui/app.py)                 │
│    - EditorSubmitRequested message posted                     │
│    - Message placed on request_queue                          │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ 2. REQUEST PROCESSING (Core Layer)                            │
│    - _request_worker dequeues from request_queue              │
│    - Calls process_request() (core/agents/main.py)           │
│    - RequestOrchestrator instantiated                          │
│    - Agent created/retrieved from cache                       │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ 3. AGENT EXECUTION (Core Layer)                               │
│    - System prompt composed from sections                     │
│    - Agent.iter() loop begins                                 │
│    - Model request sent to LLM API                            │
│    - Response streamed back                                   │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ 4. TOOL SELECTION (Core Layer)                                │
│    - Node processor inspects response                         │
│    - Tool calls extracted from structured output              │
│    - tool_callback invoked (ui/repl_support.py)              │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ 5. AUTHORIZATION (Tools Layer)                                │
│    - ToolHandler checks authorization policy                  │
│    - User confirmation requested if needed                    │
│    - Tool execution approved or denied                        │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ 6. TOOL EXECUTION (Tools Layer)                               │
│    - Tool function executed (e.g., bash, grep)                │
│    - Return value captured                                    │
│    - Results recorded in the run message history              │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ 7. RESPONSE RENDERING (UI Layer)                              │
│    - streaming_callback updates streaming_output              │
│    - tool_result_callback creates Panel for results           │
│    - Final response written to RichLog                        │
│    - Token usage and cost calculated                          │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
STATE UPDATE
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ 8. STATE MANAGEMENT (Core Layer)                              │
│    - SessionState messages synced from agent_run history       │
│    - Token usage updated                                      │
│    - Context window managed via compaction                    │
└───────────────────────────────────────────────────────────────┘
```

### Callback Communication Flow

```
┌─────────────────┐                    ┌─────────────────┐
│      UI         │                    │      Core       │
│  (TextualApp)   │                    │ (Orchestrator)  │
└────────┬────────┘                    └────────┬────────┘
         │                                     │
         │  streaming_callback(text)           │
         │  tool_callback(tool_name)           │
         │  tool_result_callback(result)       │
         │  tool_start_callback()              │
         │------------------------------------>│
         │                                     │
         │                                     │  Execute tool
         │                                     │  Stream response
         │                                     │
         │  Update UI widgets                  │
         │  Show confirmation dialog           │
         │  Render tool output                 │
         │<-------------------------------------│
         │                                     │
```

---

## 4. Design Patterns

### 1. Factory & Singleton Pattern

**Location**: `src/tunacode/core/agents/agent_components/agent_config.py`

```python
def get_or_create_agent(model: ModelName, state_manager: StateManager) -> PydanticAgent:
    # Factory: Creates agent instances
    # Singleton: Caches agents per model
    if model not in _agent_cache:
        agent = Agent(
            model=model_instance,
            system_prompt=system_prompt,
            tools=tools_list,
        )
        _agent_cache[model] = agent
    return _agent_cache[model]
```

**Purpose**: Avoid expensive re-initialization of agents while allowing dynamic creation.

### 2. Strategy Pattern

**Location**: `src/tunacode/tools/grep.py`

```python
def grep(..., search_type: Literal["smart", "ripgrep", "python", "hybrid"] = "smart"):
    # Dynamically selects search algorithm based on context
    if search_type == "smart":
        # Choose best algorithm automatically
    elif search_type == "ripgrep":
        # Use ripgrep
    elif search_type == "python":
        # Use pure Python
```

**Purpose**: Allow runtime selection of search algorithms based on file count and context.

### 3. Decorator Pattern

**Location**: `src/tunacode/tools/decorators.py`

```python
@file_tool
def read_file(file_path: str) -> str:
    # Decorator adds error handling and LSP diagnostics
    ...

@base_tool
def bash(command: str) -> str:
    # Decorator adds authorization and error handling
    ...
```

**Purpose**: Add cross-cutting concerns (error handling, authorization) without cluttering tool logic.

### 4. Observer Pattern

**Location**: Throughout UI/Core communication

```python
# Core notifies UI of state changes
async def process_request(
    streaming_callback: Callable[[str], None],
    tool_callback: Callable[[ToolCall], None],
    tool_result_callback: Callable[[ToolResult], None],
    ...
):
    # Core (Subject) notifies UI (Observer) via callbacks
    await streaming_callback(token)
    await tool_callback(tool_call)
    await tool_result_callback(result)
```

**Purpose**: Enable UI to react to core events without tight coupling.

### 5. Composite Pattern

**Location**: `src/tunacode/core/agents/delegation_tools.py`

```python
# A tool that is itself an agent
def research_codebase(query: str) -> str:
    # Main agent delegates to specialized research agent
    research_agent = get_or_create_agent(model, ...)
    return await research_agent.run(query)
```

**Purpose**: Enable hierarchical agent organization where agents can delegate to specialized sub-agents.

### 6. Policy Pattern

**Location**: `src/tunacode/tools/authorization/`

```python
class AuthorizationPolicy:
    def __init__(self, rules: List[AuthorizationRule]):
        self.rules = rules

    def should_confirm(self, tool_name: str) -> bool:
        return any(rule.should_confirm(tool_name) for rule in self.rules)

# Concrete rules
ReadOnlyToolRule()
YoloModeRule()
DangerousToolRule()
```

**Purpose**: Allow flexible composition of authorization rules.

### 7. State Management Pattern

**Location**: `src/tunacode/core/state.py`

```python
class StateManager:
    def __init__(self):
        self.session = SessionState(
            messages=[],
            model=None,
            token_usage=TokenUsage(),
            ...
        )

# Centralized state store passed to all components
state_manager = StateManager()
app = TextualReplApp(state_manager=state_manager)
```

**Purpose**: Single source of truth for application state, avoiding scattered state management.

---

## 5. Module Dependencies

### Dependency Hierarchy

```
Level 0 (Foundation):
├── constants
├── types
└── exceptions

Level 1 (Utilities):
├── configuration
│   ├── models (model registry, pricing)
│   ├── defaults (default config)
│   └── settings (API keys, user config)
├── utils
│   ├── config
│   ├── messaging
│   ├── parsing
│   └── system
├── templates
├── lsp
├── prompting
│   └── sections
└── indexing

Level 2 (Core Logic):
├── core
│   ├── agents (agent orchestration)
│   ├── background (async task management)
│   ├── logging
│   ├── setup
│   └── token_usage
└── tools
    ├── authorization
    ├── grep_components
    ├── prompts
    └── utils

Level 3 (Application):
├── ui
│   ├── screens (setup, picker, confirm)
│   ├── renderers (tools, panels)
│   ├── components
│   ├── widgets
│   └── styles
└── services (currently empty)
```

### Import Flow Analysis

**Tightly Coupled**:
- `core` -> `tools` (one-way orchestration dependency)
  - `core` imports tool functions for agent configuration and dispatch

**Loosely Coupled**:
- `configuration` - Standalone, only depends on foundation types
- `constants`, `types`, `exceptions` - No internal dependencies
- `indexing`, `lsp`, `prompting` - Limited, specific dependencies

**Highly Coupled to UI**:
- `ui` depends on nearly all modules (core, tools, configuration, indexing, lsp)

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `textual` | ^4.0.0 | TUI framework |
| `pydantic-ai` | ^1.18.0 | AI agent framework |
| `pydantic` | ^2.12.4 | Data validation |
| `typer` | ^0.15.0 | CLI framework |
| `rich` | ^14.2.0 | Terminal formatting |
| `pathspec` | ^0.12.1 | Gitignore pattern matching |
| `html2text` | ^2024.2.26 | HTML to Markdown conversion |
| `python-Levenshtein` | ^0.21.0 | String similarity |
| `ruff` | ^0.14.0 | Linting and formatting |
| `textual-autocomplete` | ^4.0.6 | Autocomplete widget |
| `defusedxml` | * | Secure XML parsing |
| `prompt_toolkit` | ^3.0.52 | REPL prompt handling |
| `click` | ^8.1.0 | CLI utilities |

---

## 6. Key Architectural Decisions

### Decision 1: UI/Core Decoupling

**Rationale**: Enable headless execution, simplify testing, support future UI implementations

**Implementation**:
- Callback-based communication
- `StateManager` as shared state object
- Core logic has no Textual dependencies

**Files**:
- `/Users/tuna/Desktop/tunacode/src/tunacode/ui/app.py`
- `/Users/tuna/Desktop/tunacode/src/tunacode/core/agents/main.py`

### Decision 2: Modular System Prompts

**Rationale**: Make prompts maintainable, composable, and customizable per agent type

**Implementation**:
- Prompts composed from sections in `src/tunacode/core/prompting/sections/`
- `SectionLoader` and `compose_prompt` for assembly
- Different agents use different prompt combinations

**Files**:
- `/Users/tuna/Desktop/tunacode/src/tunacode/core/prompting/`
- `/Users/tuna/Desktop/tunacode/src/tunacode/prompts/sections/`

### Decision 3: Agent as Iterator

**Rationale**: Provide clean, pull-based model for consuming agent execution steps

**Implementation**:
- Agent execution exposed as async iterator
- UI consumes steps as they arrive
- Avoids callback hell

**Files**:
- `/Users/tuna/Desktop/tunacode/src/tunacode/core/agents/main.py`

### Decision 4: Centralized State Management

**Rationale**: Single source of truth, explicit state changes, easier debugging

**Implementation**:
- `SessionState` dataclass holds all session data
- `StateManager` provides access and updates
- State passed to key components

**Files**:
- `/Users/tuna/Desktop/tunacode/src/tunacode/core/state.py`

### Decision 5: Tool Authorization System

**Rationale**: Balance safety with usability, allow user control over dangerous operations

**Implementation**:
- Policy-based authorization system
- Composable rules (read-only, yolo mode, dangerous tools)
- User confirmation for unauthorized operations

**Files**:
- `/Users/tuna/Desktop/tunacode/src/tunacode/tools/authorization/`

---

## 7. Separation of Concerns

### UI Layer (`src/tunacode/ui/`)

**Responsibility**: Presentation and user interaction

**Key Files**:
- `app.py` - Main Textual application
- `screens/` - Setup, picker, and confirmation screens
- `renderers/` - Tool output rendering
- `components/` - Reusable UI components
- `widgets/` - Custom widgets

**Does NOT**:
- Execute tool logic
- Make agent decisions
- Manage business logic

### Core Layer (`src/tunacode/core/`)

**Responsibility**: Agent orchestration and business logic

**Key Files**:
- `agents/main.py` - Request processing entry point
- `agents/agent_config.py` - Agent factory
- `agents/agent_components/node_processor.py` - Response processing
- `state.py` - State management
- `prompting/` - Prompt composition

**Does NOT**:
- Render UI
- Execute file operations directly
- Handle Textual framework details

### Tools Layer (`src/tunacode/tools/`)

**Responsibility**: Agent capabilities and system interactions

**Key Files**:
- `bash.py` - Shell command execution
- `grep.py` - Code search
- `read_file.py` - File reading
- `authorization/` - Tool authorization

**Does NOT**:
- Orchestrate agent flow
- Render output
- Manage UI state

### Configuration Layer (`src/tunacode/configuration/`)

**Responsibility**: Settings and model data

**Key Files**:
- `models.py` - Model registry
- `defaults.py` - Default configuration
- `settings.py` - User settings

**Does NOT**:
- Execute logic
- Manage state
- Interact with UI

---

## 8. Anti-Patterns and Technical Debt

### Circular Dependency: Core ↔ Tools

**Issue**:
- `core` imports tool functions
- Some tools import from `core`

**Impact**:
- Difficult to test in isolation
- Complex initialization order
- Harder to reason about

**Potential Solutions**:
1. Extract shared interfaces to a separate module
2. Use dependency injection
3. Move shared functionality to a utilities module

### Current Locations

**Core → Tools**:
- `/Users/tuna/Desktop/tunacode/src/tunacode/core/agents/agent_components/agent_config.py`

**Tools → Core**:
- `/Users/tuna/Desktop/tunacode/src/tunacode/tools/authorization/`
- `/Users/tuna/Desktop/tunacode/src/tunacode/tools/todo.py`

---

## 9. Extension Points

### Adding a New Tool

1. Create tool function in `/Users/tuna/Desktop/tunacode/src/tunacode/tools/`
2. Decorate with `@file_tool` or `@base_tool`
3. Add to tools list in `agent_config.py`
4. Optionally create custom renderer in `ui/renderers/tools/`

### Adding a New Agent Type

1. Create prompt sections in `/Users/tuna/Desktop/tunacode/src/tunacode/prompts/sections/`
2. Compose prompt using `compose_prompt()`
3. Configure tools for agent type
4. Add agent factory logic

### Adding a New UI Screen

1. Create screen class in `/Users/tuna/Desktop/tunacode/src/tunacode/ui/screens/`
2. Integrate with `TextualReplApp`
3. Add navigation logic

---

## 10. Testing Strategy

### Current Test Coverage

Located in `/Users/tuna/Desktop/tunacode/tests/`:
- Tool decorator tests
- Tool conformance tests
- Compaction tests
- Tool retry logic tests

### Testing Challenges

1. **Circular Dependency**: Makes unit testing difficult
2. **Async Code**: Requires pytest-asyncio
3. **UI Code**: Textual framework requires specialized testing

### Recommended Testing Approach

1. **Unit Tests**: Test tools in isolation
2. **Integration Tests**: Test core orchestration with mock tools
3. **E2E Tests**: Test full request flow with real tools
4. **UI Tests**: Use textual-dev for screen testing

---

## 11. Performance Considerations

### Token Management

- Context window managed via `prune_old_tool_outputs()`
- Token usage tracked per request and session
- Cost calculation based on model pricing

### Caching

- Agent instances cached per model
- Code index cached
- Model registry lazy-loaded

### Async Operations

- All I/O operations are async
- Background tasks for long-running operations
- Non-blocking UI updates

---

## 12. Local Mode vs API Mode

Tunacode supports two operating modes optimized for different model capabilities.

### Architecture

**Both modes use identical providers.** There are no separate LocalProvider implementations. The same `AnthropicProvider` or `OpenAIProvider` classes are used regardless of mode.

All optimization happens at the **message preparation layer** before any provider interaction.

### The 6 Optimization Layers

When `local_mode: true` is set in configuration, these layers activate:

| Layer | Component | Standard Mode | Local Mode |
|-------|-----------|--------------|------------|
| 1 | System prompt | 11 sections (~3,500 tok) | 3 sections (~1,100 tok) |
| 2 | Guide file | User's AGENTS.md (~2k+ tok) | local_prompt.md (~500 tok) |
| 3 | Tool set | 11 tools, full descriptions | 6 tools, 1-word descriptions |
| 4 | Output limits | 2000 lines, 5000 chars | 200 lines, 1500 chars |
| 5 | Response cap | Unlimited | 1000 tokens |
| 6 | Pruning | Protect 40k tokens | Protect 2k tokens |

### Message Flow

```
User Message
     │
     ▼
process_request() [core/agents/main.py:527]
     │
     ▼
get_or_create_agent() [agent_config.py]
     │   - is_local_mode() check
     │   - Select template (LOCAL_TEMPLATE vs MAIN_TEMPLATE)
     │   - Select tools (6 vs 11)
     │   - Apply max_tokens
     │
     ▼
prune_old_tool_outputs() [compaction.py]
     │   - get_prune_thresholds() based on mode
     │   - Backward scan messages
     │   - Protect recent outputs
     │   - Replace old with placeholder
     │
     ▼
agent.iter() → Provider HTTP Request
     │
     ▼
(Same pydantic-ai message format for both modes)
```

### Configuration

Central control via `~/.config/tunacode.json`:

```json
{
  "settings": {
    "local_mode": true,
    "local_max_tokens": 1000
  }
}
```

Precedence: `explicit setting > local_mode default > standard default`

### Key Files

| File | Role |
|------|------|
| `utils/limits.py` | Central mode detection (`is_local_mode()`) |
| `core/compaction.py` | Pruning with mode-aware thresholds |
| `core/agents/agent_config.py` | Template/tool selection |
| `core/prompting/templates.py` | LOCAL_TEMPLATE vs MAIN_TEMPLATE |
| `core/prompting/local_prompt.md` | Condensed guide for local mode |
| `constants.py` | Default limit values |

### Token Budget

| Component | Standard | Local |
|-----------|----------|-------|
| System prompt | ~3,500 | ~1,100 |
| Guide file | ~2,000+ | ~500 |
| Tool schemas | ~1,800 | ~575 |
| **Total base** | **~7,300+** | **~2,200** |

With 10k context window:
- Standard: ~2,700 tokens for conversation
- Local: ~7,800 tokens for conversation

---

## 13. Security Considerations

### Tool Authorization

- Policy-based authorization system
- User confirmation for dangerous operations
- Yolo mode for experienced users

### Input Validation

- Pydantic models for all inputs
- Path sanitization for file operations
- Shell command validation

### Dependency Security

- `defusedxml` for secure XML parsing
- Bandit security scanning configured
- Regular dependency updates

---

## Conclusion

Tunacode demonstrates a well-structured, modular architecture with clear separation of concerns. The primary architectural strength is the UI/Core decoupling, enabling multiple UI implementations and headless operation. Core-to-tools dependencies are now one-way, keeping the tool layer isolated from core internals.

The callback-based communication pattern, centralized state management, and composable system prompts all contribute to a maintainable and extensible codebase.

---

**Generated**: 2026-01-04
**Analysis Tool**: Gemini MCP (gemini-2.5-pro)
**Codebase Version**: 0.1.20
