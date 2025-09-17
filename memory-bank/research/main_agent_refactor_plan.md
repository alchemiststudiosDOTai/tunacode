# Main Agent Refactor Recovery Plan

Date: 2025-09-17
Status: Execution (phases 1-3 complete)
Artifact: `src/tunacode/core/agents/main_v2.py`

## Context
The refactored agent entry point (`main_v2.py`) provides much cleaner structure but broke the CLI due to API drift and mismatched expectations across the codebase. We rolled back to the snapshot commit (`d88c959`) to stabilize. This plan outlines how to reintroduce the refactor gradually, prioritising compatibility and test coverage.

## Root Causes Identified
1. **Public API divergence**
   - Downstream modules import helpers directly from `tunacode.core.agents.main`, while refactor moved them into `agent_components` without re-exporting.
   - CLI code shadows the agent coroutine by defining its own `process_request`, leading to unexpected keyword arguments when calling the agent-level function.

2. **State management assumptions**
   - `StateFacade.reset_for_new_request` preserves `original_query`, causing stale prompts once multiple requests are processed.

3. **Fallback duplication**
   - Both `_build_fallback_output` and its caller patch tool messages, creating duplicate “Task incomplete” entries.

4. **Test coverage gaps**
   - No tests assert that CLI imports remain valid or that CLI `process_request` continues to accept the same keyword arguments.

## Completed Work
- Phase 1 aligned the public API: `tunacode.core.agents.__init__` now re-exports runtime helpers and CLI callers import from the package surface.
- Phase 2 landed the refactored `main.py` from `main_v2.py`, keeping RequestContext/StateFacade while re-exporting compatibility shims.
- State reset now clears `original_query`, and fallback synthesis no longer double-patches tool messages.
- CLI helper renamed to `execute_repl_request` with a compatibility alias, resolving name collisions and keeping external integrations working.
- Characterization tests updated to mock the package API and to provide agent run context (`ctx`), maintaining coverage for tool recovery and request processing flows.

## Key Benefits
- Remaining references to `tunacode.core.agents.main.*` now exist only in tests; production code uses the package API.
- Action item: migrate the test harness to import from `tunacode.core.agents`/`agent_components` so the temporary re-export shim in `main.py` can be removed.
- Restored refactored agent architecture without breaking existing consumers.
- Eliminated duplicate fallback messaging and stale query leakage between requests.
- Clarified public API boundaries, making future agent refactors safer.
- Simplified CLI/test imports by pointing to the package root, reducing coupling to module internals.


## Phased Recovery Strategy
### Phase 0 – Documentation & Scaffolding (current)
- Document failure points (done).
- Define target public API surface for `tunacode.core.agents` package.
- Record completed hotfix: CLI imports for `patch_tool_messages` and `extract_and_execute_tool_calls` now point to
  `tunacode.core.agents.agent_components`, resolving the post-refactor `ImportError`s.

### Phase 1 – Public API Alignment
- Update `tunacode.core.agents.__init__` to explicitly export supported entry points (`process_request`, `get_or_create_agent`, `patch_tool_messages`, etc.).
- Refactor runtime callers (CLI, commands) to import from package root rather than `.main`.
- Provide temporary compatibility shim or clear migration path for tests.


### Phase 2 – Refactor Reintroduction
- Replace `main.py` contents with the `main_v2.py` implementation.
- Ensure the refactored module re-exports necessary helpers or delegates to `agent_components` via package-level API.
- Fix state reset logic (`original_query` clear) and fallback duplication.

### Testing Cadence (applies to every phase)
- Run `hatch run test` before making code changes to capture the current baseline.
- After applied updates, run `hatch run test` again to detect regressions.
- If failures arise, update or add tests before proceeding to the next phase.

## Open Questions / Decisions Needed
- Should CLI rename its helper to avoid name collision with agent coroutine? ✅ Completed – helper renamed to `execute_repl_request` with `process_request` alias preserved.
- Which helpers should be considered public API vs internal (`_process_node`, etc.)?

 - CLI helper rename (docs/reviews/main_agent_refactor_plan.md:48): today src/tunacode/cli/repl.py uses a
  function named process_request, which shadows the real agent coroutine. Renaming the CLI helper (for example
  to run_agent_request) would prevent confusion and accidental import collisions.
  - Public API vs internal helpers (docs/reviews/main_agent_refactor_plan.md:49): we need to decide which
  functions in tunacode.core.agents.agent_components (e.g., _process_node, patch_tool_messages) we officially
  support for other modules. Everything left “internal” should be treated as private so refactors can move
  them without breaking consumers.
