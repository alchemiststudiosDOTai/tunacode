# TunaCode Main Agent Architecture

## Overview

The TunaCode agent system follows a clean modular architecture with single source of truth principles:

- **Main orchestrator** (`src/tunacode/core/agents/main.py`) - Central request processing and coordination
- **Agent components** (`src/tunacode/core/agents/agent_components/`) - Modular functionality with specific responsibilities
- **Direct imports** - No re-export layers, clean dependency graph

The main agent is responsible for:
- Processing user requests through the agent orchestration
- Coordinating with specialized agent components
- Managing streaming responses and fallback mechanisms
- Providing clear completion indicators to show when processing is done

## Clean Architecture Principles

### Single Source of Truth
Each function is defined in exactly ONE module:
- ✅ `agent_components/agent_config.py` - Agent creation and management
- ✅ `agent_components/tool_executor.py` - Parallel tool execution
- ✅ `agent_components/message_handler.py` - Message patching and handling
- ✅ `agent_components/json_tool_parser.py` - Tool call parsing and execution
- ✅ `main.py` - Request orchestration and coordination

### Direct Dependencies
All imports use direct paths to implementation modules:
```python
from tunacode.core.agents.agent_components import patch_tool_messages
from tunacode.core.agents.agent_components import extract_and_execute_tool_calls
```

## Key Components

### 1. Agent Creation and Management (`agent_components/agent_config.py`)

The `get_or_create_agent()` function creates agents on-demand for different models:

- Loads system prompts from `prompts/system.md`
- Integrates project context from `AGENTS.md` if present
- Configures the agent with all available tools (bash, grep, read_file, etc.)
- Supports MCP (Model Context Protocol) servers for external tools
- Caches agents by model name to avoid recreation

### 2. Tool System Integration

The agent integrates with TunaCode's tool system:

**Built-in Tools:**
- `bash` - Execute bash commands
- `glob` - File pattern matching
- `grep` - Fast file content searching
- `list_dir` - Directory listing
- `read_file` - Read file contents
- `run_command` - Execute shell commands
- `todo` - Task management
- `update_file` - Update existing files
- `write_file` - Create new files

Tools are wrapped with retry logic and max retries from user config.

### 3. Parallel Tool Execution (`agent_components/tool_executor.py`)

A key performance optimization is parallel execution of read-only tools:

- **Read-only tools**: `read_file`, `grep`, `list_dir`, `glob`
- These tools execute concurrently when multiple are called
- Write/execute tools run sequentially for safety
- Controlled by `TUNACODE_MAX_PARALLEL` environment variable
- Implemented in `execute_tools_parallel()` function

**Current Implementation:**
- Detects when ALL tools in a response are read-only
- Executes them in parallel with progress tracking
- Shows ~3-5x speedup over sequential execution

**Completion Indicators:**
- **"Parallel batch completed"** - Shows after each parallel batch with timing stats
- **"✅ Final batch completed"** - Displays when all remaining buffered tools finish
- These visual cues clearly indicate when the agent has finished processing

**Planned Enhancement:**
- Mixed batching: Group consecutive read-only tools even when mixed with write tools
- Example: `[read, read, write, read]` → `[read||read], [write], [read]`

---

### How TunaCode Determines Completion

TunaCode determines that it is “done” processing a request using several explicit signals and controls, ensuring no partial or ambiguous results:

- **Parallel Batch Completion:** After running a batch of read-only tools (`read_file`, `grep`, `list_dir`, `glob`), it emits a clear "Parallel batch completed" indicator in the UI, along with processing time.
- **Final Batch Indicator:** When all pending (in-flight) tool operations—including sequential write/execute tools—are complete, TunaCode displays "✅ Final batch completed" to confirm the request is truly finished.
- **Processing Loop Control:** The `process_request()` loop only exits when:
    - All required actions and tool executions are finished.
    - Any buffered tools have run to completion and returned results.
    - No actionable responses or follow-up work remain.
    - The maximum iteration limit (configurable, default: 40) is reached.
- **Fallback Handling:** If the max iteration count is exceeded or a request stalls, TunaCode triggers fallback logic:
    - Provides a detailed summary of all actions taken.
    - Lists tools executed, files modified, steps completed.
    - Suggests next actions or debugging steps.
- **User-Facing Signals:** Completion is always marked by explicit messages in the output, never leaving requests in an unclear or partial state. When thoughts/debug mode is enabled, internal markers and timing are also shown.

This robust system guarantees users always know when TunaCode’s processing of any user request is completely finished.

---

### 4. Request Processing Flow

The `process_request()` function orchestrates the entire flow:

1. **Initialization**
   - Create/retrieve agent for model
   - Copy message history
   - Setup usage tracking and response state
   - Reset iteration counters

2. **Main Processing Loop**
   - Iterate through agent responses
   - Process each node (request, response, tool calls)
   - Track thoughts, tool calls, and files in context
   - Handle streaming for supported models
   - Execute tools (with parallel batching for read-only)

3. **Iteration Control**
   - Max iterations from config (default: 40)
   - Break when limit reached
   - Track progress with detailed logging when thoughts enabled

4. **Completion and Cleanup**
   - Execute any remaining buffered tools with "✅ Final batch completed" message
   - Clear visual indication when all processing is done
   - Timing statistics show performance gains from parallel execution

5. **Fallback Handling**
   - If no user response after max iterations
   - Generate comprehensive fallback with:
     - Summary of attempts
     - Tools executed
     - Files modified
     - Suggested next steps

### 5. Node Processing

The `_process_node()` function handles individual agent responses:

- **Request tracking**: Adds to message history
- **Thought processing**: Displays agent reasoning when enabled
- **Tool execution**: Coordinates tool calls with batching
- **Token usage**: Tracks and displays usage statistics
- **Streaming**: Handles token-level streaming when available

### 6. State Management

The agent maintains conversation state through `StateManager`:

- Message history
- Tool call tracking
- Files in context
- Current iteration count
- User permissions and config
- Agent instances by model

### 7. Enhanced Debugging

When thoughts are enabled (`/thoughts on`):

- Raw API response data
- Tool collection and batching info
- Parallel execution timing with completion indicators
- Token counts
- File context tracking
- Iteration progress
- Visual feedback for batch completion ("✅ Final batch completed")
- Performance metrics showing speedup from parallelization

## Architecture Patterns

### 1. Lazy Loading
- Agents created on-demand
- Tool imports deferred until needed
- Reduces startup time

### 2. Protocol-Based Design
- Uses protocols for type safety
- Allows flexible implementations
- Supports different agent backends

### 3. Async Throughout
- All operations are async
- Enables concurrent tool execution
- Non-blocking UI updates

### 4. Fallback Safety
- Graceful degradation on errors
- Synthetic tool responses for orphaned calls
- Comprehensive fallback messages

### 5. Streaming Support
- Token-level streaming for real-time output
- Fallback to content streaming
- Progress indicators during processing

## Configuration

### User Config Options
- `default_model`: Default AI model
- `max_retries`: Tool retry attempts (default: 3)
- `max_iterations`: Max agent iterations (default: 40)
- `fallback_response`: Enable fallback messages (default: true)
- `fallback_verbosity`: Detail level (minimal/normal/detailed)

### Environment Variables
- `TUNACODE_MAX_PARALLEL`: Max concurrent tools (default: CPU count)

## Future Enhancements

1. **Improved Parallel Batching**
   - Mixed read/write batching
   - Dynamic batch sizing
   - Priority-based execution

2. **Enhanced Streaming**
   - Richer progress indicators
   - Tool execution progress
   - Partial result streaming

3. **Advanced State Management**
   - Conversation branching
   - State checkpointing
   - Resume capabilities

4. **Performance Optimizations**
   - Tool result caching
   - Smarter context pruning
   - Predictive tool loading
