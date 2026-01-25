# TunaCode Dependency Architecture

## Current State (Clean)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                    UI                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   app.py    │  │  widgets/   │  │ renderers/  │  │  repl_support.py    │ │
│  │  (Textual)  │  │             │  │             │  │   (callbacks)       │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼────────────────┼────────────────────┼────────────┘
          │                │                │                    │
          ▼                ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                   CORE                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  StateManager   │  │  Orchestrator   │  │  agents/                    │  │
│  │   (state.py)    │◄─┤  (main.py)      │  │   ├─ agent_config.py        │  │
│  └────────┬────────┘  └────────┬────────┘  │   ├─ resume/                │  │
│           │                    │           │   └─ agent_components/      │  │
│           ▼                    ▼           └─────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       SessionState                                   │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │    │
│  │  │  messages    │  │ tool_calls   │  │ react_pad    │  ... 40 fields│    │
│  │  │ (polymorphic)│  │ (duplicated) │  │ (dict)       │               │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  TOOLS                                      │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐ │
│  │   bash    │  │   glob    │  │   grep    │  │ read_file │  │   react   │ │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘  └───────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  authorization/   (ToolHandler, policies)                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TYPES / UTILS                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐  │
│  │  base.py      │  │ dataclasses.py│  │  protocols.py │  │ messaging/  │  │
│  │  (aliases)    │  │  (ModelConfig │  │  (StateProto) │  │   utils     │  │
│  │               │  │   TokenUsage) │  │               │  │             │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Target State (After Refactor)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                    UI                                       │
│                           (unchanged - clean)                               │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                   CORE                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  StateManager   │  │  Orchestrator   │  │  ToolCallRegistry          │  │
│  │   (state.py)    │  │  (main.py)      │  │  (single source of truth)  │  │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────────────────┘  │
│           │                    │                                            │
│           ▼                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                   SessionState (composed)                            │    │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │    │
│  │  │ ConversationSt │  │   ReActState   │  │   TaskState    │         │    │
│  │  │  - messages:   │  │  - scratchpad  │  │  - todos       │         │    │
│  │  │    Message[]   │  │    (typed)     │  │    (typed)     │         │    │
│  │  └────────────────┘  └────────────────┘  └────────────────┘         │    │
│  │  ┌────────────────┐  ┌────────────────┐                             │    │
│  │  │  RuntimeState  │  │   UsageState   │                             │    │
│  │  │  (ephemeral)   │  │  (typed)       │                             │    │
│  │  └────────────────┘  └────────────────┘                             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  TOOLS                                      │
│                           (unchanged - clean)                               │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TYPES (canonical)                              │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                       canonical.py (NEW)                              │ │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐          │ │
│  │  │  Message  │  │ ToolCall  │  │ TodoItem  │  │ ReActEntry│          │ │
│  │  │ (frozen)  │  │ (frozen)  │  │ (frozen)  │  │ (frozen)  │          │ │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘          │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                       adapter.py (NEW)                                │ │
│  │  to_canonical(pydantic_msg) ─────────────▶ Message                   │ │
│  │  from_canonical(msg) ◀───────────────────── Message                  │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Message Format Problem (Current)

```
        ┌─────────────────────────────────────────────────────────────────┐
        │                    Message History                              │
        │                                                                 │
        │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
        │  │  dict with    │  │  dict with    │  │  pydantic-ai  │       │
        │  │  "content"    │  │  "parts"      │  │  ModelRequest │       │
        │  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘       │
        │          │                  │                  │               │
        │          ▼                  ▼                  ▼               │
        │  ┌─────────────────────────────────────────────────────────┐   │
        │  │            get_message_content() - 4 branches           │   │
        │  │                                                         │   │
        │  │  if dict and "content"  → str(content)                  │   │
        │  │  if dict and "parts"    → join(parts)                   │   │
        │  │  if dict and "thought"  → str(thought)                  │   │
        │  │  if hasattr .content    → str(content)                  │   │
        │  │  if hasattr .parts      → join(parts)                   │   │
        │  └─────────────────────────────────────────────────────────┘   │
        └─────────────────────────────────────────────────────────────────┘
                                     │
                                     │ SCATTERED across:
                                     │  - message_utils.py
                                     │  - sanitize.py (300+ lines!)
                                     │  - serialization in state.py
                                     ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │                    Target: Canonical Message                    │
        │                                                                 │
        │  ┌─────────────────────────────────────────────────────────┐   │
        │  │  @dataclass(frozen=True)                                │   │
        │  │  class Message:                                         │   │
        │  │      role: MessageRole                                  │   │
        │  │      parts: tuple[MessagePart, ...]                     │   │
        │  │      timestamp: datetime | None                         │   │
        │  └─────────────────────────────────────────────────────────┘   │
        │                                                                 │
        │  ONE type. ONE accessor. NO branching.                         │
        └─────────────────────────────────────────────────────────────────┘
```

## Tool Call Duplication (Historical)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TOOL CALL TRACKING (Historical)                      │
│                                                                             │
│   1. session.runtime.tool_calls: list[dict]                                 │
│      {"tool": "read_file", "args": {...}, "id": "tc_123"}                   │
│                                                                             │
│   2. session.runtime.tool_call_args_by_id: dict[str, dict]                  │
│      {"tc_123": {"filepath": "/foo/bar"}}                                   │
│                                                                             │
│   3. Message parts (pydantic-ai)                                            │
│      ModelResponse.parts = [ToolCallPart(tool_call_id="tc_123", ...)]       │
│                                                                             │
│   THREE places tracking the SAME data!                                      │
│   When cleanup runs, must update ALL three.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TOOL CALL TRACKING (Current)                         │
│                                                                             │
│   ToolCallRegistry:                                                         │
│      dict[str, ToolCall]  keyed by tool_call_id                             │
│                                                                             │
│   @dataclass(frozen=True)                                                   │
│   class ToolCall:                                                           │
│       tool_call_id: str                                                     │
│       tool_name: str                                                        │
│       args: dict                                                            │
│       status: ToolCallStatus                                                │
│       result: str | None                                                    │
│       started_at: datetime | None                                           │
│       completed_at: datetime | None                                         │
│                                                                             │
│   ONE source of truth. Status transitions tracked.                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## SessionState Decomposition

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SessionState (Current: 40+ fields)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ CONVERSATION           │ REACT             │ TASK                          │
│  messages              │  react_scratchpad │  todos                        │
│  thoughts              │  react_forced     │  task_hierarchy               │
│                        │  react_guidance   │  recursive_context_stack      │
│                        │                   │  max_recursion_depth          │
│                        │                   │  parent_task_id               │
│                        │                   │  iteration_budgets            │
├────────────────────────┼───────────────────┼───────────────────────────────┤
│ RUNTIME (ephemeral)    │ USAGE             │ CONFIG                        │
│  spinner               │  total_tokens     │  user_config                  │
│  is_streaming_active   │  max_tokens       │  current_model                │
│  streaming_panel       │  last_call_usage  │  yolo                         │
│  tool_registry         │  session_total    │  debug_mode                   │
│  operation_cancelled   │                   │  plan_mode                    │
│  current_task          │                   │                               │
├────────────────────────┼───────────────────┼───────────────────────────────┤
│ IDENTITY               │ DEBUG             │ COUNTERS                      │
│  session_id            │  _debug_events    │  consecutive_empty_responses  │
│  device_id             │  _debug_raw_accum │  batch_counter                │
│  project_id            │                   │  iteration_count              │
│  working_directory     │                   │  current_iteration            │
│  created_at            │                   │                               │
│  last_modified         │                   │                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SessionState (Target: composed)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  @dataclass                                                                 │
│  class SessionState:                                                        │
│      # Composed sub-states (each ~5 fields)                                 │
│      conversation: ConversationState                                        │
│      react: ReActState                                                      │
│      task: TaskState                                                        │
│      runtime: RuntimeState                                                  │
│      usage: UsageState                                                      │
│                                                                             │
│      # Identity (kept at top level)                                         │
│      session_id: str                                                        │
│      project_id: str                                                        │
│      device_id: str | None                                                  │
│      working_directory: str                                                 │
│      created_at: datetime                                                   │
│      last_modified: datetime                                                │
│                                                                             │
│      # Config (kept at top level, rarely mutated)                           │
│      user_config: UserConfig                                                │
│      current_model: ModelName                                               │
│                                                                             │
│  Total: ~12 top-level fields (down from 40+)                                │
└─────────────────────────────────────────────────────────────────────────────┘
```
