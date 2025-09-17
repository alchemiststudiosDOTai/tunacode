# Main Agent Refactor Recovery Plan

Date: 2025-09-17
Status: Planning (no code changes applied yet)
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
- Should CLI rename its helper to avoid name collision with agent coroutine? (Recommended for clarity.)
- Which helpers should be considered public API vs internal (`_process_node`, etc.)?

This document will guide controlled rollout of the refactor, reducing risk of repeated rollbacks.
