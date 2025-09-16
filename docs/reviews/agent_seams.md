# TunaCode Main Agent Module - Comprehensive Technical Analysis

## Overview

The `src/tunacode/core/agents/main.py` module serves as the central orchestrator for TunaCode's AI agent system. This document provides an exhaustive analysis of its architecture, implementation patterns, and operational flow.

## Module Structure and Dependencies

### Core Imports and Type Safety

```python
"""Module: tunacode.core.agents.main

Main agent functionality and coordination for the TunaCode CLI.
Handles agent creation, configuration, and request processing.

CLAUDE_ANCHOR[main-agent-module]: Primary agent orchestration and lifecycle management
"""

from typing import TYPE_CHECKING, Awaitable, Callable, Optional
from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai import Tool  # noqa: F401
```

**Analysis**: The module uses `TYPE_CHECKING` to avoid circular imports while maintaining type safety. The `Tool` import is deferred to runtime when needed via the `get_agent_tool()` function.

### Dependency Architecture

```python
from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.exceptions import ToolBatchingJSONError, UserAbortError
from tunacode.services.mcp import get_mcp_servers
from tunacode.types import (
    AgentRun,
    ModelName,
    ToolCallback,
    UsageTrackerProtocol,
)
from tunacode.ui.tool_descriptions import get_batch_description
```

**Key Dependencies**:
- **StateManager**: Centralized session state management
- **Exception Handling**: Specialized exceptions for tool batching and user interruption
- **MCP Integration**: Model Context Protocol server support
- **Type System**: Protocol-based design for flexibility
- **UI Integration**: Tool description formatting for user feedback

### Agent Components Import Strategy

```python
from .agent_components import (
    AgentRunWithState,
    AgentRunWrapper,
    ResponseState,
    SimpleResult,
    ToolBuffer,
    _process_node,
    check_task_completion,
    create_empty_response_message,
    create_fallback_response,
    create_progress_summary,
    create_user_message,
    execute_tools_parallel,
    extract_and_execute_tool_calls,
    format_fallback_output,
    get_model_messages,
    get_or_create_agent,
    get_recent_tools_context,
    get_tool_summary,
    parse_json_tool_calls,
    patch_tool_messages,
)
```

**Design Pattern**: The module follows a composition pattern, importing specialized components rather than implementing everything inline. This promotes modularity and testability.

## Streaming Support Architecture

### Conditional Streaming Imports

```python
try:
    from pydantic_ai.messages import PartDeltaEvent, TextPartDelta
    STREAMING_AVAILABLE = True
except ImportError:
    PartDeltaEvent = None
    TextPartDelta = None
    STREAMING_AVAILABLE = False
```

**Graceful Degradation**: The module handles different pydantic-ai versions by conditionally importing streaming types and setting a feature flag.

## Core Functions Analysis

### 1. Lazy Agent/Tool Import Resolution

```python
def get_agent_tool() -> tuple[type[Agent], type["Tool"]]:
    """Lazy import for Agent and Tool to avoid circular imports."""
    from pydantic_ai import Agent, Tool
    return Agent, Tool
```

**Purpose**: Prevents circular import issues while providing access to pydantic-ai types when needed during runtime.

### 2. Query Satisfaction Stub

```python
async def check_query_satisfaction(
    agent: Agent,
    original_query: str,
    response: str,
    state_manager: StateManager,
) -> bool:
    """Check if the response satisfies the original query."""
    return True  # Completion decided via DONE marker in RESPONSE
```

**Design Decision**: This function always returns `True`, shifting completion detection to explicit markers in model responses. This prevents recursive agent evaluation that previously caused empty outputs.

## Main Request Processing Function

### Function Signature and Parameters

```python
async def process_request(
    message: str,
    model: ModelName,
    state_manager: StateManager,
    tool_callback: Optional[ToolCallback] = None,
    streaming_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    usage_tracker: Optional[UsageTrackerProtocol] = None,
    fallback_enabled: bool = True,
) -> AgentRun:
```

**Parameter Analysis**:
- `message`: User's request text
- `model`: AI model identifier (supports multiple providers)
- `state_manager`: Session state and message history
- `tool_callback`: Optional callback for tool execution notifications
- `streaming_callback`: Real-time token streaming handler
- `usage_tracker`: Token/cost tracking protocol
- `fallback_enabled`: Controls synthetic response generation

### Request Initialization Sequence

```python
# Get or create agent for the model
agent = get_or_create_agent(model, state_manager)

# Create a unique request ID for debugging
import uuid
request_id = str(uuid.uuid4())[:8]

# Attach request_id to session for downstream logging/context
try:
    state_manager.session.request_id = request_id
except Exception:
    pass

# Reset state for new request
state_manager.session.current_iteration = 0
state_manager.session.iteration_count = 0
state_manager.session.tool_calls = []

# Initialize batch counter if not exists
if not hasattr(state_manager.session, "batch_counter"):
    state_manager.session.batch_counter = 0
```

**State Management Strategy**:
1. **Agent Retrieval**: Uses caching mechanism via `get_or_create_agent`
2. **Request Tracking**: UUID-based request identification for debugging
3. **State Reset**: Clears iteration counters and tool call history
4. **Batch Initialization**: Ensures batch counter exists for tool execution

### Core Processing Infrastructure Setup

```python
# Initialize tool buffer for parallel execution
tool_buffer = ToolBuffer()

# Initialize response state tracking
response_state = ResponseState()

# Get max iterations from config
max_iterations = state_manager.config.max_iterations

# Initialize productivity tracking
unproductive_iterations = 0
last_productive_iteration = 0

# Get message history for context
message_history = get_model_messages(state_manager)
```

**Component Initialization**:
- **ToolBuffer**: Manages parallel execution of read-only tools
- **ResponseState**: Tracks completion status and user guidance needs
- **Productivity Tracking**: Monitors tool usage to prevent infinite loops
- **Message History**: Provides conversation context to the agent

## Agent Iteration Loop Architecture

### Main Iteration Structure

```python
async with agent.iter(message, message_history=message_history) as agent_run:
    # Process nodes iteratively
    i = 1
    async for node in agent_run:
        state_manager.session.current_iteration = i
        state_manager.session.iteration_count = i
```

**Async Context Management**: Uses pydantic-ai's async context manager for proper resource cleanup and streaming support.

### Streaming Integration

```python
# Handle token-level streaming for model request nodes
Agent, _ = get_agent_tool()
if streaming_callback and STREAMING_AVAILABLE and Agent.is_model_request_node(node):
    await stream_model_request_node(
        node,
        agent_run.ctx,
        state_manager,
        streaming_callback,
        request_id,
        i,
    )
```

**Streaming Strategy**:
1. **Node Type Detection**: Identifies model request nodes for streaming
2. **Feature Availability**: Checks if streaming is supported
3. **Delegation**: Uses specialized streaming handler from agent_components

### Node Processing and State Management

```python
empty_response, empty_reason = await _process_node(
    node,
    tool_callback,
    state_manager,
    tool_buffer,
    streaming_callback,
    usage_tracker,
    response_state,
)
```

**Node Processing Returns**:
- `empty_response`: Boolean indicating if the response was empty
- `empty_reason`: Diagnostic string explaining why response was empty

## Empty Response Recovery System

### Detection and Counter Management

```python
if empty_response:
    state_manager.session.consecutive_empty_responses += 1

    if state_manager.session.consecutive_empty_responses >= 1:
        force_action_content = create_empty_response_message(
            message,
            empty_reason,
            state_manager.session.tool_calls,
            i,
            state_manager,
        )
        create_user_message(force_action_content, state_manager)
```

**Recovery Strategy**:
1. **Immediate Intervention**: Triggers after just 1 empty response
2. **Context-Aware Prompting**: Includes original message, failure reason, and tool history
3. **Message Injection**: Adds corrective prompt to conversation history

### User Feedback for Empty Responses

```python
if state_manager.session.show_thoughts:
    from tunacode.ui import console as ui

    await ui.warning(
        "\nEMPTY RESPONSE FAILURE - AGGRESSIVE RETRY TRIGGERED"
    )
    await ui.muted(f"   Reason: {empty_reason}")
    await ui.muted(
        f"   Recent tools: {get_recent_tools_context(state_manager.session.tool_calls)}"
    )
    await ui.muted("   Injecting retry guidance prompt")
```

**Diagnostic Output**: Provides detailed feedback when debug mode is enabled, including failure reasons and recent tool context.

## Response Detection and User Output Tracking

```python
# Check if this node produced a user-visible response
if hasattr(node, 'result') and hasattr(node.result, 'output') and node.result.output:
    response_state.has_user_response = True
```

**Purpose**: Tracks whether the agent has produced user-visible output, which influences fallback response generation later.

## Productivity Enforcement System

### Tool Usage Monitoring

```python
# Check if this iteration used any tools
iteration_had_tools = False
if hasattr(node, 'result') and hasattr(node.result, 'response_parts'):
    for part in node.result.response_parts:
        if hasattr(part, 'tool_name'):
            iteration_had_tools = True
            break

if iteration_had_tools:
    # Reset unproductive counter
    unproductive_iterations = 0
    last_productive_iteration = i
else:
    # Increment unproductive counter
    unproductive_iterations += 1
```

**Productivity Tracking Logic**:
1. **Tool Detection**: Scans response parts for tool usage
2. **Counter Management**: Resets on tool usage, increments on inactivity
3. **Productivity Marking**: Records last iteration with tool usage

### Forced Action Mechanism

```python
# After 3 unproductive iterations, force action
if unproductive_iterations >= 3 and not response_state.task_completed:
    no_progress_content = f"""ALERT: No tools executed for {unproductive_iterations} iterations.

Last productive iteration: {last_productive_iteration}
Current iteration: {i}/{max_iterations}
Task: {message[:200]}...

You're describing actions but not executing them. You MUST:

1. If task is COMPLETE: Start response with TUNACODE DONE:
2. If task needs work: Execute a tool RIGHT NOW (grep, read_file, bash, etc.)
3. If stuck: Explain the specific blocker

NO MORE DESCRIPTIONS. Take ACTION or mark COMPLETE."""

    create_user_message(no_progress_content, state_manager)
```

**Escalation Strategy**:
1. **Threshold**: Triggers after 3 consecutive iterations without tools
2. **Clear Instructions**: Provides explicit guidance on required actions
3. **Context Preservation**: Includes task summary and iteration progress
4. **Action Forcing**: Demands immediate tool execution or completion

## Context Tracking and Observability

### Original Query Preservation

```python
# Store original query for reference
if not hasattr(state_manager.session, "original_query"):
    state_manager.session.original_query = message
```

**Purpose**: Preserves the initial user request for use in clarification prompts and progress summaries.

### Progress Telemetry

```python
# Display iteration progress if thoughts are enabled
if state_manager.session.show_thoughts:
    from tunacode.ui import console as ui

    await ui.muted(f"\nITERATION: {i}/{max_iterations} (Request ID: {request_id})")

    # Show summary of tools used so far
    if state_manager.session.tool_calls:
        tool_summary = get_tool_summary(state_manager.session.tool_calls)
        summary_str = ", ".join(
            [f"{name}: {count}" for name, count in tool_summary.items()]
        )
        await ui.muted(f"TOOLS USED: {summary_str}")
```

**Observability Features**:
1. **Iteration Tracking**: Shows current progress against limits
2. **Request Correlation**: Includes request ID for debugging
3. **Tool Usage Summary**: Aggregates tool usage by type and count

## User Guidance and Clarification System

### Clarification Request Generation

```python
# User clarification: Ask user for guidance when explicitly awaiting
if response_state.awaiting_user_guidance:
    _, tools_used_str = create_progress_summary(state_manager.session.tool_calls)

    clarification_content = f"""I need clarification to continue.

Original request: {getattr(state_manager.session, "original_query", "your request")}

Progress so far:
- Iterations: {i}
- Tools used: {tools_used_str}

If the task is complete, I should respond with TUNACODE DONE:
Otherwise, please provide specific guidance on what to do next."""

    create_user_message(clarification_content, state_manager)
```

**Clarification Strategy**:
1. **Context Provision**: Includes original request and progress summary
2. **Clear Options**: Explains completion marker or guidance request
3. **State Management**: Sets awaiting_user_guidance flag

## Iteration Limit Handling

### Limit Reached Response

```python
if i >= max_iterations and not response_state.task_completed:
    _, tools_str = create_progress_summary(state_manager.session.tool_calls)
    tools_str = tools_str if tools_str != "No tools used yet" else "No tools used"

    extend_content = f"""I've reached the iteration limit ({max_iterations}).

Progress summary:
- Tools used: {tools_str}
- Iterations completed: {i}

The task appears incomplete. Would you like me to:
1. Continue working (I can extend the limit)
2. Summarize what I've done and stop
3. Try a different approach

Please let me know how to proceed."""

    create_user_message(extend_content, state_manager)

    max_iterations += 5
    response_state.awaiting_user_guidance = True
```

**Limit Handling Strategy**:
1. **Progress Summary**: Shows what was accomplished
2. **User Options**: Provides clear choices for continuation
3. **Automatic Extension**: Adds 5 more iterations
4. **Guidance Flag**: Sets state to await user direction

## Task Completion Detection

```python
# Check if task is explicitly completed
if response_state.task_completed:
    if state_manager.session.show_thoughts:
        from tunacode.ui import console as ui
        await ui.success("Task completed successfully")
    break
```

**Completion Logic**: Relies on explicit completion markers detected by the response state rather than recursive agent evaluation.

## Buffered Tool Execution System

### Final Tool Flush

```python
# Final flush: execute any remaining buffered read-only tools
if tool_callback and tool_buffer.has_tasks():
    import time
    from tunacode.ui import console as ui

    buffered_tasks = tool_buffer.flush()
    start_time = time.time()

    # Update spinner message for final batch execution
    tool_names = [part.tool_name for part, _ in buffered_tasks]
    batch_msg = get_batch_description(len(buffered_tasks), tool_names)
    await ui.update_spinner_message(
        f"[bold #00d7ff]{batch_msg}...[/bold #00d7ff]", state_manager
    )
```

**Batch Execution Features**:
1. **Performance Timing**: Measures execution duration
2. **UI Feedback**: Updates spinner with batch description
3. **Tool Enumeration**: Lists tools being executed

### Detailed Batch Reporting

```python
await ui.muted("\n" + "=" * 60)
await ui.muted(
    f"FINAL BATCH: Executing {len(buffered_tasks)} buffered read-only tools"
)
await ui.muted("=" * 60)

for idx, (part, node) in enumerate(buffered_tasks, 1):
    tool_desc = f"  [{idx}] {part.tool_name}"
    if hasattr(part, "args") and isinstance(part.args, dict):
        if part.tool_name == "read_file" and "file_path" in part.args:
            tool_desc += f" → {part.args['file_path']}"
        elif part.tool_name == "grep" and "pattern" in part.args:
            tool_desc += f" → pattern: '{part.args['pattern']}'"
            if "include_files" in part.args:
                tool_desc += f", files: '{part.args['include_files']}'"
        elif part.tool_name == "list_dir" and "directory" in part.args:
            tool_desc += f" → {part.args['directory']}"
        elif part.tool_name == "glob" and "pattern" in part.args:
            tool_desc += f" → pattern: '{part.args['pattern']}'"
    await ui.muted(tool_desc)
```

**Detailed Reporting**: Provides comprehensive information about each tool being executed, including arguments and targets.

## Fallback Response System

### Fallback Conditions and Generation

```python
# Generate fallback response if needed
if (
    not response_state.has_user_response
    and state_manager.session.iteration_count >= max_iterations
    and fallback_enabled
):
    # Patch any outstanding tool messages
    patch_tool_messages("Request completed", state_manager=state_manager)

    # Create fallback response
    fallback_response = create_fallback_response(
        state_manager.session.tool_calls,
        getattr(state_manager.session, "original_query", message),
        state_manager,
    )

    # Format and wrap the response
    formatted_fallback = format_fallback_output(fallback_response)
    return AgentRunWrapper(agent_run, formatted_fallback)
```

**Fallback Logic**:
1. **Condition Check**: No user response + iteration limit reached + fallback enabled
2. **Message Patching**: Cleans up orphaned tool messages
3. **Response Generation**: Creates synthetic summary of actions taken
4. **Wrapper Return**: Packages fallback response with original agent run

## Error Handling and Exception Management

### User Abort Handling

```python
except UserAbortError:
    raise
```

**Pass-through**: User interruptions are re-raised without modification to allow higher-level handling.

### Tool Batching Error Handling

```python
except ToolBatchingJSONError as e:
    logger.error(f"Tool batching JSON error: {e}", exc_info=True)
    # Patch orphaned tool messages with error
    patch_tool_messages(f"Tool batching failed: {str(e)[:100]}...", state_manager=state_manager)
    # Re-raise to be handled by caller
    raise
```

**Specialized Handling**: Tool batching errors receive specific logging and message patching before re-raising.

### Generic Exception Handling

```python
except Exception as e:
    # Include request context to aid debugging
    safe_iter = (
        state_manager.session.current_iteration
        if hasattr(state_manager.session, "current_iteration")
        else "?"
    )
    logger.error(
        f"Error in process_request [req={request_id} iter={safe_iter}]: {e}",
        exc_info=True,
    )
    # Patch orphaned tool messages with generic error
    patch_tool_messages(
        f"Request processing failed: {str(e)[:100]}...", state_manager=state_manager
    )
    raise
```

**Comprehensive Error Context**: Includes request ID and iteration number for debugging, with safe attribute access.

## Module Exports and Public API

```python
__all__ = [
    "ToolBuffer",
    "check_task_completion",
    "extract_and_execute_tool_calls",
    "get_model_messages",
    "parse_json_tool_calls",
    "patch_tool_messages",
    "get_mcp_servers",
    "check_query_satisfaction",
    "process_request",
    "get_or_create_agent",
    "_process_node",
    "ResponseState",
    "SimpleResult",
    "AgentRunWrapper",
    "AgentRunWithState",
    "execute_tools_parallel",
    "get_agent_tool",
]
```

**Public Interface**: Exposes both high-level functions (`process_request`) and low-level components for testing and extension.

## Architecture Patterns and Design Principles

### 1. Composition Over Inheritance
The module imports specialized components rather than implementing everything inline, promoting modularity and testability.

### 2. Protocol-Based Design
Uses protocols like `UsageTrackerProtocol` and `ToolCallback` for flexible implementations.

### 3. Graceful Degradation
Handles missing features (streaming) and different pydantic-ai versions gracefully.

### 4. Comprehensive Error Recovery
Multiple layers of error handling with context preservation and user feedback.

### 5. Performance Optimization
Parallel tool execution for read-only operations with detailed performance reporting.

### 6. Observability
Extensive logging, progress tracking, and debug output for troubleshooting.

### 7. State Management
Centralized session state with careful initialization and cleanup.

This module represents a sophisticated orchestration layer that balances performance, reliability, and user experience while maintaining clean separation of concerns and extensibility.
