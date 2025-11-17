# Agent Runtime Rebuild Plan

## Objectives
- Remove configuration defaults from `src/tunacode/core/agents/main.py` and instead consume a canonical, install-time configuration file or module.
- Rebuild the agent runtime orchestration with focused components so responsibilities (state prep, iteration control, guidance, fallback) are isolated and testable.
- Preserve current behavior (forced React guidance, fallback synthesis, tool batching) while clarifying flow and surface area for future features.

## Configuration Strategy
1. Introduce `tunacode.core.config.agent` (or similar) that loads agent defaults from the required config file at install time.
2. Expose a typed `AgentConfig`/`AgentLimits` dataclass with:
   - `max_iterations`, `debug_metrics_enabled`
   - Productivity thresholds (`unproductive_limit`)
   - React guidance cadence (`forced_interval`, `forced_limit`)
   - Fallback toggles + verbosity
3. `StateFacade` (or a dedicated adapter) merges per-session overrides (from `user_config`) onto `AgentConfig` so `main.py` never defines raw constants.

## Module Decomposition
- **AgentRuntime**: High-level orchestrator with `prepare`, `run_iterations`, `finalize` phases.
- **IterationLoop**: Drives `agent.iter`, streams tokens, updates iteration counters, consumes helper services.
- **NodeProcessor**: Wraps existing `ac._process_node` to produce a structured `NodeResult`.
- **ProductivityEnforcer**: Tracks tool usage streaks and emits forced-action nudges.
- **ReactGuidanceManager**: Handles timed snapshots, UI logging, and system message injection.
- **FallbackOrchestrator**: Builds progress summaries, clarification prompts, and fallback responses.
- **ToolBatchExecutor**: Buffers read-only tool calls and executes them with consistent UI output.
- **Clarification/EmptyResponse handlers**: Dedicated utilities for their respective prompts.

## Control Flow Outline
1. `process_request()`:
   - Load `AgentConfig`.
   - Build `StateFacade`, reset session, set original query/request id.
   - Instantiate `AgentRuntime` with dependencies (agent, config, UI hooks, React manager, tool buffer, fallback orchestrator).
2. `AgentRuntime.execute()`:
   - `prepare()` returns message history snapshot.
   - `run_iterations()` drives `IterationLoop`, which:
     - Streams tokens (`TokenStreamer` helper).
     - Calls `NodeProcessor` per node and updates `ResponseState`.
     - Applies productivity checks, forced React guidance, clarification prompts.
     - Stops on completion/limits, returning `IterationOutcome`.
   - `finalize()` flushes buffered read-only tools, decides between fallback synthesis and normal wrapper, and returns the final `AgentRun`.
3. Error handling remains centralized but now logs through structured helpers that include request metadata from `AgentConfig`.

## Testing & Docs (future steps)
- Add targeted unit tests for new config loader and helper services (e.g., productivity enforcer, fallback orchestrator).
- Document the new configuration file requirements and structure in README/CLAUDE docs.
- Run `ruff` + `hatch run test` after implementation.
