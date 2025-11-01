# Kimi CLI Architecture Summary

## Overview

Kimi CLI demonstrates **10 production-grade architectural patterns** that work together to create a maintainable, testable, extensible system for AI-powered command-line interactions.

## The 10 Patterns (Quick Reference)

### 1. Separation of Concerns
**What**: Each module has one responsibility; config is separate from loading.
**Key Files**: `config.py`, `soul/runtime.py`, `soul/context.py`
**Impact**: Changes to config structure don't affect the agent loop.

### 2. Declarative Extensibility
**What**: New agents/tools are declared in YAML, not hardcoded in Python.
**Key Files**: `agentspec.py`, `soul/agent.py::_load_tool()`
**Impact**: New tools can be added without touching Python code.

### 3. Type-First Design
**What**: Pydantic models and type hints enforce correctness at instantiation.
**Key Files**: `config.py`, `tools/bash/__init__.py`, `llm.py`
**Impact**: Invalid configs fail at load time, not at runtime.

### 4. Constructor-Based DI
**What**: Dependencies are constructor parameters; no service locators.
**Key Files**: `tools/bash/__init__.py`, `soul/agent.py::_load_tool()`
**Impact**: Easy to mock in tests; dependencies are explicit.

### 5. Explicit Result Types
**What**: Functions return typed results (ToolOk, ToolError), not strings.
**Key Files**: `tools/utils.py::ToolResultBuilder`, `soul/__init__.py`
**Impact**: All error cases are handled explicitly; no exception surprises.

### 6. Async-by-Default I/O
**What**: All I/O is async; timeouts and cleanup are built in.
**Key Files**: `soul/context.py`, `tools/bash/__init__.py`, `soul/kimisoul.py`
**Impact**: No blocking; responsive to cancellation; proper resource cleanup.

### 7. Production-Grade Error Flow
**What**: Typed exceptions, error chaining, selective retry logic.
**Key Files**: `exception.py`, `config.py::load_config()`, `soul/kimisoul.py`
**Impact**: Errors are distinguishable; retries are only for transient errors.

### 8. Consistent Output Building
**What**: Tool outputs respect dual limits (char count, line length).
**Key Files**: `tools/utils.py::ToolResultBuilder`
**Impact**: All tools truncate consistently; no tool-specific truncation logic.

### 9. Testability
**What**: Dependencies are mockable; fixtures compose; async tests work.
**Key Files**: `conftest.py`, `soul/toolset.py`, `test_bash.py`
**Impact**: High test coverage without mocking frameworks or complexity.

### 10. Operational Clarity
**What**: Naming is semantic; docstrings explain the why; logging is structured.
**Key Files**: `soul/context.py`, `shell_manager.py`, `utils/logging.py`
**Impact**: Code is self-documenting; behavior is auditable.

---

## Key Design Decisions

### 1. Reflection-Based Tool Loading
```python
# Agent spec declares tools as strings
tools:
  - "kimi_cli.tools.bash:Bash"
  - "kimi_cli.tools.file.read:ReadFile"

# Agent loader inspects constructors and injects dependencies
for param in inspect.signature(cls).parameters.values():
    args.append(dependencies[param.annotation])
return cls(*args)
```
**Why**: No registration required. New tools are auto-discovered.

### 2. ContextVar for Tool Call Context
```python
current_tool_call = ContextVar[ToolCall | None]("current_tool_call", default=None)

# Tools can access their own tool call
tool_call = get_current_tool_call_or_none()
```
**Why**: Tools need metadata without threading parameters through all layers. Context vars are task-local (async-safe).

### 3. Wire Pattern for Soul ↔ UI Communication
```python
wire = Wire()
# Soul → UI (soul_side.send())
wire_send(StepBegin(step_no))
wire_send(StatusUpdate(...))

# UI ← Soul (ui_side.receive())
msg = await wire.ui_side.receive()
```
**Why**: Decouples soul from UI. Enables streaming output, approval requests, and cancellation.

### 4. Checkpoint-Based Context Management
```python
# Context maintains checkpoints on disk
async def checkpoint(self, add_user_message: bool):
    # Saves state at each agent step
    
async def revert_to(self, checkpoint_id: int):
    # Enables time-travel via D-Mail
```
**Why**: Agents can recover from failed attempts. D-Mail (time-travel messaging) enables future-to-past communication.

### 5. ToolResultBuilder Pattern
```python
builder = ToolResultBuilder(max_chars=50_000, max_line_length=2000)
builder.write(output)  # Incremental writing
if exitcode == 0:
    return builder.ok("Success")
else:
    return builder.error("Failed", brief="Error summary")
```
**Why**: Uniform output limits across all tools. Truncation is transparent to the tool author.

---

## Architecture Diagram (Simplified)

```
┌─────────────────────────────────────────────────────┐
│                   CLI Entry Point                    │
│                   (src/kimi_cli/cli.py)              │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│          Load Configuration & Resolve Agent          │
│          - Config (Pydantic validation)              │
│          - AgentSpec (YAML + inheritance)            │
│          - Runtime factory (async init)              │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│               Load Agent (reflection-based DI)       │
│          - Tool paths → Classes (importlib)          │
│          - Inspect constructors                      │
│          - Wire dependencies (type-safe)            │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                    Create KimiSoul                   │
│          (System prompt + Toolset + Context)         │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────┐
│                  run_soul() with Wire                 │
│   ┌──────────────────────────────────────────────┐   │
│   │ Soul Task                    UI Loop Task    │   │
│   │ ─────────────────────────────────────────    │   │
│   │ 1. _agent_loop()             receive()       │   │
│   │ 2. _step() → kosong.step()   display msg     │   │
│   │ 3. _grow_context()           prompt user     │   │
│   │ 4. Handle retries/errors     cancel event    │   │
│   └──────────────────────────────────────────────┘   │
│                                                       │
│   Communication:                                      │
│   - Soul → UI: Wire messages (stdout, tool calls)    │
│   - UI → Soul: Approval requests, cancellation       │
│   - Cancellation: asyncio.Event → soul_task.cancel() │
└───────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│              Tool Execution (Parallel)               │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │
│   │    Bash      │  │   ReadFile   │  │ SearchWeb│  │
│   │              │  │              │  │          │  │
│   │ Approval+DI  │  │ Work dir DI  │  │ Config DI│  │
│   │ Async stream │  │ Async file I/O │ │ Retry   │  │
│   │ Truncation   │  │ Limits       │  │ Logic   │  │
│   └──────────────┘  └──────────────┘  └──────────┘  │
│                         ▲                            │
│   Output Building: ToolResultBuilder (shared)       │
│   - Character limit (50K)                            │
│   - Line length limit (2000)                         │
│   - Truncation metadata                              │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│            Context Management & Checkpoints          │
│          - Append messages (async file I/O)         │
│          - Update token count                       │
│          - Create checkpoints                       │
│          - Revert to checkpoint (D-Mail)            │
└─────────────────────────────────────────────────────┘
```

---

## Testing Model

### Test Fixtures (Composable)
```python
# Base fixtures
config → get_default_config()
llm → LLM(MockChatProvider([]))
temp_work_dir → tempfile.TemporaryDirectory()

# Composed fixtures
runtime(config, llm, builtin_args, ...)
bash_tool(approval) → Bash instance
read_file_tool(builtin_args) → ReadFile instance

# Context managers for tool calls
tool_call_context("Bash") → sets ContextVar
```

### Async Test Pattern
```python
@pytest.mark.asyncio
async def test_command(bash_tool: Bash):
    result = await bash_tool(Params(command="..."))
    assert isinstance(result, ToolOk)
```

### Pure Unit Tests
```python
def test_char_limit_truncation():
    builder = ToolResultBuilder(max_chars=10)
    builder.write("Hello world")
    assert builder.is_full
    assert "truncated" in builder.ok("").message
```

---

## Extension Points

### Adding a New Tool
1. Create `src/kimi_cli/tools/mytool/__init__.py`:
```python
class MyTool(CallableTool2[Params]):
    def __init__(self, dependency1: Type1, **kwargs):
        self._dep1 = dependency1
    
    async def __call__(self, params: Params) -> ToolReturnType:
        builder = ToolResultBuilder()
        # ... implementation ...
        return builder.ok("Success")
```

2. Add to agent spec YAML:
```yaml
tools:
  - "kimi_cli.tools.mytool:MyTool"
```

3. Add to test fixtures (`conftest.py`):
```python
@pytest.fixture
def mytool(dependency1: Type1) -> MyTool:
    return MyTool(dependency1)
```

### Adding a New Agent
1. Create agent YAML file:
```yaml
version: 1
agent:
  name: "My Agent"
  extend: "default"
  system_prompt_path: "prompt.md"
  tools: [...]
```

2. Load via CLI:
```bash
kimi --agent /path/to/agent.yaml
```

---

## Error Handling Philosophy

### Layered Approach
1. **Validation errors** → Pydantic raises ValidationError (load time)
2. **Config errors** → ConfigError, AgentSpecError (startup)
3. **Tool errors** → ToolError result (runtime, not exceptions)
4. **LLM errors** → Typed exceptions (APIConnectionError, APIStatusError)
5. **Retry logic** → Tenacity (only retryable errors)

### Exception Hierarchy
```python
KimiCLIException
├── ConfigError
└── AgentSpecError

# From kosong
ChatProviderError
├── APIConnectionError
├── APITimeoutError
└── APIStatusError (status_code available)

# Domain exceptions
LLMNotSet
LLMNotSupported(llm, capabilities)
MaxStepsReached(n_steps)
RunCancelled
BackToTheFuture(checkpoint_id, messages)
```

---

## Performance Considerations

### Token Management
- Context tracks token count (from LLM response)
- Compaction triggered when `token_count + reserved_tokens >= max_context_size`
- Reserved tokens: 50,000 (safety margin)

### Output Limits
- Bash/ReadFile: 50,000 character limit
- Line length: 2,000 characters
- Prevents LLM context bloat from runaway output

### Async Patterns
- Subprocess I/O: streamed in real-time (not buffered)
- File I/O: async (no event loop blocking)
- Approval requests: piped to wire concurrently
- Tool execution: kosong handles parallelization

### Retry Strategy
- Exponential backoff: 0.3s → 5s max, with jitter
- Only retries transient errors: 429, 5xx
- Max 3 attempts per step (configurable)

---

## Operational Insights

### Logging
- **loguru** with structured fields
- Levels: debug, info, warning, error
- Field-based substitution enables JSON logs
- Examples: `logger.debug("Loading agent: {agent_file}", agent_file=...)`

### Monitoring Points
- Step begin/end (step_no, token_count)
- Compaction start/end (context size)
- Tool execution (tool name, parameters, result)
- Approval requests (tool, action, description)
- Retry attempts (error type, attempt #, wait time)

### Debugging Aids
- Checkpoint files (JSONL format, line-per-message)
- D-Mail mechanism (time-travel for recovery)
- Wire messages (visible to UI, logged)
- ContextVar for current tool call

---

## Comparison to Alternatives

### Why Not Service Locators?
- Declarative tool list in YAML is self-documenting
- DI via constructor inspection is more testable
- Type safety prevents wiring errors

### Why ContextVar Instead of Thread-Local?
- Async-safe (task-local, not thread-local)
- Works seamlessly with asyncio
- No need for careful propagation

### Why Checkpoints Instead of In-Memory History?
- Survives process crashes
- Enables time-travel (D-Mail)
- Rotation handles unbounded growth

### Why Pydantic Instead of Dataclasses?
- JSON serialization built-in
- Validators for cross-field constraints
- SecretStr for sensitive fields
- Better error messages

---

## Summary

Kimi CLI is a **production-ready demonstration** of:
- **Modularity**: Each component has one clear responsibility
- **Extensibility**: YAML-driven agent specs + reflection-based tool loading
- **Reliability**: Typed exceptions, retry logic, structured logging
- **Testability**: Composable fixtures, mockable dependencies, async support
- **Clarity**: Semantic naming, self-documenting code, operational transparency

These patterns work together to enable a system that is both **powerful** (concurrent tool execution, time-travel recovery, streaming I/O) and **maintainable** (easy to understand, test, extend, and operate).
