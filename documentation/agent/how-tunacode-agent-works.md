# How the TunaCode Agent Works

TunaCode is a CLI-based AI coding assistant built on top of `pydantic-ai`. This document explains the architecture and flow of the agent system.

## Quick Summary

**TunaCode Agent** = **pydantic-ai** + **9 tools** + **parallel execution** + **interactive REPL**

- **Brain**: pydantic-ai handles LLM communication and tool orchestration
- **Hands**: 9 tools (4 read-only parallel, 5 write/execute sequential)
- **Memory**: StateManager tracks everything (messages, costs, context)
- **Interface**: Rich REPL with commands (/), shell (!), and prompts
- **Efficiency**: Explicit task completion with `TUNACODE_TASK_COMPLETE`
- **Self-Assessment**: Built-in self-evaluation after each iteration (no extra API calls)
- **Safety**: Confirmation prompts for destructive operations

## Architecture Overview





### Core Components

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│      REPL       │────▶│    Agent     │────▶│     LLM     │
│ (prompt_toolkit)│     │(pydantic-ai) │     │  Provider   │
└─────────────────┘     └──────────────┘     └─────────────┘
         │                      │                     │
         │                      ▼                     │
         │              ┌──────────────┐              │
         │              │    Tools     │              │
         │              │  (7 types)   │              │
         │              └──────────────┘              │
         │                      │                     │
         │                      ▼                     │
         │              ┌──────────────┐              │
         └─────────────▶│StateManager  │◀─────────────┘
                        │ (Session)    │
                        └──────────────┘
```

## 1. Agent System (`src/tunacode/core/agents/main.py`)

The agent is the brain of TunaCode, orchestrating interactions between the user, LLM, and tools.

### Key Features:

- **Multi-Provider Support**: Works with Anthropic, OpenAI, Google, OpenRouter
- **Parallel Tool Execution**: Read-only tools run concurrently for 3x speedup
- **Streaming**: Real-time token streaming when supported by the provider
- **Error Recovery**: Automatic retries and fallback JSON parsing

### Agent Lifecycle:

```python
# 1. Agent Creation (lazy, per-model)
agent = get_or_create_agent(model_name, state_manager)

# 2. System Prompt Loading
# - Loads system.md prompt with tool instructions
# - Appends AGENTS.md if present (project context)
# - Adds current todos if any exist
# - Includes TUNACODE_TASK_COMPLETE completion protocol

# 3. Tool Registration
tools = [
    Tool(bash, max_retries=3),
    Tool(glob, max_retries=3),
    Tool(grep, max_retries=3),
    Tool(list_dir, max_retries=3),
    Tool(read_file, max_retries=3),
    Tool(run_command, max_retries=3),
    Tool(todo_tool._execute, max_retries=3),
    Tool(update_file, max_retries=3),
    Tool(write_file, max_retries=3),
]

# 4. MCP Server Integration (if configured)
mcp_servers = get_mcp_servers(state_manager)
```

### Request Processing Flow:

```python
async def process_request(model, message, state_manager, tool_callback, streaming_callback):
    # 1. Get or create agent for the model
    agent = get_or_create_agent(model, state_manager)

    # 2. Create response state to track completion
    response_state = ResponseState()

    # 3. Start iterative processing
    async with agent.iter(message, message_history=mh) as agent_run:
        i = 0
        for node in agent_run:
            # 4. Process each node (request/response cycle)
            await _process_node(node, tool_callback, state_manager, response_state)

            # 5. Self-evaluation protocol (after iteration 2+)
            if i > 1 and not response_state.task_completed:
                # Inject system message prompting self-assessment
                # This is part of the same conversation, not a new API call
                self_eval_prompt = SystemPromptPart(
                    content="Reflect on your progress: Have you completed the user's task? ...",
                    part_kind="system-prompt"
                )
                state_manager.session.messages.append(ModelRequest(parts=[self_eval_prompt]))

            # 6. Check for explicit task completion
            if response_state.task_completed:
                break

            # 7. Check iteration limits
            if i >= max_iterations:
                break

            i += 1

    # 8. Return results or fallback response
    return agent_run
```

## 2. State Management (`src/tunacode/core/state.py`)

The `StateManager` maintains all session state as a single source of truth.

### SessionState Fields:

```python
@dataclass
class SessionState:
    # Configuration
    user_config: UserConfig
    current_model: ModelName

    # Agent & Messages
    agents: dict[str, Any]  # Model -> Agent instances
    messages: MessageHistory

    # Cost Tracking
    total_cost: float
    session_total_usage: dict

    # Tool Management
    tool_ignore: list[ToolName]  # Skip confirmation
    yolo: bool  # Skip all confirmations

    # Context Tracking
    files_in_context: set[str]
    tool_calls: list[dict]
    iteration_count: int

    # UI State
    spinner: Optional[Any]
    is_streaming_active: bool
    show_thoughts: bool

    # Recursive Execution
    current_recursion_depth: int
    task_hierarchy: dict
    iteration_budgets: dict
```

## 3. Tool System

Tools are the agent's way of interacting with the filesystem and system.

### Tool Types:

1. **Read-Only Tools** (can run in parallel, no confirmation needed):
   - `read_file`: Read file contents (up to 4KB)
   - `grep`: Search file contents with regex patterns
   - `list_dir`: List directory contents (up to 200 entries)
   - `glob`: Find files by pattern (up to 1000 files)

2. **Write/Execute Tools** (run sequentially, require confirmation):
   - `write_file`: Create new files (fails if exists)
   - `update_file`: Modify existing files (shows diff)
   - `run_command`/`bash`: Execute shell commands (up to 5KB output)
   - `todo`: Manage task list (no confirmation needed)

### Tool Base Classes:

```python
class BaseTool(ABC):
    """Base for all tools with error handling and logging"""

    async def execute(self, *args, **kwargs):
        try:
            # Log operation
            await self.ui.info(f"{self.tool_name}({args})")

            # Execute tool logic
            result = await self._execute(*args, **kwargs)

            return result
        except ModelRetry:
            # Re-raise for LLM guidance
            raise
        except Exception as e:
            # Handle and wrap errors
            await self._handle_error(e, *args, **kwargs)

    def _get_base_prompt(self) -> str:
        """Load dynamic prompt from XML files"""
        # XML-based prompt injection system (Phase 5)
        # Loads prompts from tools/prompts/*.xml with fallbacks

    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Generate JSON schema from XML or hardcoded fallback"""
        # Dynamic parameter schema generation from XML

class FileBasedTool(BaseTool):
    """Extended base for file operations"""
    # Adds file-specific error handling
```

### Tool Prompt Injection System (Phase 5):

All 12 tools now use XML-based dynamic prompt loading for enhanced flexibility:

```
src/tunacode/tools/prompts/
├── bash_prompt.xml          # Bash command execution
├── exit_plan_mode_prompt.xml # Plan mode controls
├── glob_prompt.xml          # File pattern matching
├── grep_prompt.xml          # Text search
├── list_dir_prompt.xml      # Directory listing
├── present_plan_prompt.xml  # Plan presentation
├── read_file_prompt.xml     # File reading
├── run_command_prompt.xml   # Command execution
├── todo_prompt.xml          # Task management
├── update_file_prompt.xml   # File modification
└── write_file_prompt.xml    # File creation
```

**Benefits:**
- Prompts can be updated without code changes
- Consistent XML structure across all tools
- Secure parsing using defusedxml
- Graceful fallback to hardcoded prompts if XML fails

### Parallel Execution:

When the agent needs multiple read-only tools, they execute concurrently:

```python
# Example: Agent wants to read 3 files
# Instead of: 300ms (sequential)
# We get: 100ms (parallel)

async def execute_tools_parallel(tool_calls, callback):
    max_parallel = os.cpu_count() or 4

    # Execute in batches if needed
    tasks = [execute_with_error_handling(part, node) for part, node in tool_calls]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

## 4. REPL (`src/tunacode/cli/repl.py`)

The REPL provides the interactive shell interface.

### Input Processing:

```
User Input
    │
    ├─> "/" Command ──────> CommandRegistry ──> Execute Command
    │
    ├─> "!" Shell ────────> subprocess.run ──> Shell Output
    │
    └─> Text Prompt ──────> Agent ──────────> LLM Response
                               │
                               ├─> Tool Calls ──> Confirmations
                               │
                               └─> Streaming ───> Live Output
```

### Key Features:

- **Multiline Input**: Via prompt_toolkit with syntax highlighting
- **Command System**: Extensible commands starting with "/"
- **Shell Integration**: Direct shell access with "!"
- **Tool Confirmations**: Safety prompts for write/execute operations
- **Streaming Output**: Real-time display of LLM responses

## 5. Message Flow

### Complete Request Lifecycle:

1. **User Input** → REPL receives prompt
2. **Pre-processing** → Expand file references, update context
3. **Agent Request** → Send to LLM with message history
4. **LLM Response** → Parse response parts:
   - Text content → Display to user
   - Tool calls → Execute with confirmation
   - Thoughts → Show if enabled
5. **Tool Execution**:
   - Group read-only tools → Execute in parallel
   - Write/execute tools → Run sequentially with confirmation
6. **Tool Results** → Feed back to LLM
7. **Self-Evaluation** (after iteration 2+):
   - System message injected: "Reflect on your progress..."
   - Agent assesses if task is complete
   - May respond with TUNACODE_TASK_COMPLETE
8. **Iteration** → Repeat until done or limit reached
9. **Final Output** → Display result or fallback message

### Example Flow:

```
User: "Read all Python files in src/ and find the main function"

1. LLM plans approach
2. Calls glob("src/**/*.py") → Returns 10 files
3. Batches 10 read_file calls → Executes in parallel
4. Calls grep("def main", files) → Searches content
5. Returns findings to user
```

### Example Flow with Completion Detection:

```
User: "What's in the config.json file?"

1. Iteration 1: Agent calls read_file("config.json")
2. Agent receives file content
3. Iteration 2: Agent starts to respond with content
4. Self-evaluation injected: "Reflect on your progress: Have you completed the user's task?..."
5. Iteration 3: Agent responds with:
   TUNACODE_TASK_COMPLETE
   The config.json contains database settings, API endpoints, and feature flags.
6. System detects completion marker
7. Strips marker and shows clean response to user
8. Breaks iteration loop (no more iterations needed)
```

The self-evaluation prompt triggers the agent to assess its work and use the completion marker when appropriate, all within the same API conversation.

## 6. Advanced Features

### Streaming:
- Token-level streaming when supported by provider
- Fallback to content-based streaming
- Live update panel during generation

### Error Recovery:
- Automatic retries for transient failures
- JSON fallback parsing for tool calls
- Graceful degradation for missing features

### Context Management:
- Automatic AGENTS.md loading
- Todo state integration
- File reference expansion (@file syntax)

### Performance Optimizations:
- Parallel read-only tool execution
- 3-second deadline for grep searches
- Efficient message history management

## 7. Self-Evaluation Protocol

### The Genius of Self-Assessment:

TunaCode implements a **zero-cost self-evaluation mechanism** that prompts the agent to assess its own progress without requiring additional API calls:

1. **When It Happens**: After iteration 2 and onwards (not on first iteration)
2. **How It Works**: A system message is injected into the conversation asking the agent to reflect
3. **The Prompt**: "Reflect on your progress: Have you completed the user's task? If so, respond with 'TUNACODE_TASK_COMPLETE' followed by a summary of what was accomplished. If not, continue working on the task."
4. **No Extra API Calls**: This is injected as part of the ongoing conversation flow

### Implementation:

```python
# After iteration 2+, before the next agent response
if i > 1 and not response_state.task_completed:
    # Inject self-evaluation prompt
    system_prompt_part = SystemPromptPart(
        content="Reflect on your progress: Have you completed the user's task? ...",
        part_kind="system-prompt"
    )
    state_manager.session.messages.append(ModelRequest(parts=[system_prompt_part]))

    if state_manager.session.show_thoughts:
        await ui.muted("\n🔄 SELF-EVALUATION: Prompting agent to assess task completion")
```

### Benefits:

- **Efficiency**: Agent can signal completion as soon as the task is done
- **Transparency**: Users see when self-evaluation happens (with thoughts enabled)
- **Zero Overhead**: No additional API calls - it's part of the natural flow
- **Better UX**: Prevents unnecessary iterations when task is already complete

## 8. Task Completion Detection

### How It Works:

The agent now has an **explicit completion mechanism** similar to SWE-agent:

1. **Completion Marker**: The agent includes `TUNACODE_TASK_COMPLETE` at the start of its final response
2. **Automatic Detection**: The system detects this marker and stops iterations
3. **Clean Output**: The marker is stripped before showing the response to users

### Implementation Details:

```python
# In _process_node function
if response_state:
    for part in node.model_response.parts:
        if hasattr(part, "content") and isinstance(part.content, str):
            is_complete, cleaned_content = check_task_completion(part.content)
            if is_complete:
                response_state.task_completed = True
                response_state.has_user_response = True
                part.content = cleaned_content  # Remove marker from output
                break
```

### When The Agent Signals Completion:

- Successfully completed the requested task
- Provided all requested information
- Fixed the bug or implemented the feature
- No more tool calls needed

### Benefits:

- **Efficiency**: Prevents unnecessary iterations after task completion
- **Clarity**: Clear distinction between completed tasks and iteration limits
- **Performance**: Saves API calls and processing time
- **User Experience**: No more "Reached maximum iterations" for completed tasks

## 9. Extensibility

### Adding New Tools:

1. Create tool file in `src/tunacode/tools/`
2. Extend `BaseTool` or `FileBasedTool`
3. Implement `_execute()` method
4. Register in agent's tool list

### Adding Commands:

1. Create command class extending `BaseCommand`
2. Implement `matches()` and `execute()`
3. Register with `@CommandRegistry.register`

### Adding LLM Providers:

1. Configure in model registry
2. Set appropriate API keys
3. Agent handles provider differences

## Comparison with SWE-agent

While TunaCode shares some concepts with SWE-agent (tool-based interaction, iterative processing), it differs in:

1. **Architecture**: Built on pydantic-ai vs custom implementation
2. **Parallelism**: Automatic parallel execution of read-only tools
3. **UI**: Rich interactive REPL with confirmations
4. **Flexibility**: Multi-provider support out of the box
5. **State Management**: Comprehensive session tracking
6. **Error Handling**: Graceful recovery mechanisms
7. **Completion Detection**: Adopted SWE-agent's explicit completion signaling approach

### Key Similarities with SWE-agent:
- Tool-based interaction model
- Iterative processing with LLM
- Explicit task completion signaling (TUNACODE_TASK_COMPLETE vs MINI_SWE_AGENT_FINAL_OUTPUT)

### Key Differences:
- TunaCode is designed for interactive use with human confirmation loops
- SWE-agent is more autonomous and batch-oriented
- TunaCode emphasizes transparency and user control
- SWE-agent focuses on autonomous task completion

The agent is designed for interactive coding assistance rather than autonomous task completion, prioritizing user control and transparency.
