# State Management Documentation

## Overview

TunaCode employs a multi-layered state management strategy that combines a central global session store with localized component states and explicit state machines for agent behavior. This architecture provides both centralized truth and localized control where appropriate, while supporting session persistence.

## 1. State Stores and Global State

### 1.1 Primary State Store: StateManager

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/core/state.py`

The `StateManager` class is the central application state orchestrator. It holds a `SessionState` object and is instantiated as a global singleton in `/Users/tuna/Desktop/tunacode/src/tunacode/ui/main.py`.

```python
state_manager = StateManager()
```

#### SessionState Dataclass

The `SessionState` class encapsulates the entire user session runtime state:

- **Conversation State:** `messages`, `current_model`
- **Configuration:** `user_config` (merged defaults + user settings)
- **Tool State:** `tool_calls`, `tool_ignore`, `yolo` mode
- **Agent State:** `react_scratchpad`, `todos`, `iteration_count`
- **UI State:** `operation_cancelled`, `is_streaming_active`
- **Metadata:** `session_id`, `project_id`, `created_at`, `last_modified`, `working_directory`
- **Metrics:** `session_total_usage` (token and cost tracking)

The `state_manager.session` object is the primary shared mutable state passed across agent components, tools, and UI elements.

### 1.2 Agent Orchestration State

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/core/agents/main.py`

Several state classes manage agent behavior:

- **`AgentConfig` (dataclass):** Defines agent behavior configuration (e.g., `max_iterations`)
- **`RequestContext` (dataclass):** Holds request-specific context (e.g., `request_id`)
- **`EmptyResponseHandler`:** Manages state for consecutive empty responses
- **`IterationManager`:** Tracks agent iteration progress and productivity
- **`ReactSnapshotManager`:** Manages ReAct snapshots and guidance
- **`RequestOrchestrator`:** Composes and manages the above state classes

### 1.3 UI State Containers

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/ui/app.py`

- **`TextualReplApp`:** Core UI state including:
  - `request_queue`: Asynchronous event queue
  - `pending_confirmation`: Async interaction state
  - Streaming flags: `_streaming_paused`, `_stream_buffer`, `current_stream_text`
  - Task references: `_current_request_task`

**Widget-specific state:**
- **`Editor`** (`/Users/tuna/Desktop/tunacode/src/tunacode/ui/widgets/editor.py`): Input editor state (`_placeholder_cleared`, `_was_pasted`, `_pasted_content`)
- **`ResourceBar`** (`/Users/tuna/Desktop/tunacode/src/tunacode/ui/widgets/resource_bar.py`): Resource display state (`_tokens`, `_model`, `_cost`, `_lsp_enabled`)
- **`StatusBar`** (`/Users/tuna/Desktop/tunacode/src/tunacode/ui/widgets/status_bar.py`): Status bar state (`_edited_files`, `_location_text`)
- **`ShellRunner`** (`/Users/tuna/Desktop/tunacode/src/tunacode/ui/shell_runner.py`): External process state (`_task`, `_process`)

## 2. Caching Strategies

### 2.1 Module-Level In-Memory Caches

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/core/agents/agent_components/agent_config.py`

Three module-level dictionaries serve as global in-memory caches:

```python
_TUNACODE_CACHE: dict[str, tuple[str, float]] = {}
_AGENT_CACHE: dict[ModelName, PydanticAgent] = {}
_AGENT_CACHE_VERSION: dict[ModelName, int] = {}
```

- **`_TUNACODE_CACHE`:** Caches `AGENTS.md` content with modification time
- **`_AGENT_CACHE`:** Stores `PydanticAgent` instances across requests
- **`_AGENT_CACHE_VERSION`:** Manages cache versioning for invalidation

> **Note:** System prompts are now composed from section files via `SectionLoader` in `src/tunacode/core/prompting/loader.py`, which uses instance-level caching.

### 2.2 Models Registry Cache

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/configuration/models.py`

```python
_models_registry_cache: dict | None = None

def load_models_registry() -> dict:
    global _models_registry_cache
    if _models_registry_cache is not None:
        return _models_registry_cache
    # ... loads from file ...
    _models_registry_cache = json.load(f)
    return _models_registry_cache
```

The models registry is cached in memory to avoid repeated file reads.

### 2.3 Token Counter Heuristic

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/utils/messaging/token_counter.py`

Uses a lightweight character heuristic:

```python
CHARS_PER_TOKEN: int = 4

def estimate_tokens(text: str, model_name: str | None = None) -> int:
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN
```

### 2.4 Tool Buffer

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/core/agents/agent_components/tool_buffer.py`

- **`ToolBuffer`:** Buffers read-only tool calls (`self.read_only_tasks`) for parallel execution
- Acts as a transient data store for tool calls awaiting batched execution

### 2.5 Progress Tracker

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/core/agents/research_agent.py`

- **`ProgressTracker`:** Tracks `operation_count` for subagent tool execution

## 3. Configuration Management

### 3.1 Configuration Hierarchy

**Default Configuration:**
**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/configuration/defaults.py`

```python
DEFAULT_USER_CONFIG = {
    "default_model": "openrouter:openai/gpt-4.1",
    "env": {
        "ANTHROPIC_API_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENROUTER_API_KEY": ""
    },
    "settings": {
        "max_retries": 3,
        "max_iterations": 10,
        "global_request_timeout": 120,
        "theme": "dark",
        # ... tool-specific settings
    }
}
```

**User Configuration:**
**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/utils/config/user_configuration.py`

- **`load_config()`:** Reads user-specific `~/.config/tunacode.json`, merging with `DEFAULT_USER_CONFIG` (user values take precedence)
- **`save_config(state_manager)`:** Persists current configuration to disk
- Includes caching for performance

**Application Settings:**
**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/configuration/settings.py`

- **`PathConfig`:** Specifies configuration file path
- **`ApplicationSettings`:** Manages application-wide metadata and paths
- Instantiated as global singleton `app_settings` in `/Users/tuna/Desktop/tunacode/src/tunacode/ui/main.py`

**Model Configuration:**
**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/configuration/models.py`

- Loads model metadata from `models_registry.json`
- Provides:
  - `get_provider_env_var()`: Provider-specific environment variable names
  - `get_provider_base_url()`: API base URLs
  - `get_model_context_window()`: Model context window sizes

### 3.2 Environment Variable Handling

**Configuration Resolution:**
**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/core/agents/agent_components/agent_config.py`

```python
def _create_model_with_retry(state_manager: StateManager):
    # Retrieves API keys from user_config["env"]
    api_keys = state_manager.session.user_config.get("env", {})

    # Resolves API base URLs: OS env > user config > settings
    base_url = os.getenv("ENV_OPENAI_BASE_URL") or settings.base_url
```

**Tool Execution:**
**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/tools/bash.py`

```python
exec_env = os.environ.copy()
if env:
    exec_env.update(env)
```

The bash tool copies the current process environment and allows custom variables per command.

## 4. Session Management

### 4.1 Session Lifecycle

**Session Creation:**
- Each session gets a unique `session_id` (UUID)
- Associated with a `project_id` (generated from Git or CWD via `get_project_id()`)
- Tracked in `SessionState` metadata fields

**Session Persistence:**
**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/core/state.py`

```python
def save_session():
    # Serializes SessionState to JSON
    # Stored in platform-specific session directory
    # ~/.local/share/tunacode/sessions/ on Linux
```

**Session Loading:**
```python
def load_session(session_id):
    # Deserializes JSON to SessionState
    # Restores application state
```

**Serialization Helpers:**
- `_serialize_messages()`: Converts Pydantic-AI message objects to JSON
- `_deserialize_messages()`: Restores messages from JSON

**Auto-Save:**
**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/ui/app.py`

- `save_session()` called automatically:
  - On application unmount
  - After each user request
- Ensures state persistence across interactions and restarts

### 4.2 Session Storage

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/utils/system/paths.py`

- `get_session_storage_dir()`: Platform-agnostic session storage location
- `get_session_dir()`: Session-specific directory path
- `get_project_id()`: Generates unique project identifier

### 4.3 Session Commands

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/ui/commands/__init__.py`

- **`ResumeCommand`:** List, load, and delete previous sessions
- Enables users to resume work where they left off

## 5. State Machines

### 5.1 Agent State Machine

**AgentState Enum:**
**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/types/dataclasses.py`

```python
class AgentState(Enum):
    USER_INPUT = "user_input"
    ASSISTANT = "assistant"
    TOOL_EXECUTION = "tool_execution"
    RESPONSE = "response"
```

**State Machine Implementation:**
**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/core/agents/agent_components/state_transition.py`

- **`AgentStateMachine`:** Thread-safe state machine managing `AgentState` transitions
- **`StateTransitionRules`:** Defines valid transitions between states
- **`AGENT_TRANSITION_RULES`:** Global instance defining allowed agent processing flow

**ResponseState Interface:**
**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/core/agents/agent_components/response_state.py`

```python
@dataclass
class ResponseState:
    state_machine: AgentStateMachine
    # Provides interface for agent state and completion tracking
    # Maintains backward compatibility through boolean flags
```

The state machine ensures controlled, validated transitions through agent processing stages.

## 6. User Preferences and Settings

### 6.1 Preference Storage

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/core/state.py`

All user-customizable settings are stored in:
```python
SessionState.user_config
```

This makes preferences accessible throughout the application.

### 6.2 Runtime Preference Modification

**Location:** `/Users/tuna/Desktop/tunacode/src/tunacode/ui/commands/__init__.py`

CLI commands allow runtime preference changes:

- **`/model`:** Changes `user_config["default_model"]`
- **`/theme`:** Updates `user_config["settings"]["theme"]`
- **`/yolo`:** Toggles auto-approve mode for tool execution

## Summary

TunaCode's state management is characterized by:

1. **Centralized Session Store:** `StateManager.session` as the single source of truth
2. **Layered Caching:** Module-level caches for prompts, agents, and models
3. **Explicit State Machines:** Controlled agent lifecycle through `AgentStateMachine`
4. **Persistent Sessions:** JSON-based session save/load with automatic persistence
5. **Flexible Configuration:** Merged defaults + user config with runtime modification
6. **Component-Level State:** Encapsulated state in UI widgets and agent components
7. **Environment-Aware:** Dynamic API key and base URL resolution

This architecture balances performance (caching), safety (state machines), and usability (session persistence, runtime configuration).
