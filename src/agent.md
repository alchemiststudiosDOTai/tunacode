gent Flow Overview

  - Summary: process_request orchestrates the full agent lifecycle from setup
  through iterative reasoning, tool execution, safeguards, and termination,
  surfacing fallback answers or errors when needed (src/tunacode/core/agents/
  main.py:104-449).
    Detailed analysis: The agent is configured and invoked via agent.iter, with the
  loop mediating between model outputs and TunaCode’s session state. Control logic
  around streaming, buffering, tool execution, and UI feedback keeps the agent
  responsive while enforcing productivity, and post-loop handlers guarantee either
  a synthesized result or explicit failure propagation.

  Seam 1 – Module Scaffolding and Dependencies (src/tunacode/core/agents/main.py:1-
  84)

  - Summary: Defines the module’s exports and consolidates agent component imports.
    Detailed analysis: Beyond descriptive docstrings, this seam aggregates
  numerous helpers from .agent_components, exposing them through __all__.
  Central dependencies—logging, state management, tool metadata, and streaming
  compatibility checks—are resolved here so process_request can delegate behavior
  such as node processing, fallback formatting, and buffered execution without
  redefining them.

  Seam 2 – Lazy Agent Imports (src/tunacode/core/agents/main.py:87-92)

  - Summary: get_agent_tool defers importing Agent/Tool to avoid circular
  references.
    Detailed analysis: The helper fetches the canonical Agent class whenever
  needed inside the loop (e.g., to detect model request nodes), keeping top-level
  imports lightweight while preventing recursive module loading. Returning both
  types allows downstream seams to use a unified accessor when tool class metadata
  is required.

  Seam 3 – Query Satisfaction Stub (src/tunacode/core/agents/main.py:94-101)

  - Summary: Placeholder always returns True, shifting completion detection to
  model output.
    Detailed analysis: The comment clarifies that DONE markers in responses
  now govern completion, so this seam primarily exists to satisfy interface
  expectations while avoiding recursive agent evaluation that previously caused
  empty outputs.

  Seam 4 – Request Initialization (src/tunacode/core/agents/main.py:104-162)

  - Summary: Prepares agent, session, and tracking structures prior to iteration.
    Detailed analysis: After resolving the Agent instance via get_or_create_agent,
  a UUID-based request_id is attached to the session for downstream logging.
  Session counters and tool call history reset, a batch counter is ensured,
  and a fresh ToolBuffer plus ResponseState object are created. User-configured
  max_iterations is read once, establishing the guardrails for the ensuing loop.

  Seam 5 – Agent Iteration & Streaming Hook (src/tunacode/core/agents/main.py:168-
  195)

  - Summary: Consumes the async generator from agent.iter, proxying streaming
  tokens when supported.
    Detailed analysis: The loop records iteration indices in session state and,
  when streaming is enabled, calls stream_model_request_node for model request
  nodes detected via Agent.is_model_request_node. Each node then flows through
  _process_node, which encapsulates tool execution, message patching, and updates
  to ResponseState. The seam ensures event-driven progress while cleanly isolating
  node-level processing logic.

  Seam 6 – Empty Response Recovery (src/tunacode/core/agents/main.py:197-226)

  - Summary: Detects empty outputs and injects corrective user messages to force
  action.
    Detailed analysis: Consecutive empty responses increment a session counter,
  and once triggered, create_empty_response_message crafts a guidance prompt
  seeded with current task context and tool history. The prompt is appended through
  create_user_message, and optional UI logging alerts the operator. Resetting the
  counter prevents runaway loops while giving the model explicit instructions on
  how to recover.

  Seam 7 – Response Detection (src/tunacode/core/agents/main.py:230-233)

  - Summary: Flags when the agent produces a user-visible output.
    Detailed analysis: By interrogating node.result.output, the seam sets
  response_state.has_user_response. This feeds later fallback logic, allowing the
  system to decide whether a synthesized answer is required when the loop exits
  without producing a final message.

  Seam 8 – Productivity Enforcement (src/tunacode/core/agents/main.py:234-276)

  - Summary: Monitors tool usage per iteration and forces action after repeated
  inactivity.
    Detailed analysis: The code inspects response parts for tool-call segments,
  resetting unproductive_iterations whenever a tool is used. After three empty
  iterations, it injects an escalating prompt demanding immediate action or
  completion, with UI feedback if thoughts are visible. last_productive_iteration
  aids in diagnostic messaging, and counters reset after the forced prompt to avoid
  repeated triggers.

  Seam 9 – Context Tracking & Observability (src/tunacode/core/agents/main.py:281-
  298)

  - Summary: Persists the original query and emits progress telemetry when thoughts
  are shown.
    Detailed analysis: Preserving original_query ensures future prompts (like
  clarification requests) reference the user’s intent. When verbose mode is active,
  the seam logs iteration counts and a summarized breakdown of tools invoked,
  helping both developers and users audit the agent’s path in real time.

  Seam 10 – Clarification & Iteration Limit Handling (src/tunacode/core/agents/
  main.py:299-360)

  - Summary: Drives user re-engagement when guidance is required or iteration caps
  are reached.
    Detailed analysis: If ResponseState signals a need for user guidance, the
  agent crafts a progress recap via create_progress_summary and asks for direction,
  mirroring messages in the UI. Should iterations reach the configured limit
  without completion, a separate message offers options to continue, summarize,
  or pivot, simultaneously extending the cap by five and flagging the state as
  awaiting guidance.

  Seam 11 – Loop Termination & Counter Increment (src/tunacode/core/agents/
  main.py:325-364)

  - Summary: Breaks when tasks complete and advances iteration counters otherwise.
    Detailed analysis: Upon detecting response_state.task_completed, the loop
  thanks success and exits. If neither completion nor iteration limit triggers
  occur, the counter increments to maintain accurate tracking for diagnostics and
  guardrails.

  Seam 12 – Buffered Tool Flush (src/tunacode/core/agents/main.py:365-418)

  - Summary: Executes any deferred read-only tool calls in a final batch with UI
  instrumentation.

  Composing detailed final summary outline (1m 17s • Esc to interrupt)
    Detailed analysis: After the main loop, buffered tasks
  are flushed if a tool_callback exists. The seam announces
  batch execution via UI hooks, lists per-tool metadata for
  transparency, and times the batch to report perceived speedup
  over sequential execution. It also resets the spinner to the
  default thinking message to maintain UX parity.

  Seam 13 – Fallback Response Synthesis (src/tunacode/core/
  agents/main.py:419-449)

  - Summary: Produces a synthetic summary when no user response
  was generated and limits were hit.
    Detailed analysis: When the agent stalled without output but
  iterations exceeded max_iterations and fallbacks are enabled,
  the system patches outstanding tool messages, assembles a
  fallback structure using create_fallback_response, formats it,
  and wraps the original agent_run in an AgentRunWrapper carrying
  the synthesized result. Without fallback, it still returns an
  AgentRunWithState to relay the ResponseState upwards.

  Seam 14 – Error Propagation (src/tunacode/core/agents/
  main.py:451-475)

  - Summary: Converts exceptions into logged diagnostics and
  patches session messages before re-raising.
    Detailed analysis: UserAbortError bubbles up untouched,
  while ToolBatchingJSONError logs detail and patches tools with
  a concise failure note. The generic exception handler logs
  contextualized errors (embedding request_id and iteration),
  updates tool messages with a truncated failure reason, and re-
  raises, ensuring external callers decide on recovery while
  users see why the run stopped.
