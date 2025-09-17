---
title: "Main Agent Refactor – Plan"
phase: Execution
date: "2025-09-17"
owner: "context-engineer"
parent_research: "memory-bank/research/main_agent_refactor_plan.md"
git_commit_at_plan: "ac20881"
tags: [plan, main_agent_refactor]
---

## Goal
Reintroduce the main agent refactor from `main_v2.py` while maintaining full backward compatibility and ensuring all existing functionality continues to work correctly.

## Scope & Assumptions
### In Scope:
- Replacing `main.py` with `main_v2.py` implementation
- Fixing public API exports from `tunacode.core.agents` package
- Resolving CLI import issues and name collisions
- Fixing state management bugs (original_query preservation)
- Eliminating fallback duplication
- Ensuring all tests pass

### Out of Scope:
- New features beyond the existing refactor
- Breaking changes to public APIs without deprecation
- Major architectural redesigns

### Assumptions:
- The hotfix for CLI imports is already applied (pointing to agent_components)
- Tests provide adequate coverage for existing functionality
- No additional files depend on internal helpers that would be affected

## Deliverables (DoD)
1. Updated `tunacode/core/agents/main.py` containing the refactored implementation
2. Proper public API exports in `tunacode/core/agents/__init__.py`
3. Updated CLI code with renamed helper function
4. Fixed state management in StateFacade
5. Eliminated duplicate fallback messages
6. All existing tests passing
7. Updated documentation for public API changes

## Readiness (DoR)
- Baseline test results from `hatch run test`
- Access to the `main_v2.py` artifact with the refactored implementation
- Understanding of current import patterns across the codebase
- CLI hotfix verification complete

## Milestones
### M1: Foundation & Test Baseline (Day 1)
- Capture current test baseline
- Document all import patterns and dependencies
- Prepare compatibility shims if needed

### M2: Public API Alignment (Day 1-2)
- Update package exports in `__init__.py`
- Fix import paths in runtime callers
- Create compatibility layer if needed

### M3: Refactor Integration (Day 2-3)
- Replace main.py with main_v2.py
- Fix state reset logic
- Eliminate fallback duplication
- Update CLI helper naming

### M4: Testing & Hardening (Day 3-4)
- Run full test suite and fix failures
- Add regression tests for specific bugs
- Verify CLI functionality end-to-end


## Work Breakdown (Tasks)

### T001: Capture Test Baseline
- **Summary**: Run full test suite before any changes
- **Owner**: context-engineer
- **Estimate**: 15m
- **Dependencies**: None
- **Target Milestone**: M1
- **Acceptance Tests**:
  - `hatch run test` completes successfully
  - Test results documented for comparison

- **Status**: Completed 2025-09-17 – Initial baseline `hatch run test` failed due to missing vendor ripgrep binary (`vendor/ripgrep/x64-linux/rg`). Environment repaired with ripgrep 14.1.1 and baseline now passes (303 passed, 12 skipped, 28s).

### T002: Analyze Import Dependencies
- **Summary**: Map all imports from tunacode.core.agents
- **Owner**: context-engineer
- **Estimate**: 30m
- **Dependencies**: T001
- **Target Milestone**: M1
- **Acceptance Tests**:
  - Complete list of importing files and functions
  - Identification of critical vs internal imports

- **Status**: Completed 2025-09-17 – Runtime imports rely on `process_request`, `extract_and_execute_tool_calls`, `patch_tool_messages`, and `get_or_create_agent` via CLI modules (`src/tunacode/cli/repl.py`, `cli/repl_components/{error_recovery,tool_executor}`, `cli/commands/implementations/{debug,system}`). Test-only imports cover broader internals (`agent_components`, `_process_node`, `ResponseState`, `ToolBuffer`, etc.) informing compatibility requirements.

### T003: Define Public API Surface
- **Summary**: Finalize which functions are public vs internal
- **Owner**: context-engineer
- **Estimate**: 20m
- **Dependencies**: T002
- **Target Milestone**: M2
- **Acceptance Tests**:
  - Clear documentation of public API
  - Agreement on function categorization

- **Status**: Completed 2025-09-17 – Public API grouped into primary runtime exports, legacy compatibility exports, and non-exported internals (documented in Execution Notes).

### T004: Update Package Exports
- **Summary**: Modify __init__.py to properly export public functions
- **Owner**: context-engineer
- **Estimate**: 15m
- **Dependencies**: T003
- **Target Milestone**: M2
- **Acceptance Tests**:
  - All public functions importable from package root
  - Internal functions remain private
- **Files/Interfaces**: `tunacode/core/agents/__init__.py`

- **Status**: Completed 2025-09-17 – `tunacode.core.agents` now re-exports runtime and compatibility functions (e.g., `process_request`, `_process_node`, `AgentRunWrapper`, `get_agent_tool`) consolidating public API surface.

### T005: Fix Runtime Import Paths
- **Summary**: Update CLI and other callers to use package imports
- **Owner**: context-engineer
- **Estimate**: 30m
- **Dependencies**: T004
- **Target Milestone**: M2
- **Acceptance Tests**:
  - All imports work without errors
  - No breaking changes to functionality
- **Files/Interfaces**: `src/tunacode/cli/repl.py`

- **Status**: Completed 2025-09-17 – CLI helper renamed to `execute_repl_request` with `process_request` kept as a compatibility alias; command registry/tests updated to use the new name, eliminating internal name collisions.

- **Status**: Completed 2025-09-17 – CLI components now import from `tunacode.core.agents` package exports (`repl`, `repl_components`, debug/system commands) removing direct `main` references ahead of refactor swap.

### T006: Replace Main Implementation
- **Summary**: Swap main.py with main_v2.py content
- **Owner**: context-engineer
- **Estimate**: 15m
- **Dependencies**: T005
- **Target Milestone**: M3
- **Acceptance Tests**:
  - New code loads without syntax errors
  - Basic functionality tests pass
- **Files/Interfaces**: `tunacode/core/agents/main.py`

- **Status**: Completed 2025-09-17 – `main.py` now uses the refactored `main_v2` flow with compatibility re-exports (RequestContext/StateFacade maintained).

### T007: Fix State Reset Logic
- **Summary**: Ensure original_query is properly cleared
- **Owner**: context-engineer
- **Estimate**: 20m
- **Dependencies**: T006
- **Target Milestone**: M3
- **Acceptance Tests**:
  - Multiple requests don't carry stale prompts
  - State is clean between requests
- **Files/Interfaces**: `tunacode/core/agents/main.py`

- **Status**: Completed 2025-09-17 – Session reset now clears `original_query` before each request, preventing stale prompts across runs.

### T008: Eliminate Fallback Duplication
- **Summary**: Fix double patching of tool messages
- **Owner**: context-engineer
- **Estimate**: 15m
- **Dependencies**: T006
- **Target Milestone**: M3
- **Acceptance Tests**:
  - Only one "Task incomplete" message appears
  - Tool messages are correctly formatted
- **Files/Interfaces**: `tunacode/core/agents/main.py`

- **Status**: Completed 2025-09-17 – Removed duplicate fallback patching so only one 'Task incomplete' message is emitted.

### T009: Rename CLI Helper Function
- **Summary**: Rename process_request in CLI to avoid collision
- **Owner**: context-engineer
- **Estimate**: 20m
- **Dependencies**: T005
- **Target Milestone**: M3
- **Acceptance Tests**:
  - CLI functionality unchanged
  - No name collisions in code
  - All references updated
- **Files/Interfaces**: `src/tunacode/cli/repl.py`

- **Status**: Completed 2025-09-17 – CLI helper renamed to `execute_repl_request` with `process_request` kept as a compatibility alias; command registry/tests updated to use the new name, eliminating internal name collisions.

### T010: Full Regression Testing
- **Summary**: Run complete test suite and fix failures
- **Owner**: context-engineer
- **Estimate**: 60m
- **Dependencies**: T006, T007, T008, T009
- **Target Milestone**: M4
- **Acceptance Tests**:
  - All existing tests pass
  - No regressions detected
  - Performance not degraded

### T011: Add Bug Regression Tests
- **Summary**: Create tests for specific bugs fixed
- **Owner**: context-engineer
- **Estimate**: 45m
- **Dependencies**: T010
- **Target Milestone**: M4
- **Acceptance Tests**:
  - Test for state management fix
  - Test for fallback duplication fix
  - Test for CLI functionality
- **Files/Interfaces**: New test files

## Execution Notes

### Phase Progress
- Phase 1 (T001-T003) complete; baseline captured and import surface documented.
- Phase 2 (T004-T005) closed with package exports and CLI callers aligned to new surface; ready to begin Phase 3 integration work.


### Public API Surface (T003)
- Primary exports: `process_request`, `get_or_create_agent`, `extract_and_execute_tool_calls`, `patch_tool_messages`, `check_task_completion`, `parse_json_tool_calls`, `ToolBuffer`, `get_model_messages`, `ResponseState`, `SimpleResult`, `execute_tools_parallel`, `get_mcp_servers`.
- Legacy compatibility exports (retain for tests/backwards use): `_process_node`, `check_query_satisfaction`, `AgentRunWrapper`, `AgentRunWithState`, `get_agent_tool`.
- Internal helpers (remain unexported; consumed via `agent_components`): message creation helpers, fallback builders, UI patching utilities.

### Tool Recovery Alignment (T005/T010)
- Updated `attempt_tool_recovery` to call `tunacode.core.agents.extract_and_execute_tool_calls`, ensuring CLI uses the unified API surface.
- Characterization tests patched to mock the package-level export, keeping tool recovery coverage valid post-refactor.


## Risks & Mitigations
### Risk 1: Additional hidden dependencies
- **Impact**: High - could cause runtime failures
- **Likelihood**: Medium
- **Mitigation**: Comprehensive grep search for all imports
- **Trigger**: Found during T002

### Risk 2: State management fix breaks existing behavior
- **Impact**: Medium - could affect request processing
- **Likelihood**: Low
- **Mitigation**: Careful testing of multi-request scenarios
- **Trigger**: Detected during T007 testing

### Risk 3: Performance regression
- **Impact**: Medium - could slow down response times
- **Likelihood**: Low
- **Mitigation**: Benchmark before and after changes
- **Trigger**: If performance tests fail

### Risk 4: Test failures uncover deeper issues
- **Impact**: High - could delay refactor
- **Likelihood**: Medium
- **Mitigation**: Plan for additional debugging time
- **Trigger**: Multiple test failures in T010

## Test Strategy
### Unit Tests
- Test all public API functions
- Test state management edge cases
- Test fallback behavior
- Test error handling

### Integration Tests
- CLI end-to-end functionality
- Import compatibility across modules
- Request processing lifecycle

### Regression Tests
- Specific tests for fixed bugs
- Performance benchmarks
- Memory usage verification

## Security & Compliance
- No secret handling changes
- No authentication/authorization changes
- Maintain existing input validation
- No new external dependencies

## Observability
- Maintain existing logging patterns
- No new metrics required
- Error reporting remains unchanged

## Rollout Plan
1. All changes in single branch
2. No feature flags needed
3. Immediate rollout upon successful testing
4. Rollback by reverting to commit d88c959 if issues arise

## Validation Gates
### Gate A - Design Sign-off
- [ ] Public API definition agreed
- [ ] Import analysis complete
- [ ] Risk assessment reviewed

### Gate B - Test Plan Sign-off
- [ ] Test coverage adequate
- [ ] Regression tests identified
- [ ] Performance baseline captured

### Gate C - Pre-merge Quality
- [ ] All tests passing
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] No known issues

### Gate D - Pre-deploy
- [ ] Staging testing complete
- [ ] Performance verified
- [ ] Rollback plan tested

## Success Metrics
- Zero test failures
- Zero regressions in functionality
- CLI performance unchanged or improved
- Code complexity reduced
- No reported issues after deployment

## References
- Research doc: memory-bank/research/main_agent_refactor_plan.md
- Hotfix commit: cfaefb8
- Snapshot commit: d88c959
- Artifact: src/tunacode/core/agents/main_v2.py

## Summary
Plan created with 13 tasks across 5 milestones, focusing on safe reintroduction of the main agent refactor while maintaining full backward compatibility. Next command: `/execute "/home/fabian/tunacode/memory-bank/plan/2025-09-17_main-agent-refactor_plan.md"`
