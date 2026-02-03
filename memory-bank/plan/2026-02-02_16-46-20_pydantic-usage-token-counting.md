---
title: "Switch Token Counting to Pydantic-AI Usage Totals – Plan"
phase: Plan
date: "2026-02-02T22:46:20Z"
owner: "claude"
parent_research: ""
git_commit_at_plan: "22cca4726cf1f5efc1e64cb0b89e6967aebf100e"
tags: [plan, tokens, usage, ui]
---

## Goal

Stop per-message heuristic token counting and use pydantic-ai per-call usage totals as the source of truth for token display.

**Non-goals:**
- No UI redesigns or visual style changes
- No changes to LLM providers or retry logic
- No new dependencies

## Scope & Assumptions

**In scope:**
- Replace the UI token source with pydantic-ai usage totals
- Remove or retire per-message `estimate_messages_tokens` usage in runtime flows
- Ensure persisted sessions and runtime state stay coherent

**Out of scope:**
- Any change to tool output pruning heuristics
- Pricing model changes
- Streaming logic changes

**Verified facts (no assumptions):**
- `ModelResponse.usage` is always present but can be empty (pydantic-ai returns zeroed `RequestUsage` when provider usage is missing).
- `RequestUsage` exposes deprecated `request_tokens`/`response_tokens` properties (mapped to `input_tokens`/`output_tokens`).
- `RequestUsage` does not provide a `cached_tokens` attribute (we currently default cached tokens to 0 in normalization).
- Using usage totals will reflect *API usage totals*, not context window size.

## Deliverables (DoD)

1. UI token display uses accumulated pydantic-ai usage totals
2. Heuristic per-message token counting is no longer invoked in core agent flow
3. No new mypy errors; ruff passes
4. Existing tests pass (if any touch these paths)

## Readiness (DoR)

- [x] Current call sites for token counting identified
- [x] Pydantic-ai usage fields verified

## Milestones

- **M1:** Define new canonical token source for UI (usage totals)
- **M2:** Remove core flow calls to `update_token_count()`
- **M3:** Wire UI resource bar to usage totals
- **M4:** Validate persisted session compatibility

## Work Breakdown (Tasks)

| Task | ID | Summary | File(s) | Acceptance Tests |
|------|-----|---------|---------|------------------|
| T1 | tk-new | Add helper to derive total usage tokens (input+output) from session usage totals | `core/agents/agent_components/orchestrator/usage_tracker.py`, `types/canonical.py` | Existing tests pass |
| T2 | tk-new | Replace resource bar token source with usage totals | `ui/app.py`, `ui/widgets/resource_bar.py` | Manual run: resource bar updates post-request |
| T3 | tk-new | Remove per-message token count updates from agent flow | `core/agents/main.py`, `core/state.py` | Existing tests pass |
| T4 | tk-new | Update session persistence defaults/migrations if needed | `core/state.py`, `core/types/state_structures.py` | Load old session works |

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| Usage totals differ from context window size | Medium | High | Document change in behavior and UI meaning | Token display confusion |
| Missing usage for some providers (usage == 0) | Medium | Medium | Decide whether to surface explicit warning vs. accept zero totals | Zero usage observed |
| Cached token counts unavailable from RequestUsage | Low | High | Map cache_read/write to cached tokens or keep cached=0 | Cached token reporting needed |
| Legacy sessions lack totals | Medium | Medium | Default to zero and accumulate forward | Session load errors |

## Test Strategy

- `uv run pytest` (full suite)
- Manual: run a request, confirm resource bar tokens increase by usage totals

## References

- `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py` (where usage is read)
- `src/tunacode/core/agents/agent_components/orchestrator/usage_tracker.py` (usage accumulation)
- `src/tunacode/ui/app.py` (resource bar update)
- `pydantic_ai.messages.ModelResponse.usage` and `pydantic_ai.usage.RequestUsage`

## Tickets Created (max 5)

| Ticket ID | Title | Priority | Status |
|-----------|-------|----------|--------|
| pending | Not created yet | - | - |

## Dependencies

- T2 depends on T1 (helper available for UI consumption)
- T3 depends on M1 decision on canonical token source
