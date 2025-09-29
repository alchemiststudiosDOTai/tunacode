# Simplified Agent Implementation – Handoff Plan

**Phase:** Implementation Readiness (handoff)
**Date:** 2025-09-29
**Owner:** context-engineer:plan
**Parent Research:** memory-bank/research/2025-09-29_11-08-14_state_and_task_logic.md
**Repo Snapshot:** 269f84a7a766057e3011e0f218f1011466f0bd25 (git rev-parse HEAD)
**Tags:** [plan, simplification, agent-refactoring, completion-detection-fix]

## Current Verification Snapshot (2025-09-29)
- `process_request` remains a 189-line loop with competing completion logic (`src/tunacode/core/agents/main.py:416` → `:604`).
- No simplified entry point exists yet (`rg "process_request_simple"` → no matches).
- System prompt still mandates `TUNACODE DONE:` markers (`src/tunacode/core/agents/agent_components/agent_config.py:176`).
- Productivity counters (`UNPRODUCTIVE_LIMIT`, forced React snapshots) continue to influence stop conditions.

### Proof Artifacts
- `python - <<'PY' ...` run on 2025-09-29 → `process_request spans lines 416-604 (189 lines)`.
- `rg "process_request_simple" -n src/tunacode/core/agents/main.py` → exit code 1 (no definition yet).
- `src/tunacode/core/agents/agent_components/agent_config.py:168-189` documents forced completion markers outside plan mode.

## Target Outcomes
1. Ship `process_request_simple()` (~40 lines) alongside the legacy function without regressions.
2. Remove reliance on artificial completion markers; rely on "no tool calls in last turn" to stop.
3. Preserve streaming, tool execution, and error propagation semantics.
4. Demonstrate parity via characterization tests and add new coverage for premature completion scenarios.

## Streamlined Implementation Plan (v2)

### Phase A – Baseline Guardrails
- [ ] A1. Freeze complex `process_request` behavior with a golden test capturing current completion output (`tests/characterization/` suggested location).
- [ ] A2. Document all completion triggers from the legacy pipeline (markers, productivity counters, iteration cap) for reference in `.claude/metadata/`.

### Phase B – Minimal Simple Loop
- [ ] B1. Introduce `process_request_simple()` in `src/tunacode/core/agents/main.py` with explicit typing, accepting the same signature.
- [ ] B2. Extract `_execute_node_tools()` helper returning `ToolExecutionResult` dataclass featuring `has_tool_calls: bool` and optional error payload.
- [ ] B3. Implement loop: process nodes, execute tools, continue when tools executed, otherwise return `AgentRun`.
- [ ] B4. Remove productivity counters and forced React nudges from the simple path (keep legacy path untouched).

### Phase C – Completion Detection Validation
- [ ] C1. Add failing test demonstrating premature `TUNACODE DONE` behavior in the old path.
- [ ] C2. Extend the test to assert the simple path continues until no tool calls remain.
- [ ] C3. Ensure streaming callback gets invoked identically between paths (mock assertion).

### Phase D – Integration & Rollout
- [ ] D1. Add feature flag or CLI switch to opt into the simple path for side-by-side validation.
- [ ] D2. Capture metrics to `.claude/delta_summaries/api_change_logs.json` summarizing completion behavior change.
- [ ] D3. Update `documentation/agent/agent-flow.md` to describe the new natural completion logic and removal of forced markers.
- [ ] D4. Run `ruff check --fix .` and `hatch run test` before merge.

## Acceptance Criteria
- `process_request_simple()` returns an `AgentRun`/`AgentRunWithState` compatible object with the legacy interface.
- Tool execution errors bubble with context; no silent fallbacks.
- Characterization baseline protects the legacy behavior until the simple loop is validated.
- Tests describe the premature completion bug and prove the fix.
- `.claude` knowledge base updated: metadata (dependencies), semantic index (call graph), delta summaries (behavioral shift), debug history (bug → fix narrative).

## Validation Strategy
- TDD: write the failing premature-completion test first, then implement, then refactor.
- Use deterministic fixtures to emulate tool/no-tool iterations.
- Track completion via tool call count and final response status in assertions.
- Compare streaming callback call counts between legacy and simple paths.

## Risks & Mitigations
- **Loss of functionality** → Keep legacy path; gate rollout by flag until parity proven.
- **Hidden dependencies on productivity counters** → Characterize expectations before removing; provide toggles for gradual disablement.
- **Tool execution regressions** → Wrap helper with explicit error typing; unit-test helper directly.
- **Documentation drift** → Update agent flow diagrams in step D3 as part of DoD.

## Hand-Off Notes for Next Developer
1. Re-use existing `StateFacade` and tool buffer helpers; avoid hidden state.
2. Keep variable initialization adjacent to first use; return early to reduce nesting.
3. Normalize naming between legacy/simple paths (e.g., `has_tool_calls`, `response_state`).
4. When updating `.claude`, add entries to:
   - `metadata/dependency_map.json`
   - `semantic_index/function_call_graphs.json`
   - `delta_summaries/api_change_logs.json`
   - `debug_history/premature_completion_fix.json`
5. After implementation, document proof of fix (before/after logs) in `.claude/qa/` for reuse.

## Next Command
`/execute "memory-bank/plan/2025-09-29_11-15-30_simplified_agent_implementation.md"`
