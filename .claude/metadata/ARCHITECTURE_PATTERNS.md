# Kimi CLI Architecture Analysis

A comprehensive examination of 10 high-level architectural patterns that exemplify production-grade software design.

---

## 1. SEPARATION OF CONCERNS

**Core Principle**: Each module has a single, well-defined responsibility. Business logic, configuration, runtime management, and tools are isolated.

### Exemplary Files:

**`src/kimi_cli/config.py`** - Configuration Management
- **Responsibility**: Load, validate, and serialize configuration
- **Key Pattern**: Pydantic BaseModel for schema validation
- **Why It's Exemplary**:
  ```python
  class LLMProvider(BaseModel):
      type: Literal["kimi", "openai_legacy", "openai_responses", "_chaos"]
      api_key: SecretStr  # Sensitive data handling
      
  class Config(BaseModel):
      models: dict[str, LLMModel]
      providers: dict[str, LLMProvider]
      
      @model_validator(mode="after")
      def validate_model(self) -> Self:
          # Cross-field validation ensures referential integrity
  ```
  - Separates data structure from loading/persistence logic
  - `load_config()` and `save_config()` are pure functions
  - Secret handling via `SecretStr` for sensitive fields
  - Validators prevent invalid state at instantiation time

**`src/kimi_cli/soul/runtime.py`** - Runtime State
- **Responsibility**: Aggregate all runtime dependencies without orchestrating them
- **Why It's Exemplary**:
  ```python
  class Runtime(NamedTuple):
      config: Config
      llm: LLM | None
      session: Session
      denwa_renji: DenwaRenji
      approval: Approval
      shell_manager: ShellManager | None
      
      @staticmethod
      async def create(...) -> "Runtime":
          # Factory method for async initialization
          # Purely compositional—no business logic
  ```
  - Immutable NamedTuple ensures no accidental mutation
  - Aggregates dependencies without orchestrating them
  - Factory method handles async initialization

**`src/kimi_cli/soul/context.py`** - Session History Management
- **Responsibility**: Manage conversation history, checkpoints, and token tracking
- **Why It's Exemplary**:
  ```python
  class Context:
      async def checkpoint(self, add_user_message: bool): ...
      async def revert_to(self, checkpoint_id: int): ...
      async def append_message(self, message: Message | Sequence[Message]): ...
  ```
  - Clear async interface for async file I/O
  - Immutable properties (e.g., `history` is a Sequence)
  - File backend abstraction allows different storage implementations

**`src/kimi_cli/tools/` directories** - Tool Isolation
- Each tool in its own module (bash/, file/, web/, task/, etc.)
- Tools depend on injected dependencies, not global state
- Example:
  ```python
  class Bash(CallableTool2[Params]):
      def __init__(self, approval: Approval, **kwargs):
          self._approval = approval
  ```

---

## 2. DECLARATIVE EXTENSIBILITY

**Core Principle**: New behavior is declared in YAML, not coded in Python. Agent specs, tool configurations, and system prompts are separate from implementation.

### Exemplary Files:

**`src/kimi_cli/agentspec.py`** - YAML-Driven Agent Specification
- **Why It's Exemplary**:
  ```python
  class AgentSpec(BaseModel):
      extend: str | None  # Supports inheritance: "default" or relative path
      name: str | None
      system_prompt_path: Path | None
      tools: list[str] | None  # Tool paths: "module.path:ClassName"
      exclude_tools: list[str] | None
      subagents: dict[str, "SubagentSpec"] | None
  ```
  - Recursive extension support (`_load_agent_spec` calls itself for base agents)
  - Tools are declared as strings ("kimi_cli.tools.bash:Bash")
  - System prompt args allow templating without hardcoding
  - YAML files become version-controllable, shareable agent definitions

  ```yaml
  version: 1
  agent:
    name: "Default Agent"
    extend: "default"
    system_prompt_path: "prompt.md"
    tools:
      - "kimi_cli.tools.bash:Bash"
      - "kimi_cli.tools.file.read:ReadFile"
    exclude_tools:
      - "kimi_cli.tools.bash:Bash"  # Can override defaults
  ```

**`src/kimi_cli/soul/agent.py` - _load_tool()** - Dynamic Tool Loading
- **Why It's Exemplary**:
  ```python
  def _load_tool(tool_path: str, dependencies: dict[type[Any], Any]) -> ToolType | None:
      module_name, class_name = tool_path.rsplit(":", 1)
      module = importlib.import_module(module_name)
      cls = getattr(module, class_name, None)
      
      # Automatic dependency injection based on signature
      args: list[type[Any]] = []
      for param in inspect.signature(cls).parameters.values():
          if param.kind == inspect.Parameter.KEYWORD_ONLY:
              break
          if param.annotation not in dependencies:
              raise ValueError(f"Tool dependency not found: {param.annotation}")
          args.append(dependencies[param.annotation])
      return cls(*args)
  ```
  - Tools are loaded via string paths from configuration
  - Reflection-based dependency injection—no registration needed
  - New tools can be added by creating a module and declaring it in YAML
  - Declarative tool composition without changing Python code

**`agents/default/agent.yaml`** Example
  - Provides baseline configuration
  - Custom agents extend it with `extend: "default"`
  - System prompts, model settings, and tools are all declarative

---

## 3. TYPE-FIRST DESIGN

**Core Principle**: Comprehensive type hints and Pydantic models ensure correctness at instantiation time, not runtime.

### Exemplary Files:

**`src/kimi_cli/config.py`** - Pydantic-Based Type Safety
- **Why It's Exemplary**:
  ```python
  class LLMModel(BaseModel):
      provider: str
      model: str
      max_context_size: int
      capabilities: set[LLMModelCapability] | None = None
      
  class Config(BaseModel):
      default_model: str = Field(default="")
      models: dict[str, LLMModel]
      providers: dict[str, LLMProvider]
      
      @model_validator(mode="after")
      def validate_model(self) -> Self:
          if self.default_model and self.default_model not in self.models:
              raise ValueError(...)
          for model in self.models.values():
              if model.provider not in self.providers:
                  raise ValueError(...)
          return self
  ```
  - Pydantic enforces type validation and constraints
  - `Field()` descriptors add semantic information
  - Cross-field validators (mode="after") check invariants
  - JSON serialization automatically handles `SecretStr`
  - Invalid configurations fail at load time, not at use time

**`src/kimi_cli/tools/bash/__init__.py`** - Params Model
- **Why It's Exemplary**:
  ```python
  class Params(BaseModel):
      command: str = Field(description="The bash command to execute.")
      timeout: int = Field(
          description=...,
          default=60,
          ge=1,  # Greater than or equal
          le=MAX_TIMEOUT,  # Less than or equal
      )
  
  class Bash(CallableTool2[Params]):
      async def __call__(self, params: Params) -> ToolReturnType:
  ```
  - Generic `CallableTool2[Params]` binds parameter type
  - Field constraints (`ge`, `le`) prevent invalid values upfront
  - Descriptions auto-generated for LLM schema

**`src/kimi_cli/soul/__init__.py`** - Type-Safe Protocol
- **Why It's Exemplary**:
  ```python
  class LLMNotSupported(Exception):
      def __init__(self, llm: LLM, capabilities: list[str]):
          self.llm = llm
          self.capabilities = capabilities
  
  @runtime_checkable
  class Soul(Protocol):
      @property
      def name(self) -> str: ...
      
      @property
      def model(self) -> str: ...
      
      async def run(self, user_input: str | list[ContentPart]):
          """Raises: LLMNotSet, LLMNotSupported, MaxStepsReached, ..."""
      
  class KimiSoul(Soul):  # Verified by type checker
      ...
  ```
  - Protocol defines the interface; KimiSoul implements it
  - Exceptions specify their semantic meaning (not just string)
  - TYPE_CHECKING block for static verification without runtime cost

**`src/kimi_cli/llm.py`** - NamedTuple + Type Aliases
- **Why It's Exemplary**:
  ```python
  class LLM(NamedTuple):
      chat_provider: ChatProvider
      max_context_size: int
      capabilities: set[LLMModelCapability]
      
      @property
      def supports_image_in(self) -> bool:
          return "image_in" in self.capabilities
  ```
  - Immutable by design (NamedTuple)
  - Computed properties for derived data
  - Type aliases prevent magic strings

---

## 4. CONSTRUCTOR-BASED DEPENDENCY INJECTION

**Core Principle**: Dependencies are declared in `__init__` signatures and injected at instantiation. No service locators, no global singletons.

### Exemplary Files:

**`src/kimi_cli/tools/bash/__init__.py`** - Simple Constructor Injection
- **Why It's Exemplary**:
  ```python
  class Bash(CallableTool2[Params]):
      def __init__(self, approval: Approval, **kwargs):
          super().__init__(**kwargs)
          self._approval = approval
      
      async def __call__(self, params: Params) -> ToolReturnType:
          if not await self._approval.request(...):
              return ToolRejectedError()
  ```
  - Clear positional parameter declares dependency
  - No global `get_approval()` lookup
  - Testable: inject a mock Approval in tests

**`src/kimi_cli/tools/file/read.py`** - Parameter Type as Dependency
- **Why It's Exemplary**:
  ```python
  class ReadFile(CallableTool2[Params]):
      def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs):
          super().__init__(**kwargs)
          self._work_dir = builtin_args.KIMI_WORK_DIR
  ```
  - Injected type (BuiltinSystemPromptArgs) is semantic, not generic
  - Type system prevents accidental wiring errors
  - `_work_dir` is cached as instance variable (safe for async)

**`src/kimi_cli/soul/agent.py` - _load_tool()** - Reflection-Based DI
- **Why It's Exemplary**:
  ```python
  tool_deps = {
      ResolvedAgentSpec: agent_spec,
      Runtime: runtime,
      Config: runtime.config,
      BuiltinSystemPromptArgs: runtime.builtin_args,
      Session: runtime.session,
      DenwaRenji: runtime.denwa_renji,
      Approval: runtime.approval,
      ShellManager: runtime.shell_manager,
  }
  
  # Inspect tool's __init__ signature and wire dependencies
  for param in inspect.signature(cls).parameters.values():
      if param.annotation not in dependencies:
          raise ValueError(f"Tool dependency not found: {param.annotation}")
      args.append(dependencies[param.annotation])
  return cls(*args)
  ```
  - Registry of types → instances
  - Constructor inspection discovers required dependencies
  - Keyword-only parameters stop dependency injection (allows **kwargs)
  - Type mismatch raises ValueError before tool loads

**`src/kimi_cli/soul/runtime.py` - Runtime.create()** - Async Factory
- **Why It's Exemplary**:
  ```python
  @staticmethod
  async def create(config: Config, llm: LLM | None, ...) -> "Runtime":
      ls_output, agents_md = await asyncio.gather(
          asyncio.to_thread(_list_work_dir, session.work_dir),
          asyncio.to_thread(load_agents_md, session.work_dir),
      )
      
      shell_manager = None
      if config.persistent_shell.enabled:
          shell_manager = ShellManager(config.persistent_shell)
      
      return Runtime(
          config=config,
          llm=llm,
          session=session,
          builtin_args=BuiltinSystemPromptArgs(...),
          denwa_renji=DenwaRenji(),
          approval=Approval(yolo=yolo),
          shell_manager=shell_manager,
      )
  ```
  - Factory pattern for complex async initialization
  - All dependencies are injected; none are global
  - Optional dependencies checked at factory time

---

## 5. EXPLICIT RESULT TYPES

**Core Principle**: Functions return structured, typed results, not strings or untyped tuples. Result types encode success, failure, and optional side information.

### Exemplary Files:

**`src/kimi_cli/tools/utils.py` - ToolResultBuilder** - Result Abstraction
- **Why It's Exemplary**:
  ```python
  class ToolResultBuilder:
      def ok(self, message: str = "", *, brief: str = "") -> ToolOk:
          """Create a ToolOk result with the current output."""
          output = "".join(self._buffer)
          return ToolOk(output=output, message=final_message, brief=brief)
      
      def error(self, message: str, *, brief: str) -> ToolError:
          """Create a ToolError result with the current output."""
          output = "".join(self._buffer)
          return ToolError(output=output, message=final_message, brief=brief)
  ```
  - Builds output incrementally with limits
  - Returns typed result (ToolOk or ToolError)
  - Distinguishes `message` (detailed) from `brief` (concise)
  - Handles truncation metadata transparently

**`src/kimi_cli/tools/bash/__init__.py`** - Tool Result Pattern
- **Why It's Exemplary**:
  ```python
  class Bash(CallableTool2[Params]):
      async def __call__(self, params: Params) -> ToolReturnType:
          builder = ToolResultBuilder()
          
          if not await self._approval.request(...):
              return ToolRejectedError()  # Explicit rejection
          
          try:
              exitcode = await _stream_subprocess(...)
              
              if exitcode == 0:
                  return builder.ok("Command executed successfully.")
              else:
                  return builder.error(
                      f"Command failed with exit code: {exitcode}.",
                      brief=f"Failed with exit code: {exitcode}",
                  )
          except TimeoutError:
              return builder.error(
                  f"Command killed by timeout ({params.timeout}s)",
                  brief=f"Killed by timeout ({params.timeout}s)",
              )
  ```
  - No exceptions bubbling up; all cases handled explicitly
  - Result type (ToolOk, ToolError, ToolRejectedError) encodes outcome
  - Brief messages for UI, detailed messages for context

**`src/kimi_cli/soul/kimisoul.py` - StepResult Pattern**
- **Why It's Exemplary**:
  ```python
  result = await kosong.step(...)  # Returns StepResult
  
  if result.usage is not None:
      await self._context.update_token_count(result.usage.input)
      wire_send(StatusUpdate(status=self.status))
  
  results = await result.tool_results()  # Async result gathering
  
  rejected = any(isinstance(result.result, ToolRejectedError) for result in results)
  if rejected:
      return True  # Early return on rejection
  ```
  - StepResult bundles all information from one LLM step
  - `tool_results()` is async—respects concurrent tool execution
  - Explicit checking for rejection vs. normal completion

**`src/kimi_cli/soul/__init__.py` - Exception Hierarchy**
- **Why It's Exemplary**:
  ```python
  class LLMNotSet(Exception): pass
  
  class LLMNotSupported(Exception):
      def __init__(self, llm: LLM, capabilities: list[str]):
          self.llm = llm  # Structured data, not string
          self.capabilities = capabilities
  
  class MaxStepsReached(Exception):
      n_steps: int
  
  class RunCancelled(Exception): pass
  ```
  - Exception types encode the category of error
  - Structured fields allow recovery logic
  - Distinct from generic RuntimeError

---

## 6. ASYNC-BY-DEFAULT I/O

**Core Principle**: All I/O operations are async. Timeouts, cancellation, and cleanup are built into the control flow.

### Exemplary Files:

**`src/kimi_cli/shell_manager.py`** - Async Shell Execution
- **Why It's Exemplary** (from docstring and design):
  ```python
  class ShellManager:
      """
      Manages persistent shell sessions.
      
      The ShellManager maintains a long-running bash subprocess that persists
      state across multiple command executions.
      """
      
      # (Implementation includes async session management and cleanup)
  ```
  - Persistent subprocess, not spawning a new shell per command
  - Async process management with proper cleanup
  - Stateful (cd, export persist across commands)

**`src/kimi_cli/tools/bash/__init__.py` - _stream_subprocess()**
- **Why It's Exemplary**:
  ```python
  async def _stream_subprocess(command: str, stdout_cb, stderr_cb, timeout: int) -> int:
      async def _read_stream(stream, cb):
          while True:
              line = await stream.readline()
              if line:
                  cb(line)
              else:
                  break
      
      process = await asyncio.create_subprocess_shell(
          command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
      )
      
      try:
          await asyncio.wait_for(
              asyncio.gather(
                  _read_stream(process.stdout, stdout_cb),
                  _read_stream(process.stderr, stderr_cb),
              ),
              timeout,
          )
          return await process.wait()
      except TimeoutError:
          process.kill()
          raise
  ```
  - Streams stdout and stderr concurrently
  - Timeout enforced via `asyncio.wait_for()`
  - Proper cleanup: `process.kill()` on timeout
  - Callbacks for real-time output handling

**`src/kimi_cli/soul/context.py`** - Async File I/O
- **Why It's Exemplary**:
  ```python
  async def restore(self) -> bool:
      async with aiofiles.open(self._file_backend, encoding="utf-8") as f:
          async for line in f:
              if not line.strip():
                  continue
              line_json = json.loads(line)
              # ...
      return True
  
  async def revert_to(self, checkpoint_id: int):
      async with (
          aiofiles.open(rotated_file_path, encoding="utf-8") as old_file,
          aiofiles.open(self._file_backend, "w", encoding="utf-8") as new_file,
      ):
          async for line in old_file:
              # ...
  ```
  - All file I/O is async (aiofiles)
  - No blocking in event loop
  - Async context managers ensure cleanup

**`src/kimi_cli/soul/kimisoul.py` - _agent_loop()**
- **Why It's Exemplary**:
  ```python
  while True:
      wire_send(StepBegin(step_no))
      approval_task = asyncio.create_task(_pipe_approval_to_wire())
      
      try:
          if (
              self._context.token_count + self._reserved_tokens
              >= self._runtime.llm.max_context_size
          ):
              wire_send(CompactionBegin())
              await self.compact_context()
              wire_send(CompactionEnd())
          
          finished = await self._step()
      finally:
          approval_task.cancel()  # Cleanup regardless of outcome
  ```
  - Multiple concurrent tasks (approval + step)
  - Guaranteed cleanup via finally block
  - Cancellation-safe (except for approval task)

**`src/kimi_cli/soul/__init__.py` - run_soul()**
- **Why It's Exemplary**:
  ```python
  async def run_soul(soul: "Soul", user_input: str | list[ContentPart],
                     ui_loop_fn: UILoopFn, cancel_event: asyncio.Event) -> None:
      wire = Wire()
      wire_token = _current_wire.set(wire)
      
      ui_task = asyncio.create_task(ui_loop_fn(wire.ui_side))
      soul_task = asyncio.create_task(soul.run(user_input))
      cancel_event_task = asyncio.create_task(cancel_event.wait())
      
      await asyncio.wait([soul_task, cancel_event_task],
                        return_when=asyncio.FIRST_COMPLETED)
      
      try:
          if cancel_event.is_set():
              soul_task.cancel()
              # ...
      finally:
          wire.shutdown()
          try:
              await asyncio.wait_for(ui_task, timeout=0.5)
          except asyncio.QueueShutDown:
              pass  # Expected
          except TimeoutError:
              logger.warning("UI loop timed out")
          _current_wire.reset(wire_token)
  ```
  - Dual tasks (soul + UI) with cancellation support
  - Timeout on cleanup (0.5s)
  - Exception handling for graceful shutdown
  - Context variable cleanup via reset

---

## 7. PRODUCTION-GRADE ERROR FLOW

**Core Principle**: Exceptions are typed, chained, and distinguishable. Retry logic is explicit. Error paths are testable.

### Exemplary Files:

**`src/kimi_cli/exception.py`** - Exception Hierarchy
- **Why It's Exemplary**:
  ```python
  class KimiCLIException(Exception):
      """Base exception class for Kimi CLI."""
      pass
  
  class ConfigError(KimiCLIException):
      """Configuration error."""
      pass
  
  class AgentSpecError(KimiCLIException):
      """Agent specification error."""
      pass
  ```
  - Specific exceptions for different error categories
  - Hierarchy allows catching broad or specific errors
  - Can be caught and logged distinctly from other exceptions

**`src/kimi_cli/config.py` - load_config()** - Error Chaining
- **Why It's Exemplary**:
  ```python
  def load_config(config_file: Path | None = None) -> Config:
      try:
          with open(config_file, encoding="utf-8") as f:
              data = json.load(f)
          return Config(**data)
      except json.JSONDecodeError as e:
          raise ConfigError(f"Invalid JSON in configuration file: {e}") from e
      except ValidationError as e:
          raise ConfigError(f"Invalid configuration file: {e}") from e
  ```
  - Specific error messages ("Invalid JSON", "Invalid configuration")
  - Original exception chained via `from e`
  - Caller sees ConfigError, not json.JSONDecodeError
  - Stacktrace preserved for debugging

**`src/kimi_cli/agentspec.py` - _load_agent_spec()** - Validation with Context
- **Why It's Exemplary**:
  ```python
  def _load_agent_spec(agent_file: Path) -> AgentSpec:
      assert agent_file.is_file(), "expect agent file to exist"
      try:
          with open(agent_file, encoding="utf-8") as f:
              data: dict[str, Any] = yaml.safe_load(f)
      except yaml.YAMLError as e:
          raise AgentSpecError(f"Invalid YAML in agent spec file: {e}") from e
      
      version = data.get("version", 1)
      if version != 1:
          raise AgentSpecError(f"Unsupported agent spec version: {version}")
      
      agent_spec = AgentSpec(**data.get("agent", {}))
      # ... validation continues with semantics
  ```
  - Errors include file context
  - Version mismatch caught early
  - Pydantic validation errors wrapped in AgentSpecError

**`src/kimi_cli/soul/kimisoul.py` - Retry Logic with Tenacity**
- **Why It's Exemplary**:
  ```python
  @tenacity.retry(
      retry=retry_if_exception(self._is_retryable_error),
      before_sleep=partial(self._retry_log, "step"),
      wait=wait_exponential_jitter(initial=0.3, max=5, jitter=0.5),
      stop=stop_after_attempt(self._loop_control.max_retries_per_step),
      reraise=True,
  )
  async def _kosong_step_with_retry() -> StepResult:
      return await kosong.step(...)
  
  result = await _kosong_step_with_retry()
  ```
  - Declarative retry policy
  - Retries only if `_is_retryable_error()` returns True
  - Exponential backoff with jitter (standard practice)
  - Max attempts enforced
  - Original exception re-raised after exhaustion

**`src/kimi_cli/soul/kimisoul.py` - _is_retryable_error()**
- **Why It's Exemplary**:
  ```python
  @staticmethod
  def _is_retryable_error(exception: BaseException) -> bool:
      if isinstance(exception, (APIConnectionError, APITimeoutError)):
          return True
      return isinstance(exception, APIStatusError) and exception.status_code in (
          429,  # Too Many Requests
          500,  # Internal Server Error
          502,  # Bad Gateway
          503,  # Service Unavailable
      )
  ```
  - Only retryable errors are retried (not validation errors)
  - HTTP status codes are explicit (comments explain meaning)
  - Transient errors (5xx, 429) distinguished from permanent errors

**`src/kimi_cli/tools/file/read.py` - Error Handling**
- **Why It's Exemplary**:
  ```python
  async def __call__(self, params: Params) -> ToolReturnType:
      try:
          p = Path(params.path)
          
          if not p.is_absolute():
              return ToolError(
                  message=f"`{params.path}` is not an absolute path.",
                  brief="Invalid path",
              )
          
          if not p.exists():
              return ToolError(
                  message=f"`{params.path}` does not exist.",
                  brief="File not found",
              )
          
          # ... happy path ...
      except Exception as e:
          return ToolError(
              message=f"Failed to read {params.path}. Error: {e}",
              brief="Failed to read file",
          )
  ```
  - Validation errors returned as ToolError (not exceptions)
  - Catch-all for unexpected errors (generic Exception)
  - Error messages include context (filename, expected path format)
  - Brief message for UI summary

---

## 8. CONSISTENT OUTPUT BUILDING

**Core Principle**: Tool outputs are built incrementally with uniform limits (character count, line length). Truncation is transparent and consistent.

### Exemplary Files:

**`src/kimi_cli/tools/utils.py` - ToolResultBuilder** - Output Abstraction
- **Why It's Exemplary**:
  ```python
  DEFAULT_MAX_CHARS = 50_000
  DEFAULT_MAX_LINE_LENGTH = 2000
  
  class ToolResultBuilder:
      def __init__(self, max_chars: int = DEFAULT_MAX_CHARS,
                   max_line_length: int | None = DEFAULT_MAX_LINE_LENGTH):
          self._buffer: list[str] = []
          self._n_chars = 0
          self._truncation_happened = False
      
      def write(self, text: str) -> int:
          """Write text, respecting limits. Returns chars written."""
          if self.is_full:
              return 0
          
          lines = text.splitlines(keepends=True)
          chars_written = 0
          
          for line in lines:
              if self.is_full:
                  break
              
              remaining_chars = self.max_chars - self._n_chars
              limit = (min(remaining_chars, self.max_line_length)
                      if self.max_line_length is not None
                      else remaining_chars)
              line = truncate_line(line, limit, self._marker)
              
              if line != original_line:
                  self._truncation_happened = True
              
              self._buffer.append(line)
              chars_written += len(line)
              self._n_chars += len(line)
              if line.endswith("\n"):
                  self._n_lines += 1
          
          return chars_written
      
      def ok(self, message: str = "", *, brief: str = "") -> ToolOk:
          output = "".join(self._buffer)
          
          final_message = message
          if final_message and not final_message.endswith("."):
              final_message += "."
          
          truncation_msg = "Output is truncated to fit in the message."
          if self._truncation_happened:
              if final_message:
                  final_message += f" {truncation_msg}"
              else:
                  final_message = truncation_msg
          
          return ToolOk(output=output, message=final_message, brief=brief)
  ```
  - Dual limits: character count AND line length
  - `write()` is incremental and returns bytes written
  - Truncation flag enables metadata in result
  - Automatic sentence ending (adds "." if missing)
  - Both ToolOk and ToolError use the same builder

**`src/kimi_cli/tools/utils.py` - truncate_line()**
- **Why It's Exemplary**:
  ```python
  def truncate_line(line: str, max_length: int, marker: str = "...") -> str:
      """
      Truncate a line if it exceeds `max_length`, preserving the beginning and the line break.
      """
      if len(line) <= max_length:
          return line
      
      # Find line breaks at the end of the line
      m = re.search(r"[\r\n]+$", line)
      linebreak = m.group(0) if m else ""
      end = marker + linebreak
      max_length = max(max_length, len(end))
      return line[: max_length - len(end)] + end
  ```
  - Preserves line breaks in output
  - Ensures marker fits (doesn't fail on tiny limits)
  - Regex handles CRLF correctly

**`src/kimi_cli/tools/bash/__init__.py`** - Builder Usage
- **Why It's Exemplary**:
  ```python
  async def __call__(self, params: Params) -> ToolReturnType:
      builder = ToolResultBuilder()
      
      def stdout_cb(line: bytes):
          line_str = line.decode(errors="replace")
          builder.write(line_str)
      
      def stderr_cb(line: bytes):
          line_str = line.decode(errors="replace")
          builder.write(line_str)
      
      exitcode = await _stream_subprocess(
          params.command, stdout_cb, stderr_cb, params.timeout
      )
      
      if exitcode == 0:
          return builder.ok("Command executed successfully.")
      else:
          return builder.error(..., brief=...)
  ```
  - Callbacks feed output to builder as it streams
  - No manual truncation logic in tool
  - Same result building pattern across all tools

**Tests in `tests/test_result_builder.py`** - Comprehensive Coverage
- **Why It's Exemplary**:
  ```python
  def test_char_limit_truncation():
      builder = ToolResultBuilder(max_chars=10)
      written1 = builder.write("Hello")
      written2 = builder.write(" world!")
      assert written2 == 14  # Includes marker
      assert builder.is_full
      
      result = builder.ok("Operation completed")
      assert "Output is truncated" in result.message
  
  def test_line_length_limit():
      builder = ToolResultBuilder(max_chars=100, max_line_length=20)
      written = builder.write("This is a very long line that should be truncated\n")
      assert "[...truncated]" in result.output
  ```
  - Tests both limits independently and together
  - Verifies truncation metadata is present
  - Edge cases: empty writes, writes when full, multiline handling

---

## 9. TESTABILITY

**Core Principle**: Code is organized so dependencies can be mocked. Async code is testable. Fixtures are reusable and composed.

### Exemplary Files:

**`tests/conftest.py`** - Fixture Composition
- **Why It's Exemplary**:
  ```python
  @pytest.fixture
  def config() -> Config:
      return get_default_config()
  
  @pytest.fixture
  def llm() -> LLM:
      return LLM(
          chat_provider=MockChatProvider([]),  # Mock, not real API
          max_context_size=100_000,
          capabilities=set(),
      )
  
  @pytest.fixture
  def temp_work_dir() -> Generator[Path]:
      with tempfile.TemporaryDirectory() as tmpdir:
          yield Path(tmpdir)
  
  @pytest.fixture
  def builtin_args(temp_work_dir: Path) -> BuiltinSystemPromptArgs:
      return BuiltinSystemPromptArgs(
          KIMI_NOW="1970-01-01T00:00:00+00:00",
          KIMI_WORK_DIR=temp_work_dir,
          KIMI_WORK_DIR_LS="Test ls content",
          KIMI_AGENTS_MD="Test agents content",
      )
  
  @pytest.fixture
  def runtime(config, llm, builtin_args, denwa_renji, session, approval) -> Runtime:
      return Runtime(
          config=config,
          llm=llm,
          builtin_args=builtin_args,
          denwa_renji=denwa_renji,
          session=session,
          approval=approval,
          shell_manager=None,
      )
  
  @pytest.fixture
  def bash_tool(approval: Approval) -> Generator[Bash]:
      with tool_call_context("Bash"):
          yield Bash(approval)
  ```
  - Fixtures compose other fixtures
  - Mocks are explicit (MockChatProvider, Approval(yolo=True))
  - Temp directories auto-cleanup
  - `tool_call_context()` context manager sets up ContextVar for tools
  - Each tool fixture depends on its injection requirements

**`src/kimi_cli/soul/toolset.py`** - ContextVar for Testing
- **Why It's Exemplary**:
  ```python
  current_tool_call = ContextVar[ToolCall | None]("current_tool_call", default=None)
  
  def get_current_tool_call_or_none() -> ToolCall | None:
      """Expect to be not None when called from a `__call__` method of a tool."""
      return current_tool_call.get()
  
  class CustomToolset(SimpleToolset):
      def handle(self, tool_call: ToolCall) -> HandleResult:
          token = current_tool_call.set(tool_call)
          try:
              return super().handle(tool_call)
          finally:
              current_tool_call.reset(token)
  ```
  - ContextVar allows tools to access their own tool call without parameter passing
  - Testable: `tool_call_context()` fixture sets the context variable
  - Async-safe (contextvars are task-local)

**`tests/test_bash.py`** - Async Test Coverage
- **Why It's Exemplary**:
  ```python
  @pytest.mark.asyncio
  async def test_simple_command(bash_tool: Bash):
      result = await bash_tool(Params(command="echo 'Hello World'"))
      assert result == snapshot(ToolOk(output="Hello World\n", ...))
  
  @pytest.mark.asyncio
  async def test_command_with_error(bash_tool: Bash):
      result = await bash_tool(Params(command="ls /nonexistent/directory"))
      assert isinstance(result, ToolError)
      assert "No such file or directory" in result.output
  
  @pytest.mark.asyncio
  async def test_command_timeout_expires(bash_tool: Bash):
      result = await bash_tool(Params(command="sleep 2", timeout=1))
      assert result == snapshot(
          ToolError(message="Command killed by timeout (1s)", ...)
      )
  
  @pytest.mark.asyncio
  async def test_output_truncation_on_success(bash_tool: Bash):
      oversize_length = DEFAULT_MAX_CHARS + 1000
      result = await bash_tool(
          Params(command=f"python3 -c \"print('X' * {oversize_length})\"")
      )
      assert isinstance(result, ToolOk)
      assert "Output is truncated" in result.message
  ```
  - Async tests with `@pytest.mark.asyncio`
  - Mocks entire subprocess (no real shell)
  - Tests both success and error paths
  - Timeout behavior tested directly
  - Truncation tested with deterministic command

**`tests/test_result_builder.py`** - Unit Tests for Builder
- **Why It's Exemplary**:
  ```python
  def test_char_limit_truncation():
      builder = ToolResultBuilder(max_chars=10)
      written1 = builder.write("Hello")
      written2 = builder.write(" world!")
      
      assert written1 == 5
      assert written2 == 14
      assert builder.is_full
      
      result = builder.ok("Operation completed")
      assert "Output is truncated" in result.message
  ```
  - Pure unit tests (no async, no fixtures needed for basic tests)
  - Tests invariants (is_full, n_chars, n_lines)
  - Tests boundary conditions (empty, exactly full, overflow)

---

## 10. OPERATIONAL CLARITY

**Core Principle**: Code is readable, naming is explicit, logging is structured. Developers can understand system behavior from code alone.

### Exemplary Files:

**`src/kimi_cli/utils/logging.py`** - Structured Logging
- **Why It's Exemplary**: Uses loguru for structured logging
  ```python
  from kimi_cli.utils.logging import logger
  
  # Throughout codebase:
  logger.debug("Loading agent: {agent_file}", agent_file=agent_file)
  logger.info("Loaded agents.md: {path}", path=path)
  logger.warning("UI loop timed out")
  logger.error("Checkpoint {checkpoint_id} does not exist", checkpoint_id=checkpoint_id)
  ```
  - Structured fields (e.g., `agent_file=agent_file`) enable JSON logs
  - Log levels used consistently (debug, info, warning, error)
  - No string formatting; field-based substitution

**`src/kimi_cli/soul/context.py`** - Clear Method Naming and Docstrings
- **Why It's Exemplary**:
  ```python
  async def checkpoint(self, add_user_message: bool):
      """Create a checkpoint at the current point in the conversation."""
      checkpoint_id = self._next_checkpoint_id
      self._next_checkpoint_id += 1
  
  async def revert_to(self, checkpoint_id: int):
      """
      Revert the context to the specified checkpoint.
      After this, the specified checkpoint and all subsequent content will be
      removed from the context. File backend will be rotated.
      
      Args:
          checkpoint_id (int): The ID of the checkpoint to revert to. 0 is the first checkpoint.
      
      Raises:
          ValueError: When the checkpoint does not exist.
          RuntimeError: When no available rotation path is found.
      """
  ```
  - Method names are action-oriented (checkpoint, revert_to, append_message)
  - Docstrings explain *what* and *why*, not just parameters
  - Side effects are documented (file rotation, state changes)
  - Exceptions are listed with semantic meaning

**`src/kimi_cli/shell_manager.py`** - Clear Class Responsibility
- **Why It's Exemplary**:
  ```python
  class ShellManager:
      """
      Manages persistent shell sessions.
      
      The ShellManager maintains a long-running bash subprocess that persists
      state across multiple command executions. This allows commands to modify
      the environment (cd, export, etc.) and have those changes persist for
      subsequent commands.
      
      Example:
          ```python
          config = PersistentShellConfig(enabled=True)
          manager = ShellManager(config)
          
          await manager.execute("cd /tmp")
          await manager.execute("export FOO=bar")
          await manager.cleanup()
          ```
      """
  ```
  - Docstring explains the *why* (persistent state)
  - Example usage in docstring
  - Single responsibility: manage shell sessions

**`src/kimi_cli/agentspec.py`** - Semantic Type Aliases and Enums
- **Why It's Exemplary**:
  ```python
  LLMModelCapability = Literal["image_in"]
  # vs. some_config.capabilities = {"image_in", "code_execution", "web_search"}
  # ^ Makes it clear what capabilities are valid
  
  class AgentSpec(BaseModel):
      extend: str | None = Field(default=None, description="Agent file to extend")
      name: str | None = Field(default=None, description="Agent name")  # required
      system_prompt_path: Path | None = Field(...)  # required
      tools: list[str] | None = Field(default=None, description="Tools")  # required
  ```
  - Literal types prevent invalid string values
  - Field descriptions are executable documentation
  - Comments clarify intent (required, optional semantics)

**`src/kimi_cli/config.py`** - Validation Error Messages
- **Why It's Exemplary**:
  ```python
  @model_validator(mode="after")
  def validate_model(self) -> Self:
      if self.default_model and self.default_model not in self.models:
          raise ValueError(f"Default model {self.default_model} not found in models")
      for model in self.models.values():
          if model.provider not in self.providers:
              raise ValueError(f"Provider {model.provider} not found in providers")
      return self
  ```
  - Error messages include the actual values (model name, provider name)
  - Messages are actionable ("not found in models")

**`src/kimi_cli/soul/kimisoul.py` - Step-by-Step Clarity**
- **Why It's Exemplary**:
  ```python
  async def _agent_loop(self):
      """The main agent loop for one run."""
      step_no = 1
      while True:
          wire_send(StepBegin(step_no))
          approval_task = asyncio.create_task(_pipe_approval_to_wire())
          
          try:
              # compact the context if needed
              if (self._context.token_count + self._reserved_tokens
                  >= self._runtime.llm.max_context_size):
                  logger.info("Context too long, compacting...")
                  wire_send(CompactionBegin())
                  await self.compact_context()
                  wire_send(CompactionEnd())
              
              # run a single step
              finished = await self._step()
          except BackToTheFuture as e:
              # handle time-travel (D-Mail revert)
              await self._context.revert_to(e.checkpoint_id)
              # ...
          except (ChatProviderError, asyncio.CancelledError):
              # handle cancellation
              wire_send(StepInterrupted())
              raise
          finally:
              approval_task.cancel()
          
          if finished:
              return
          
          step_no += 1
          if step_no > self._loop_control.max_steps_per_run:
              raise MaxStepsReached(...)
  ```
  - Comments clarify *what* is happening at high level
  - Exception names are semantic (BackToTheFuture, not RuntimeError)
  - Control flow is easy to follow: try→except→finally
  - Each step is logged

**`src/kimi_cli/tools/__init__.py`** - Brief Tool Descriptions
- **Why It's Exemplary**: Tool descriptions are loaded from separate `.md` files
  ```python
  class ReadFile(CallableTool2[Params]):
      description: str = load_desc(
          Path(__file__).parent / "read.md",
          {"MAX_LINES": str(MAX_LINES), ...},
      )
  ```
  - Tool descriptions are not buried in Python strings
  - Markdown files can be version-controlled and updated separately
  - Descriptions can include examples, constraints, warnings

---

## Summary Table

| Pattern | Primary File | Key Insight |
|---------|--------------|-------------|
| **Separation of Concerns** | `config.py`, `soul/runtime.py`, `soul/context.py` | Each module owns one responsibility; config is separate from loading. |
| **Declarative Extensibility** | `agentspec.py`, `soul/agent.py::_load_tool()` | YAML drives agent config; tools are loaded via string paths. |
| **Type-First Design** | `config.py`, `tools/bash/__init__.py`, `llm.py` | Pydantic + type hints enforce correctness at instantiation. |
| **Constructor-Based DI** | `tools/bash/__init__.py`, `soul/agent.py::_load_tool()` | Dependencies are constructor parameters; no service locators. |
| **Explicit Result Types** | `tools/utils.py::ToolResultBuilder`, `soul/__init__.py` | Functions return typed results (ToolOk, ToolError) not strings. |
| **Async-by-Default I/O** | `soul/context.py`, `tools/bash/__init__.py`, `soul/kimisoul.py` | All I/O is async; timeouts and cleanup are built-in. |
| **Production-Grade Error Flow** | `exception.py`, `config.py::load_config()`, `soul/kimisoul.py::_is_retryable_error()` | Typed exceptions, error chaining, selective retry logic. |
| **Consistent Output Building** | `tools/utils.py::ToolResultBuilder` | Uniform limits (chars, line length); truncation is transparent. |
| **Testability** | `conftest.py`, `soul/toolset.py::ContextVar`, `test_bash.py` | Fixtures compose; mocks are explicit; async tests work. |
| **Operational Clarity** | `soul/context.py`, `shell_manager.py`, `agentspec.py` | Naming is semantic; docstrings explain the *why*; logging is structured. |

---

## Key Takeaways

1. **Configuration as Code**: Agent specs are YAML files with validation. No hardcoding of tool paths or system prompts in Python.

2. **Reflection-Based Wiring**: Tool dependencies are discovered via `inspect.signature()`, not a registration system. This reduces boilerplate.

3. **Context Variables for Async**: `ContextVar` enables tools to access their own tool call context without threading parameters through all layers.

4. **Wire Pattern**: Soul ↔ UI communication happens through a `Wire` abstraction with two async queues, enabling real-time streaming of LLM output and approval requests.

5. **Explicit Checkpointing**: Context maintains checkpoints on disk; `BackToTheFuture` exception triggers reverts, enabling D-Mail (time-travel messaging) and recovery.

6. **Output Limits are Composable**: `ToolResultBuilder` is a reusable component across all tools, ensuring consistent truncation and metadata.

7. **Structured Logging**: `loguru` with field-based logging enables JSON-structured logs for monitoring and debugging.

8. **Async Cleanup**: All resources (processes, files, tasks) are cleaned up via async context managers and finally blocks, respecting cancellation.

9. **Pydantic for Validation**: All config and parameters are Pydantic models, catching errors at instantiation time, not at runtime.

10. **Testing Fixtures as Contract**: Fixtures in `conftest.py` define the testing contract. New tests need only the fixtures they depend on.

