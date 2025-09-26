# Main Agent Architecture

## Purpose
- This reference consolidates research from three agents and the authoritative code to describe the TunaCode main agent seams, control flow, and integration points for future maintenance.[^R-seams][^C-process]

## System Seams at a Glance
| Seam | Responsibilities | Key Artifacts |
| --- | --- | --- |
| Orchestration Loop | Coordinates request lifecycle, streaming, forced React snapshots, productivity nudges, and fallback synthesis.[^R-seams][^C-process][^C-stream][^C-react][^C-recovery] | `src/tunacode/core/agents/main.py` (StateFacade, `_init_context`, `process_request`).[^C-statefacade][^C-context] |
| Agent Configuration | Loads prompts, merges todo context, selects tools per mode, and caches agents with MCP integration.[^R-seams][^C-agent-config] | `src/tunacode/core/agents/agent_components/agent_config.py`.[^C-agent-config] |
| Node Processing | Evaluates model responses, buffers tools, enforces completion safety, and tracks truncation/intent.[^R-flow][^C-node] | `src/tunacode/core/agents/agent_components/node_processor.py`.[^C-node] |
| Tool Execution | Buffers read-only tasks, batches them in parallel, and preserves sequential semantics for writes.[^R-flow][^C-buffer][^C-executor][^C-tool-categories] | `tool_buffer.py`, `tool_executor.py`, `constants.py`.[^C-buffer][^C-executor][^C-tool-categories] |
| State & Response Management | Provides facade resets, enum-based state machine, and legacy flag compatibility.[^R-seams][^C-statefacade][^C-response][^C-state-transition] | `main.py` StateFacade, `response_state.py`, `state_transition.py`.[^C-statefacade][^C-response][^C-state-transition] |
| Reasoning & Streaming | Streams tokens when supported and injects forced React guidance into the run context.[^R-flow][^C-stream][^C-react] | `_maybe_stream_node_tokens`, `_maybe_force_react_snapshot` in `main.py`.[^C-stream][^C-react] |
| Recovery & Completion | Detects empty/truncated output, forces action after idle loops, and strips completion markers.[^R-flow][^C-node][^C-task-complete][^C-recovery] | `_handle_empty_response`, `_force_action_if_unproductive`, `task_completion.py`.[^C-recovery][^C-task-complete] |

## End-to-End Flow
1. Initialize a `RequestContext`, apply user-configured limits, and reset session counters before dispatching to the model run.[^R-flow][^C-context][^C-statefacade]
2. Acquire or reuse a configured agent with cached prompts, todo context, MCP servers, and mode-specific tool lists.[^R-flow][^C-agent-config]
3. Iterate model nodes, streaming tokens, delegating to `_process_node`, and updating response state for each turn.[^R-flow][^C-process][^C-node][^C-response]
4. Buffer read-only tool calls, execute them in parallel batches, and run write/execute tools sequentially to maintain ordering.[^R-flow][^C-buffer][^C-executor][^C-tool-categories][^C-process]
5. Apply safety rails: react snapshots, empty-response recovery, and productivity nudges until completion markers or iteration limits stop the loop.[^R-flow][^C-react][^C-recovery][^C-task-complete][^C-process]
6. Flush residual tool batches, build fallback synthesis when needed, and return an `AgentRun` wrapper carrying the final `ResponseState`.[^R-flow][^C-process][^C-response]

## Seam Deep Dives

### 1. Orchestration Layer (`main.py`)
- `StateFacade` centralizes session mutation, ensuring iteration counters, empty-response streaks, and original queries stay in sync for every request.[^R-seams][^C-statefacade]
- `_init_context` assigns an 8-character request ID and derives iteration/debug settings from user config, storing them in the lightweight `RequestContext` dataclass.[^R-flow][^C-context]
- `process_request` acquires the agent, replays message history, is instrumented for streaming, delegates to `_process_node`, tracks productivity, and manages fallback synthesis.[^R-flow][^C-process]
- `_handle_empty_response` injects retry prompts when the model produces empty or truncated output, while `_force_action_if_unproductive` sends a corrective system message after repeated idle turns.[^R-flow][^C-recovery]

### 2. Agent Configuration & Prompt Loading
- Module-level caches hold system prompts, AGENTS.md context, and agent instances to avoid redundant file I/O and model construction across requests.[^R-seams][^C-agent-config]
- `get_or_create_agent` inspects session caches, invalidates when plan mode or retry limits change, and builds the agent with the configured tool list and MCP servers.[^R-flow][^C-agent-config]
- Plan mode restricts tools to read-only plus `present_plan`, while normal mode exposes the full execution set including `bash`, `run_command`, and file mutation tools.[^R-flow][^C-agent-config][^C-tool-categories]

### 3. Node Processing & Completion Safety
- `_process_node` records thoughts, appends model responses to session history, and buffers tool calls for later execution while respecting streaming availability.[^R-flow][^C-node]
- The function guards against premature completion by rejecting DONE markers when tools are queued and by checking for stated-but-unexecuted intentions in early turns.[^R-flow][^C-node]
- Truncation heuristics and empty-content checks flag unusable responses so recovery routines can re-prompt the agent.[^R-flow][^C-node]
- Completion markers are stripped and replaced with clean content using `check_task_completion`, preserving legacy protocols while updating the state machine.[^R-flow][^C-node][^C-task-complete]

### 4. Tool Execution Pipeline
- `ToolBuffer` stores read-only calls until a write or execute request forces a flush, keeping expensive tools batched for concurrency.[^R-flow][^C-buffer]
- `execute_tools_parallel` honors the `TUNACODE_MAX_PARALLEL` ceiling, batches large sets, and isolates exceptions so one tool failure does not cancel the batch.[^R-flow][^C-executor]
- Tool-category constants keep read, write, and execute behaviors consistent across components and tests.[^R-seams][^C-tool-categories]

### 5. State & Response Management
- `ResponseState` wraps the enum state machine, exposing legacy boolean flags while keeping authoritative transitions inside `AgentStateMachine`.[^R-seams][^C-response][^C-state-transition]
- Transition rules permit `USER_INPUT → ASSISTANT → TOOL_EXECUTION → RESPONSE` loops and allow returning to `ASSISTANT` when the run continues.[^R-flow][^C-state-transition]
- When `ResponseState` registers completion, it synchronizes the enum state, sets synthesis flags, and feeds the information back to `process_request` for exit decisions.[^R-flow][^C-response][^C-process]

### 6. Reasoning, Streaming, and Guidance
- `_maybe_stream_node_tokens` delegates to the streaming component when the provider supports incremental tokens, otherwise the fallback path in `_process_node` emits chunked text.[^R-flow][^C-stream][^C-node]
- `_maybe_force_react_snapshot` triggers every second iteration (up to five times), records scratchpad guidance, injects a synthetic system prompt into the active run, and surfaces debug output when thoughts are enabled.[^R-flow][^C-react]
- React guidance entries summarize the latest tool usage so the next LLM turn stays grounded in prior actions.[^R-flow][^C-react][^C-process]

### 7. Recovery, Fallback, and Completion
- Empty or truncated responses are patched with targeted follow-up prompts built by `agent_components.create_empty_response_message`, keeping the model moving toward actionable output.[^R-flow][^C-recovery]
- Productivity nudges reset after tool execution and prevent the agent from idling for more than three iterations.[^R-flow][^C-process][^C-recovery]
- When iteration limits are reached without completion, `process_request` builds a comprehensive fallback summary via `AgentRunWrapper`, ensuring downstream consumers receive a consistent response object.[^R-flow][^C-process][^C-response]

## Extension & Integration Notes
- MCP server integration is wired during agent creation, so adding new external tools only requires updating state manager configuration.[^R-seams][^C-agent-config]
- Todo context loads into the system prompt via `TodoTool`, providing situational awareness without modifying the orchestration loop.[^R-flow][^C-agent-config]
- Plan mode instructions scrub completion markers from the prompt and enforce tool-only communication, preventing premature exit signals during planning tasks.[^R-flow][^C-agent-config][^C-task-complete]

---

[^R-seams]: memory-bank/research/2025-09-26_10-56-29_main_agent_architecture.md:29,36,43 (Key Patterns sections enumerating orchestration, modular components, and state management seams).
[^R-flow]: memory-bank/research/2025-09-26_10-56-29_main_agent_architecture.md:213,220,226,231,236,241 (Workflow Process bullets describing each phase).
[^C-process]: src/tunacode/core/agents/main.py:468,503,525,546,590,623 (process_request loop handling node iteration, recovery, and fallback).
[^C-context]: src/tunacode/core/agents/main.py:76,165,172 (defaults and RequestContext initialization).
[^C-statefacade]: src/tunacode/core/agents/main.py:97,128,149 (StateFacade management of session state).
[^C-stream]: src/tunacode/core/agents/main.py:184,197 (token streaming delegation).
[^C-react]: src/tunacode/core/agents/main.py:212,229,266,288 (forced React snapshot guidance injection).
[^C-node]: src/tunacode/core/agents/agent_components/node_processor.py:30,83,95,114,182 (node handling for tool calls, completion markers, and truncation checks).
[^C-buffer]: src/tunacode/core/agents/agent_components/tool_buffer.py:6,12,16,22 (read-only tool buffering workflow).
[^C-executor]: src/tunacode/core/agents/agent_components/tool_executor.py:14,28,39,44 (parallel execution with batching and error isolation).
[^C-response]: src/tunacode/core/agents/agent_components/response_state.py:11,36,55,105 (enum-backed response state and legacy flag synchronization).
[^C-state-transition]: src/tunacode/core/agents/agent_components/state_transition.py:24,40,62,109 (AgentStateMachine transition rules and validation).
[^C-task-complete]: src/tunacode/core/agents/agent_components/task_completion.py:6,12,29,33 (completion marker detection and cleanup).
[^C-agent-config]: src/tunacode/core/agents/agent_components/agent_config.py:25,127,161,236,254,266,296 (caching, todo integration, plan vs normal tool registration, MCP servers).
[^C-tool-categories]: src/tunacode/constants.py:65,73 (read-only, write, and execute tool classifications).
[^C-recovery]: src/tunacode/core/agents/main.py:294,318,337 (empty-response prompts and unproductive iteration nudges).
