---
title: "Global Request Timeout – Implementation Plan"
phase: Plan
date: "2025-11-20T23:50:00Z"
owner: "context-engineer:plan"
parent_research: "memory-bank/research/2025-11-20_23-45-24_global-request-timeout-architecture.md"
git_commit_at_plan: "b41dd79"
tags: [plan, global-request-timeout, agent-orchestration, minimal-code]
---

## Goal

Add a **global request timeout** (default 90s, configurable via tunacode.json) to prevent agent hanging indefinitely when model API is slow/unresponsive. Implementation MUST use minimal code changes following existing patterns.

## Scope & Assumptions

### In Scope
- Configuration field: `settings.global_request_timeout` with 90.0s default
- Timeout enforcement: Wrap `RequestOrchestrator.run()` with `asyncio.wait_for()`
- Validation: Range check (>= 0.0, where 0.0 disables timeout)
- Exception: `GlobalRequestTimeoutError` with helpful message
- Documentation: Key description and version hash update

### Out of Scope
- Per-model timeout customization
- Streaming-specific timeout behavior changes
- Tool-specific timeout modifications
- User-facing documentation updates (README, examples)
- Integration tests (test structure requires separate planning)

### Assumptions
- Research findings accurate: No global timeout currently exists
- Configuration system architecture unchanged since research
- Default 90s timeout appropriate for all model providers
- Users can disable timeout by setting value to 0.0

## Deliverables (DoD)

1. **Configuration Default** (defaults.py)
   - ✅ Field `global_request_timeout: 90.0` added after `request_delay`
   - ✅ Validates as float >= 0.0

2. **Validation Function** (agent_config.py)
   - ✅ Function `_coerce_global_request_timeout()` follows `_coerce_request_delay()` pattern
   - ✅ Returns `None` if 0.0 (disabled), otherwise returns float

3. **Timeout Wrapper** (main.py)
   - ✅ `RequestOrchestrator.run()` refactored to call `_run_impl()`
   - ✅ `asyncio.wait_for()` wraps `_run_impl()` when timeout > 0.0
   - ✅ Catches `asyncio.TimeoutError` and raises `GlobalRequestTimeoutError`

4. **Exception Class** (exceptions.py)
   - ✅ `GlobalRequestTimeoutError` defined with timeout_seconds parameter
   - ✅ Message includes timeout value and actionable guidance

5. **Key Description** (key_descriptions.py)
   - ✅ Entry for `settings.global_request_timeout` with help text and example

6. **Version Hash Update** (agent_config.py)
   - ✅ `_compute_agent_version()` includes `global_request_timeout` in hash

## Readiness (DoR)

- ✅ Research document complete with file paths and line numbers
- ✅ No code drift detected in key files since research
- ✅ Pattern examples identified (request_delay, bash timeout)
- ✅ All target files exist and are accessible

## Milestones

**M1: Configuration Foundation** (1 task)
- Add default value and key description

**M2: Core Implementation** (2 tasks)
- Validation function and timeout wrapper

**M3: Exception Handling** (1 task)
- Exception class and error message

**M4: Cache Invalidation** (1 task)
- Version hash update

## Work Breakdown (Tasks)

### Task 1: Add Configuration Default & Description
**Owner**: Executor
**Dependencies**: None
**Target Milestone**: M1

**Acceptance Tests**:
- [ ] `defaults.py:22` contains `"global_request_timeout": 90.0` after `request_delay`
- [ ] `key_descriptions.py:~108` contains entry for `settings.global_request_timeout`
- [ ] Key description includes: example (90.0), help text about disabling (0.0), typical values (30-300s)

**Files/Interfaces**:
- `/root/tunacode/src/tunacode/configuration/defaults.py:22` (add field)
- `/root/tunacode/src/tunacode/configuration/key_descriptions.py:~108` (add description)

---

### Task 2: Implement Validation Function
**Owner**: Executor
**Dependencies**: Task 1
**Target Milestone**: M2

**Acceptance Tests**:
- [ ] Function `_coerce_global_request_timeout(state_manager)` exists in agent_config.py
- [ ] Returns `None` when timeout is 0.0
- [ ] Returns float when timeout > 0.0
- [ ] Raises `ValueError` when timeout < 0.0
- [ ] Follows same pattern as `_coerce_request_delay()` (lines 85-94)

**Files/Interfaces**:
- `/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py:~95` (add function after `_coerce_request_delay`)

---

### Task 3: Refactor RequestOrchestrator.run() with Timeout Wrapper
**Owner**: Executor
**Dependencies**: Task 2
**Target Milestone**: M2

**Acceptance Tests**:
- [ ] Original `run()` logic moved to new `_run_impl()` method
- [ ] `run()` calls `_coerce_global_request_timeout(self.state_manager)`
- [ ] When timeout is `None`, calls `_run_impl()` directly (no wrapper)
- [ ] When timeout is float, wraps `_run_impl()` with `asyncio.wait_for(timeout=...)`
- [ ] Catches `asyncio.TimeoutError` and raises `GlobalRequestTimeoutError`

**Files/Interfaces**:
- `/root/tunacode/src/tunacode/core/agents/main.py:364` (refactor run method)

---

### Task 4: Add GlobalRequestTimeoutError Exception
**Owner**: Executor
**Dependencies**: Task 3
**Target Milestone**: M3

**Acceptance Tests**:
- [ ] Class `GlobalRequestTimeoutError` exists in exceptions.py
- [ ] Constructor accepts `timeout_seconds: float` parameter
- [ ] Error message includes timeout value
- [ ] Error message suggests increasing timeout or checking model API status
- [ ] Follows pattern of `PatternSearchTimeoutError` (lines 223-228)

**Files/Interfaces**:
- `/root/tunacode/src/tunacode/exceptions.py:~228` (add exception after PatternSearchTimeoutError)

---

### Task 5: Update Agent Version Hash
**Owner**: Executor
**Dependencies**: Task 1
**Target Milestone**: M4

**Acceptance Tests**:
- [ ] `_compute_agent_version()` includes `settings.get("global_request_timeout", 90.0)` in hash tuple
- [ ] Hash invalidation ensures config changes trigger agent rebuild

**Files/Interfaces**:
- `/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py:97-108` (update hash computation)

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|-----------|------------|---------|
| **90s default too short for slow models** | High | Low | Document timeout as configurable; users can set to 120-300s | User reports timeout errors |
| **Timeout wrapper breaks streaming** | Critical | Very Low | Research shows timeout wraps entire request (correct); streaming handled by `_run_impl()` | Integration testing |
| **Config loading breaks with new field** | Critical | Very Low | Field has default; existing configs without field use default | Unit test config loading |
| **Exception not caught at REPL level** | Medium | Low | Research shows exception propagates to REPL; existing error handling applies | Manual REPL testing |

## Test Strategy

**Test Type**: ONE focused integration test

**Test File**: `tests/test_global_request_timeout.py` (new)

**Test Scenario**: Mock slow model API and verify timeout triggers
- Mock `agent.iter()` with `asyncio.sleep(100)` to simulate hang
- Set `global_request_timeout: 1.0` in test config
- Assert `GlobalRequestTimeoutError` raised with correct message
- Verify timeout value in error message matches config

**Why Only One Test**:
- Unit tests for validation function covered by existing config test patterns
- Timeout wrapper logic is thin (asyncio.wait_for is battle-tested)
- Focus test effort on end-to-end integration (timeout actually triggers)
- Pattern follows existing timeout tests (bash.py timeout tests)

## References

### Research Document
- `/root/tunacode/memory-bank/research/2025-11-20_23-45-24_global-request-timeout-architecture.md` (lines 221-339: implementation plan)

### Key Code Examples
- Request delay pattern: `/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py:85-94`
- Bash timeout wrapper: `/root/tunacode/src/tunacode/tools/bash.py:193`
- Exception pattern: `/root/tunacode/src/tunacode/exceptions.py:223-228`

### Related Plans
- `/root/tunacode/memory-bank/plan/2025-11-20_rate-limit-signaling-plan.md` (error signaling)
- `/root/tunacode/memory-bank/plan/2025-11-19_10-00-00_main_agent_error_handling_hardening.md` (error handling)

## Alternative Approach (For Reference)

**Alternative: Higher-Level Wrapper at process_request()**

Instead of wrapping `RequestOrchestrator.run()`, wrap the `process_request()` call at `main.py:583`. This would:
- Apply timeout to all request types (not just orchestrated runs)
- Be simpler (one wrapper location vs. refactoring run method)
- Potentially timeout non-orchestrated flows

**Why Not Chosen**:
- Research recommends `RequestOrchestrator.run()` (Option 1) as best enforcement point
- Granularity: Timeout should apply to agent iteration, not pre/post-processing
- Consistency: Tool timeouts exist at tool level; request timeout should exist at request level
- Minimal code: Refactoring `run()` to `_run_impl()` is ~10 lines

**When to Reconsider**:
- If timeout needs to cover non-orchestrated code paths
- If `process_request()` wrapper proves simpler in practice

## Final Gate

**Plan Summary**:
- **Plan Path**: `/root/tunacode/memory-bank/plan/2025-11-20_global-request-timeout-plan.md`
- **Milestones**: 4 (M1: Config, M2: Core, M3: Exception, M4: Cache)
- **Tasks**: 5 focused changes across 5 files
- **Gates**: DoD criteria for each deliverable; ONE integration test for end-to-end validation
- **Code Footprint**: ~60 lines added/modified (minimal)

**Next Command**:
```bash
/execute "memory-bank/plan/2025-11-20_global-request-timeout-plan.md"
```

**Execution Strategy**:
1. Implement tasks 1-5 sequentially (dependencies enforced by milestone order)
2. Run `ruff check --fix .` after all code changes
3. Create single integration test (test_global_request_timeout.py)
4. Verify test passes with timeout=1.0 and mocked slow API
5. Commit with message: "feat: add global request timeout (default 90s, configurable)"
