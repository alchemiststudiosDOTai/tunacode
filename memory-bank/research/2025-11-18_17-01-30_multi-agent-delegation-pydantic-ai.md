# Research – Multi-Agent Delegation with Pydantic-AI in TunaCode

**Date:** 2025-11-18
**Owner:** Claude (Research Agent)
**Phase:** Research
**Git Commit:** df06234a7b7c922d5bbfa918bf89c555f6d014e4

## Goal

Research how to implement multi-agent delegation patterns in the tunacode codebase using pydantic-ai's agent delegation features. Specifically, investigate how to create a specialized "research" agent with read-only tools that can be delegated to from the main agent, following the pattern shown in pydantic-ai documentation where a parent agent delegates work to child agents via tool calls with shared usage tracking.

## Research Questions

1. How are agents currently created and configured in tunacode?
2. Which tools are read-only and suitable for a research agent?
3. How is usage tracking implemented and how can it be shared between parent/child agents?
4. Are there any existing multi-agent or delegation patterns in the codebase?
5. What infrastructure exists for creating specialized agents?

## Quick Search Commands

If you need to explore further:

- Agent creation: `grep -r "get_or_create_agent" src/`
- Tool definitions: `ls src/tunacode/tools/*.py`
- Usage tracking: `grep -r "UsageTrackerProtocol" src/`
- Delegation patterns: `grep -r "recursive_context" src/`

## Findings

### 1. Current Agent Architecture

#### Agent Creation Pattern

**Location:** [src/tunacode/core/agents/agent_components/agent_config.py:191-304](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/agents/agent_components/agent_config.py#L191-L304)

The tunacode system uses a **factory pattern with multi-level caching** for agent creation:

1. **Cache Check Hierarchy:**
   - Session-level cache: `state_manager.session.agents[model]` (backward compatibility)
   - Module-level cache: `_AGENT_CACHE[model]` (cross-request persistence)
   - Cache invalidation via configuration hash: `(max_retries, tool_strict_validation, mcpServers)`

2. **Agent Creation Flow:**
   ```python
   def get_or_create_agent(model: ModelName, state_manager: StateManager) -> PydanticAgent:
       # 1. Check session cache
       if model in state_manager.session.agents:
           return state_manager.session.agents[model]

       # 2. Check module cache with version validation
       if model in _AGENT_CACHE:
           if _AGENT_CACHE_VERSION.get(model) == current_config_hash:
               return _AGENT_CACHE[model]

       # 3. Create new agent
       system_prompt = load_system_prompt(base_path)
       system_prompt += load_tunacode_context()  # Optional AGENTS.md

       tools_list = [
           Tool(bash, max_retries=max_retries, strict=tool_strict_validation),
           Tool(glob, max_retries=max_retries, strict=tool_strict_validation),
           Tool(grep, max_retries=max_retries, strict=tool_strict_validation),
           Tool(list_dir, max_retries=max_retries, strict=tool_strict_validation),
           Tool(read_file, max_retries=max_retries, strict=tool_strict_validation),
           Tool(run_command, max_retries=max_retries, strict=tool_strict_validation),
           Tool(update_file, max_retries=max_retries, strict=tool_strict_validation),
           Tool(write_file, max_retries=max_retries, strict=tool_strict_validation),
       ]

       agent = Agent(
           model=model_instance,
           system_prompt=system_prompt,
           tools=tools_list,
           mcp_servers=mcp_servers,
       )

       # Store in both caches
       _AGENT_CACHE[model] = agent
       state_manager.session.agents[model] = agent
       return agent
   ```

**Key Observations:**
- Agent creation is **model-centric** (same model = same cached agent)
- All agents currently get the same 8 tools
- No role-based or task-based agent specialization exists
- Configuration-based customization rather than inheritance

#### Request Orchestration

**Location:** [src/tunacode/core/agents/main.py:298-492](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/agents/main.py#L298-L492)

The `RequestOrchestrator` class manages the main agent loop with:
- Iteration management and productivity tracking
- Empty response handling
- ReAct snapshot injection
- Tool buffering for parallel execution

**Main Loop Structure:**
```python
async with agent.iter(self.message, message_history=message_history) as agent_run:
    i = 1
    async for node in agent_run:
        # Update counters
        self.iteration_manager.update_counters(i)

        # Stream tokens if callback provided
        await _maybe_stream_node_tokens(...)

        # Process node (tool calls, responses)
        empty_response, empty_reason = await ac._process_node(...)

        # Track productivity
        had_tool_use = _iteration_had_tool_use(node)
        self.iteration_manager.track_productivity(had_tool_use, i)

        # Inject guidance if needed
        await self.react_manager.capture_snapshot(i, agent_run.ctx, show_thoughts)

        # Check completion
        if response_state.task_completed:
            break
```

**Relevant for Delegation:**
- `agent.iter()` accepts `message_history` parameter for context isolation
- Message history snapshot taken at line 378: `list(getattr(state_manager.session, "messages", []))`
- Node processing is centralized in `ac._process_node()`

### 2. Tool Categorization for Research Agent

#### Read-Only Tools (Safe for Research Agent)

**Defined in:** [src/tunacode/constants.py:61-69](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/constants.py#L61-L69)

```python
READ_ONLY_TOOLS = [READ_FILE, GREP, LIST_DIR, GLOB, REACT]
```

| Tool Name | File Path | Purpose | Side Effects |
|-----------|-----------|---------|--------------|
| `read_file` | `src/tunacode/tools/read_file.py` | Read file contents with size limits | None ✅ |
| `grep` | `src/tunacode/tools/grep.py` | Parallel content search with regex | None ✅ |
| `list_dir` | `src/tunacode/tools/list_dir.py` | List directory contents | None ✅ |
| `glob` | `src/tunacode/tools/glob.py` | Fast file pattern matching | None ✅ |
| `react` | `src/tunacode/tools/react.py` | ReAct scratchpad for reasoning | Memory only ✅ |

**Function Signatures:**
```python
async def read_file(filepath: str) -> str
async def grep(pattern: str, directory: str = ".", path: Optional[str] = None,
               case_sensitive: bool = False, use_regex: bool = False, ...) -> str
async def list_dir(directory: str = ".", max_entries: int = 200,
                   show_hidden: bool = False) -> str
async def glob(pattern: str, directory: str = ".", recursive: bool = True,
               include_hidden: bool = False, ...) -> str
```

**Tool Import Pattern:**
```python
from tunacode.tools.read_file import read_file
from tunacode.tools.grep import grep
from tunacode.tools.list_dir import list_dir
from tunacode.tools.glob import glob
from tunacode.tools.react import ReactTool  # Requires state_manager
```

#### Write Tools (Exclude from Research Agent)

```python
WRITE_TOOLS = [WRITE_FILE, UPDATE_FILE]
EXECUTE_TOOLS = [BASH, RUN_COMMAND]
```

| Tool Name | File Path | Side Effects | Include in Research Agent? |
|-----------|-----------|--------------|----------------------------|
| `write_file` | `src/tunacode/tools/write_file.py` | Creates files | ❌ NO |
| `update_file` | `src/tunacode/tools/update_file.py` | Modifies files | ❌ NO |
| `bash` | `src/tunacode/tools/bash.py` | Executes commands | ❌ NO |
| `run_command` | `src/tunacode/tools/run_command.py` | Executes commands | ❌ NO |

### 3. Usage Tracking Implementation

#### UsageTrackerProtocol Interface

**Location:** [src/tunacode/types.py:317-320](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/types.py#L317-L320)

```python
class UsageTrackerProtocol(Protocol):
    """Protocol for a class that tracks and displays token usage and cost."""
    async def track_and_display(self, response_obj: Any) -> None: ...
```

#### UsageTracker Implementation

**Location:** [src/tunacode/core/token_usage/usage_tracker.py:10-147](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/token_usage/usage_tracker.py#L10-L147)

**Core Flow:**
1. Parse response to extract token data (line 32)
2. Calculate cost using model pricing (line 38)
3. Update session state with cumulative totals (line 41)
4. Display summary if `show_thoughts` enabled (lines 44-45)

**State Storage:** [src/tunacode/core/state.py:70-83](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/state.py#L70-L83)

```python
@dataclass
class SessionState:
    # Per-call tracking
    last_call_usage: dict = field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost": 0.0,
        }
    )
    # Session-wide accumulation
    session_total_usage: dict = field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost": 0.0,
        }
    )
```

**Integration Point:** [src/tunacode/core/agents/agent_components/node_processor.py:64-65](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/agents/agent_components/node_processor.py#L64-L65)

```python
if usage_tracker:
    await usage_tracker.track_and_display(node.model_response)
```

Called for every `model_response` node during the agent iteration loop.

#### Pydantic-AI Usage Limits Support

According to pydantic-ai docs, agents support `UsageLimits`:
```python
from pydantic_ai import UsageLimits

result = agent.run_sync(
    'Tell me a joke.',
    usage_limits=UsageLimits(request_limit=5, total_tokens_limit=500),
)
print(result.usage())
#> RunUsage(input_tokens=204, output_tokens=24, requests=3, tool_calls=1)
```

**Current Status in TunaCode:**
- ✅ `UsageTrackerProtocol` exists and is implemented
- ✅ Usage tracking accumulates in `session_total_usage`
- ❌ `UsageLimits` are **not currently used**
- ❌ No usage context propagation between agents

### 4. Existing Multi-Agent Patterns

**FINDING: No active multi-agent delegation patterns found.**

However, infrastructure exists for recursive execution:

#### Recursive Context Stack

**Location:** [src/tunacode/core/state.py:118-150](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/state.py#L118-L150)

**Available Methods:**
```python
def push_recursive_context(self, context: dict) -> None:
    """Push new execution context onto stack."""

def pop_recursive_context(self) -> Optional[dict]:
    """Pop and return most recent context."""

def can_recurse_deeper(self) -> bool:
    """Check if we can recurse deeper without hitting depth limit."""

def reset_recursive_state(self) -> None:
    """Clear all recursive state."""
```

**Recursive State Fields:** [src/tunacode/core/state.py:84-90](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/state.py#L84-L90)

```python
@dataclass
class SessionState:
    # Recursive execution tracking (infrastructure exists but unused)
    current_recursion_depth: int = 0
    max_recursion_depth: int = 5
    parent_task_id: Optional[str] = None
    task_hierarchy: dict[str, Any] = field(default_factory=dict)
    iteration_budgets: dict[str, int] = field(default_factory=dict)
    recursive_context_stack: list[dict[str, Any]] = field(default_factory=list)
```

**Current Status:** These methods and fields exist but are **never called** in the codebase (verified via grep).

### 5. HTTP Retry Configuration

**Location:** [src/tunacode/core/agents/agent_components/agent_config.py:258-274](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/agents/agent_components/agent_config.py#L258-L274)

```python
# Configure HTTP client with retry logic at transport layer
transport = AsyncTenacityTransport(
    config=RetryConfig(
        retry=retry_if_exception_type(HTTPStatusError),
        wait=wait_retry_after(max_wait=60),
        stop=stop_after_attempt(max_retries),
        reraise=True,
    ),
    validate_response=lambda r: r.raise_for_status(),
)
http_client = AsyncClient(transport=transport)
```

**Key Point:** Retry logic applied at **transport layer BEFORE pydantic-ai node creation** to prevent violation of pydantic-ai's single-stream-per-node constraint.

## Key Patterns / Solutions Found

### Pattern 1: Agent Delegation via Tool Decorator (Pydantic-AI Pattern)

From pydantic-ai documentation, the recommended pattern is:

```python
from pydantic_ai import Agent, RunContext, UsageLimits

# Parent agent (main orchestrator)
research_orchestrator = Agent(
    'openai:gpt-4',
    system_prompt=(
        'Use the `research_tool` to search the codebase, then synthesize findings. '
        'You must return a comprehensive analysis.'
    ),
)

# Child agent (specialized research)
research_agent = Agent(
    'google-gla:gemini-2.5-flash',
    output_type=dict[str, Any]
)

# Delegation happens via tool
@research_orchestrator.tool
async def research_tool(ctx: RunContext[None], query: str) -> dict:
    r = await research_agent.run(
        f'Research the codebase for: {query}',
        usage=ctx.usage,  # Share usage tracking
    )
    return r.output

# Run with usage limits
result = research_orchestrator.run_sync(
    'Analyze the agent architecture',
    usage_limits=UsageLimits(request_limit=10, total_tokens_limit=5000),
)
print(result.usage())  # Shows combined parent + child usage
```

**Key Benefits:**
- ✅ Parent and child usage automatically aggregated via `ctx.usage`
- ✅ Usage limits enforced across both agents
- ✅ Clean separation of concerns (parent orchestrates, child specializes)
- ✅ No manual state management needed

### Pattern 2: Specialized Agent Factory (TunaCode-Specific)

**Implementation Strategy:**

```python
def get_or_create_specialized_agent(
    model: ModelName,
    role: str,  # e.g., "research", "synthesis", "main"
    state_manager: StateManager
) -> PydanticAgent:
    """Create role-specific agent with appropriate tools and prompts."""

    # Use composite cache key for role-specific caching
    cache_key = f"{model}:{role}"

    # Check cache first
    if cache_key in _AGENT_CACHE:
        if _AGENT_CACHE_VERSION.get(cache_key) == current_config_hash:
            return _AGENT_CACHE[cache_key]

    # Load role-specific system prompt
    prompts_dir = base_path / "prompts" / role
    system_prompt = load_system_prompt_for_role(prompts_dir)

    # Select tools based on role
    if role == "research":
        # Read-only tools for codebase exploration
        tools_list = [
            Tool(read_file, max_retries=max_retries, strict=False),
            Tool(grep, max_retries=max_retries, strict=False),
            Tool(list_dir, max_retries=max_retries, strict=False),
            Tool(glob, max_retries=max_retries, strict=False),
        ]
    elif role == "synthesis":
        # Write tools for code generation
        tools_list = [
            Tool(write_file, max_retries=max_retries, strict=False),
            Tool(update_file, max_retries=max_retries, strict=False),
        ]
    else:  # "main" role
        # Full tool suite
        tools_list = get_all_tools()

    # Create agent with role-specific configuration
    agent = Agent(
        model=model_instance,
        system_prompt=system_prompt,
        tools=tools_list,
        mcp_servers=filter_mcp_servers_by_role(mcp_servers, role),
    )

    # Cache with role-specific key
    _AGENT_CACHE[cache_key] = agent
    _AGENT_CACHE_VERSION[cache_key] = current_config_hash

    return agent
```

**Directory Structure:**
```
src/tunacode/prompts/
  ├── main/
  │   └── system.xml          # Main orchestrator prompt
  ├── research/
  │   └── system.xml          # Research agent prompt
  └── synthesis/
      └── system.xml          # Code synthesis prompt
```

### Pattern 3: Usage Context Propagation (Manual Approach)

If not using pydantic-ai's `ctx.usage` pattern, manual usage tracking:

```python
async def delegate_to_child_agent(
    parent_state_manager: StateManager,
    child_message: str,
    model: str,
    usage_tracker: UsageTrackerProtocol
) -> tuple[Any, dict]:
    """Delegate task to child agent with isolated state and usage tracking."""

    # 1. Snapshot parent state
    parent_context = {
        "request_id": parent_state_manager.session.request_id,
        "last_call_usage": parent_state_manager.session.last_call_usage.copy(),
        "session_total_usage": parent_state_manager.session.session_total_usage.copy(),
        "iteration_count": parent_state_manager.session.iteration_count
    }
    parent_state_manager.push_recursive_context(parent_context)

    # 2. Reset state for child
    parent_state_manager.session.last_call_usage = {
        "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0
    }
    parent_state_manager.session.session_total_usage = {
        "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0
    }
    parent_state_manager.session.request_id = str(uuid.uuid4())

    # 3. Run child agent
    try:
        child_result = await process_request(
            child_message,
            model,
            parent_state_manager,
            usage_tracker=usage_tracker
        )

        # 4. Capture child usage
        child_usage = parent_state_manager.session.session_total_usage.copy()

    finally:
        # 5. Restore parent state and merge usage
        restored = parent_state_manager.pop_recursive_context()
        if restored:
            # Merge child usage into parent
            parent_state_manager.session.session_total_usage = {
                "prompt_tokens": (
                    restored["session_total_usage"]["prompt_tokens"] +
                    child_usage["prompt_tokens"]
                ),
                "completion_tokens": (
                    restored["session_total_usage"]["completion_tokens"] +
                    child_usage["completion_tokens"]
                ),
                "cost": (
                    restored["session_total_usage"]["cost"] +
                    child_usage["cost"]
                )
            }
            parent_state_manager.session.request_id = restored["request_id"]

    return child_result, child_usage
```

**Trade-offs:**
- ❌ More complex than pydantic-ai's built-in approach
- ❌ Requires manual state management
- ✅ Full control over state isolation
- ✅ Works with existing TunaCode infrastructure

## Knowledge Gaps

### 1. Pydantic-AI Agent Delegation Implementation Details

**Questions:**
- How does `ctx.usage` propagation actually work in pydantic-ai?
- Can we pass different tools to delegated agents in the same tool decorator?
- Does pydantic-ai handle message history isolation automatically?

**Next Steps:**
- Review pydantic-ai source code for `RunContext.usage` implementation
- Test delegation pattern with simple prototype
- Verify usage aggregation behavior

### 2. Message History Isolation

**Current Behavior:**
- `agent.iter()` accepts `message_history` parameter
- Child messages still append to `state_manager.session.messages` via node processor

**Questions:**
- Should child agent messages be isolated from parent session?
- How to prevent message pollution in parent's conversation history?
- Should we create a separate `StateManager` instance for child agents?

**Next Steps:**
- Examine `node_processor.py` message handling logic (lines 53-62)
- Determine if message isolation is necessary or desirable
- Consider using separate session state for child agents

### 3. MCP Server Assignment

**Current Behavior:**
- All agents get same MCP servers from `user_config.mcpServers`

**Questions:**
- Should research agents have access to all MCP servers?
- Can we filter MCP servers by agent role?
- What security implications exist for delegated agents accessing MCP servers?

**Next Steps:**
- Review MCP server configuration schema
- Determine if role-based MCP filtering is needed
- Document MCP server security model

### 4. Tool Strict Validation Impact

**Current Setting:**
- `tool_strict_validation` defaults to `False` for backward compatibility

**Questions:**
- Should research agents use strict validation for safety?
- What errors occur with strict mode enabled?
- Performance impact of strict validation?

**Next Steps:**
- Test research agent with `strict=True`
- Document validation errors and fixes
- Benchmark performance difference

## Implementation Recommendations

### Recommended Approach: Pydantic-AI Native Delegation

Based on research findings, the **recommended approach** is to use pydantic-ai's built-in delegation pattern:

**Advantages:**
1. ✅ **Automatic usage aggregation** - `ctx.usage` handles token tracking across parent/child
2. ✅ **Clean API** - Tool decorator pattern is intuitive and maintainable
3. ✅ **Usage limits** - `UsageLimits` enforced across entire delegation chain
4. ✅ **Minimal state management** - No manual context stack manipulation
5. ✅ **Testable** - Clear boundaries between agents and tools

**Implementation Steps:**

#### Step 1: Create Research Agent Factory

```python
# src/tunacode/core/agents/research_agent.py

from pydantic_ai import Agent, Tool
from tunacode.tools.read_file import read_file
from tunacode.tools.grep import grep
from tunacode.tools.list_dir import list_dir
from tunacode.tools.glob import glob

def create_research_agent(model: str, state_manager: StateManager) -> Agent:
    """Create specialized research agent with read-only tools."""

    # Load research-specific system prompt
    prompts_dir = Path(__file__).parent.parent.parent / "prompts" / "research"
    system_prompt = load_system_prompt_for_role(prompts_dir)

    # Read-only tools only
    tools_list = [
        Tool(read_file, max_retries=3, strict=False),
        Tool(grep, max_retries=3, strict=False),
        Tool(list_dir, max_retries=3, strict=False),
        Tool(glob, max_retries=3, strict=False),
    ]

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools_list,
        output_type=dict,  # Structured research output
    )
```

#### Step 2: Add Research Tool to Main Agent

```python
# src/tunacode/core/agents/delegation_tools.py

from pydantic_ai import RunContext
from tunacode.core.agents.research_agent import create_research_agent

# Lazily create research agent
_research_agent = None

def get_research_agent():
    global _research_agent
    if _research_agent is None:
        _research_agent = create_research_agent("gemini-2.5-flash", state_manager)
    return _research_agent

async def research_codebase(
    ctx: RunContext[None],
    query: str,
    directories: list[str] = ["."],
    max_files: int = 10
) -> dict:
    """Delegate codebase research to specialized read-only agent.

    Args:
        ctx: RunContext with usage tracking
        query: Research query describing what to find
        directories: List of directories to search
        max_files: Maximum number of files to analyze

    Returns:
        Structured research findings with file paths and summaries
    """
    research_agent = get_research_agent()

    prompt = f"""Research the codebase for: {query}

Search in directories: {', '.join(directories)}
Analyze up to {max_files} most relevant files.

Return a structured summary with:
- relevant_files: list of file paths found
- key_findings: list of important discoveries
- code_examples: relevant code snippets
- recommendations: next steps or areas needing attention
"""

    result = await research_agent.run(
        prompt,
        usage=ctx.usage,  # Share usage tracking with parent
    )

    return result.output
```

#### Step 3: Register Tool with Main Agent

```python
# src/tunacode/core/agents/agent_components/agent_config.py

from tunacode.core.agents.delegation_tools import research_codebase

def get_or_create_agent(model: ModelName, state_manager: StateManager) -> PydanticAgent:
    # ... existing code ...

    # Add delegation tool to main agent
    research_tool = Tool(research_codebase, max_retries=3, strict=False)
    tools_list.append(research_tool)

    # ... rest of agent creation ...
```

#### Step 4: Create Research System Prompt

```xml
<!-- src/tunacode/prompts/research/system.xml -->

<system_prompt>
You are a specialized research agent focused on codebase exploration.

Your capabilities:
- Read files to understand implementation
- Search code with grep for specific patterns
- List directories to discover structure
- Use glob to find files matching patterns

Your constraints:
- Read-only operations ONLY (no writing or executing)
- Focus on gathering information, not making changes
- Return structured findings for downstream analysis

Output format:
Always return a JSON object with:
{
  "relevant_files": ["path/to/file1.py", "path/to/file2.py"],
  "key_findings": ["Finding 1", "Finding 2"],
  "code_examples": [
    {
      "file": "path/to/file.py",
      "line": 123,
      "snippet": "code snippet here",
      "explanation": "why this is relevant"
    }
  ],
  "recommendations": ["Next step 1", "Next step 2"]
}
</system_prompt>
```

#### Step 5: Usage Example

```python
# User interaction with main agent
user_query = "Find all agent creation patterns in the codebase"

# Main agent automatically delegates to research agent via tool
result = await main_agent.run(
    user_query,
    usage_limits=UsageLimits(
        request_limit=10,  # Max 10 LLM calls across parent + child
        total_tokens_limit=50000  # Max 50k tokens across both
    )
)

# Usage automatically aggregated
print(result.usage())
# RunUsage(
#   input_tokens=15234,      # Parent + child combined
#   output_tokens=3421,      # Parent + child combined
#   requests=6,              # Parent: 3, Child (research): 3
#   tool_calls=8             # Parent: 1 (research_codebase), Child: 7 (read/grep/etc)
# )
```

### Alternative Approach: Manual State Management

If you need more control than pydantic-ai provides, use the recursive context stack pattern documented in [Pattern 3: Usage Context Propagation](#pattern-3-usage-context-propagation-manual-approach).

**When to use manual approach:**
- Need complete message history isolation
- Require fine-grained control over state sharing
- Want to prevent any parent state pollution
- Need custom usage aggregation logic

## References

### Primary Code Locations

**Agent Architecture:**
- [src/tunacode/core/agents/agent_components/agent_config.py:191-304](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/agents/agent_components/agent_config.py#L191-L304) - Agent factory
- [src/tunacode/core/agents/main.py:298-492](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/agents/main.py#L298-L492) - Request orchestrator
- [src/tunacode/core/agents/main.py:590-612](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/agents/main.py#L590-L612) - Main entry point

**Tool Definitions:**
- [src/tunacode/tools/read_file.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/tools/read_file.py) - Read file tool
- [src/tunacode/tools/grep.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/tools/grep.py) - Grep search tool
- [src/tunacode/tools/list_dir.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/tools/list_dir.py) - List directory tool
- [src/tunacode/tools/glob.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/tools/glob.py) - Glob pattern tool
- [src/tunacode/constants.py:61-69](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/constants.py#L61-L69) - Tool categorization

**Usage Tracking:**
- [src/tunacode/types.py:317-320](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/types.py#L317-L320) - UsageTrackerProtocol
- [src/tunacode/core/token_usage/usage_tracker.py:10-147](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/token_usage/usage_tracker.py#L10-L147) - UsageTracker implementation
- [src/tunacode/core/agents/agent_components/node_processor.py:64-65](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/agents/agent_components/node_processor.py#L64-L65) - Usage tracking integration

**State Management:**
- [src/tunacode/core/state.py:30-90](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/state.py#L30-L90) - SessionState dataclass
- [src/tunacode/core/state.py:100-166](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/state.py#L100-L166) - StateManager
- [src/tunacode/core/state.py:118-150](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234a7b7c922d5bbfa918bf89c555f6d014e4/src/tunacode/core/state.py#L118-L150) - Recursive context methods

### External Documentation

- [Pydantic-AI Multi-Agent Documentation](https://ai.pydantic.dev/multi-agent-applications/#agent-delegation)
- [Pydantic-AI Usage Tracking](https://ai.pydantic.dev/api/usage/)
- [Pydantic-AI RunContext](https://ai.pydantic.dev/api/run/#pydantic_ai.RunContext)

### Related Tunacode Files

- `src/tunacode/tools/base.py` - BaseTool and FileBasedTool classes
- `src/tunacode/core/agents/agent_components/tool_buffer.py` - Tool batching
- `src/tunacode/core/agents/agent_components/tool_executor.py` - Parallel execution
- `src/tunacode/services/mcp.py` - MCP server management

---

**Research Completed:** 2025-11-18 17:01:30
**Next Steps:**
1. Implement research agent factory following recommended approach
2. Create research system prompt in `prompts/research/system.xml`
3. Add `research_codebase` tool to main agent's tool list
4. Test delegation with simple queries
5. Validate usage aggregation behavior
6. Document any edge cases or limitations discovered
