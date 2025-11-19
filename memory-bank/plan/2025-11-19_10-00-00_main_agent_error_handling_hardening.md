# Main Agent Error Handling Hardening – Plan

**Phase:** Plan
**Date:** 2025-11-19 10:00:00
**Owner:** claude
**Parent Research:** memory-bank/research/2025-11-19_09-45-17_main_agent_error_handling_analysis.md
**Git Commit at Plan:** 10ce081
**Tags:** [plan, error-handling, stability, cli-crash-prevention]

---

## Goal

**Singular Focus:** Eliminate CLI "blow-ups" by implementing error handling boundaries for the 4 critical gaps identified in research (MCP cleanup deferred to later iteration).

**Primary Outcome:** Zero unhandled exceptions reaching the CLI user interface during normal operation and graceful degradation under failure conditions.

**Non-Goals:**
- Refactoring existing recovery mechanisms (JSON parsing, tool execution)
- Adding new features beyond error handling
- Performance optimization
- Multi-agent error handling (scope limited to main agent)

---

## Scope & Assumptions

### In Scope
1. Background task error callbacks (main.py:64)
2. Exception handling in RequestOrchestrator (main.py:472-494)
3. Agent initialization error boundaries (agent_config.py:59-75)
4. State synchronization for concurrent tasks (repl.py:279)

### Out of Scope
- MCP server cleanup validation (main.py:102-107) - deferred to later iteration
- Existing error recovery mechanisms (error_recovery.py) - already functional
- Tool-level error handling (node_processor.py) - already comprehensive
- User abort flow modifications - working as designed
- Configuration error handling - already well-structured

### Assumptions
- Current exception hierarchy in `exceptions.py` is sufficient
- Existing logging infrastructure is adequate
- Test framework (hatch run test) is operational
- Git repository state is clean (only doc and research changes pending)

### Constraints
- No breaking API changes to public interfaces
- Must maintain backward compatibility
- Maximum of ONE new test (integration test for error boundaries)
- Changes must pass `ruff check --fix .`

**Drift Detected:** Changes to `node_processor.py` since research started - will verify changes don't conflict with error handling updates during M2.

---

## Deliverables (DoD)

1. **Background Task Error Handler**
   - Acceptance: All `asyncio.create_task()` calls have error callbacks
   - Verification: No "Task was destroyed but pending" warnings in logs

2. **Graceful Exception Flow**
   - Acceptance: RequestOrchestrator returns error states vs. re-raising
   - Verification: User sees friendly error messages, not tracebacks

3. **Agent Initialization Guard**
   - Acceptance: Missing system prompts trigger degraded mode, not crashes
   - Verification: Startup succeeds with warnings when optional files missing

4. **State Synchronization Lock**
   - Acceptance: Concurrent task access to session state is serialized
   - Verification: Race condition testing shows no data corruption

5. **Integration Test**
   - Acceptance: Single test covering all 4 error boundaries
   - Verification: Test fails before implementation, passes after

---

## Readiness (DoR)

### Preconditions
- [x] Research document complete and reviewed
- [x] Current git state captured (10ce081)
- [x] Test environment functional (`hatch run test` works)
- [x] Ruff linter configured

### Required Access
- [x] Write access to src/tunacode/core/agents/main.py
- [x] Write access to src/tunacode/cli/main.py
- [x] Write access to src/tunacode/cli/repl.py
- [x] Write access to tests/ directory

### Data/Fixtures
- Existing error recovery test patterns in tests/
- MCP server mock objects for cleanup testing
- Agent initialization failure scenarios

---

## Milestones

### M1: Architecture & Error Boundary Design
- Document error state return types for RequestOrchestrator
- Design background task error callback signature
- Define degraded mode behavior for agent initialization
- Create state lock abstraction for session management

### M2: Core Error Handling Implementation
- Implement background task error callbacks (main.py:64, repl.py:279)
- Refactor RequestOrchestrator exception flow (main.py:472-494)
- Add agent initialization error boundary (agent_config.py:59-75)

### M3: State Synchronization & Testing
- Implement session state locking mechanism
- Create integration test for all 4 error boundaries
- Verify test fails pre-implementation
- Validate test passes post-implementation

### M4: Hardening & Validation
- Run `ruff check --fix .` across all modified files
- Execute full test suite (`hatch run test`)
- Verify no drift with node_processor.py changes
- Manual smoke testing of CLI error scenarios

### M5: Documentation & Commit
- Update .claude/debug_history/ with error handling patterns
- Add .claude/patterns/ entry for error boundary pattern
- Run `claude-kb add pattern` for background task error handling
- Git commit with focused diff

---

## Work Breakdown (Tasks)

### Task 1: Background Task Error Callbacks
**Owner:** executor
**Estimate:** Small
**Dependencies:** None
**Milestone:** M2
**Files Touched:**
- src/tunacode/cli/main.py:64
- src/tunacode/cli/repl.py:279

**Acceptance Tests:**
- Background task exception is caught and logged
- Event loop continues running after task failure
- User sees warning message, not crash

### Task 2: RequestOrchestrator Error State Returns
**Owner:** executor
**Estimate:** Medium
**Dependencies:** Task 1 (design)
**Milestone:** M2
**Files Touched:**
- src/tunacode/core/agents/main.py:472-494
- src/tunacode/cli/repl.py (caller update)

**Acceptance Tests:**
- UserAbortError handled gracefully at orchestrator level
- ToolBatchingJSONError returns error state instead of raising
- Generic exceptions return error state with context

### Task 3: Agent Initialization Error Boundary
**Owner:** executor
**Estimate:** Small
**Dependencies:** None
**Milestone:** M2
**Files Touched:**
- src/tunacode/core/agents/agent_config.py:59-75
- src/tunacode/cli/main.py (startup flow)

**Acceptance Tests:**
- Missing system prompt triggers warning, not crash
- Agent starts in degraded mode with default prompts
- User notified of missing configuration

### Task 4: State Synchronization Lock
**Owner:** executor
**Estimate:** Medium
**Dependencies:** None
**Milestone:** M3
**Files Touched:**
- src/tunacode/cli/repl.py (session state access points)

**Acceptance Tests:**
- Concurrent warm_code_index() and process_request() don't collide
- Lock acquisition logged for debugging
- No deadlock under normal operation

### Task 5: Integration Test Creation
**Owner:** executor
**Estimate:** Medium
**Dependencies:** Tasks 1-4 (design phase)
**Milestone:** M3
**Files Touched:**
- tests/integration/test_error_boundaries.py (new file)

**Acceptance Tests:**
- Test covers all 4 error boundary scenarios
- Fails before implementation (TDD red phase)
- Passes after implementation (TDD green phase)

### Task 6: Validation & Commit
**Owner:** executor
**Estimate:** Small
**Dependencies:** Tasks 1-5
**Milestone:** M4-M5
**Files Touched:**
- All modified files
- .claude/debug_history/
- .claude/patterns/

**Acceptance Tests:**
- `ruff check --fix .` passes
- `hatch run test` passes
- Git diff is focused and reviewable

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| RequestOrchestrator API change breaks callers | High | Medium | Use context-synthesis agent to analyze all call sites first | Any caller expects exceptions instead of error states |
| State lock introduces deadlock | High | Low | Implement timeout-based lock acquisition with logging | Test run hangs during M3 |
| node_processor.py drift conflicts with changes | Medium | Medium | Review drift changes before M2, coordinate if needed | Git merge conflicts during implementation |
| Background task error callback adds overhead | Low | Low | Use lightweight logging, no heavy processing in callback | Performance regression in tests |
| Agent degraded mode breaks critical features | High | Low | Define minimal viable agent configuration in M1 | Integration test fails to start agent |

---

## Test Strategy

**Single Integration Test Approach:**

**File:** `tests/integration/test_error_boundaries.py`

**Test Scenarios (all in one test function):**
1. **Background Task Failure:** Create task that raises exception, verify logged and handled
2. **RequestOrchestrator Error State:** Trigger ToolBatchingJSONError, verify error state returned
3. **Agent Init Failure:** Mock missing system prompt, verify degraded mode activation
4. **State Race Condition:** Concurrent session state access, verify serialization

**TDD Flow:**
- Red: Test fails because error boundaries not implemented
- Green: Test passes after implementing all 4 boundaries
- Blue: Refactor for clarity and performance

**Existing Test Compatibility:**
- All existing tests in tests/ must continue passing
- No changes to existing test fixtures or mocks
- Error recovery tests (error_recovery.py) remain untouched

---

## References

### Research Document
- [Main Agent Error Handling Analysis](memory-bank/research/2025-11-19_09-45-17_main_agent_error_handling_analysis.md)

### Critical Code References
- Background task: [main.py:64](src/tunacode/cli/main.py#L64)
- Exception re-raise: [main.py:472-494](src/tunacode/core/agents/main.py#L472-L494)
- Agent init: [agent_config.py:59-75](src/tunacode/core/agents/agent_config.py#L59-L75)
- State race: [repl.py:279](src/tunacode/cli/repl.py#L279)

### Related Patterns
- Error recovery mechanisms: src/tunacode/cli/repl_components/error_recovery.py
- Exception hierarchy: src/tunacode/exceptions.py
- Tool error handling: src/tunacode/core/agents/agent_components/node_processor.py:479-496

---

## Agents

### Deployment Strategy (Maximum 3 Concurrent)

1. **context-synthesis** - Analyze RequestOrchestrator call sites to identify API change impact (Task 3 prerequisite)
2. **codebase-analyzer** - Review node_processor.py drift and verify no conflicts with error handling changes (M2 prerequisite)
3. **codebase-locator** - Find all asyncio.create_task() calls to ensure comprehensive coverage (Task 1 prerequisite)

**Agent Coordination:**
- All agents run in parallel during M1 (architecture phase)
- Results feed into M2 implementation decisions
- No coding during agent research phase

---

## Alternative Approach (Documented but NOT Pursued)

**Option B: Retry-Based Error Handling**
- Add automatic retry logic to RequestOrchestrator
- Implement exponential backoff for transient failures
- Circuit breaker pattern for persistent errors

**Why Not Chosen:**
- Adds complexity without addressing root causes
- Retry logic already exists at tool level
- User abort flow would be confusing with retries
- Scope creep beyond "blow-up" prevention

---

## Final Gate

**Plan Summary:**
- **Plan Path:** memory-bank/plan/2025-11-19_10-00-00_main_agent_error_handling_hardening.md
- **Milestones:** 5 (M1: Architecture → M2: Core Implementation → M3: Testing → M4: Validation → M5: Documentation)
- **Tasks:** 6 focused tasks targeting 4 critical error gaps
- **Gates:** TDD test (red→green), ruff validation, full test suite, KB update
- **Agent Support:** 3 concurrent research agents for M1 analysis

**Next Command:**
```bash
/context-engineer:execute "memory-bank/plan/2025-11-19_10-00-00_main_agent_error_handling_hardening.md"
```

**Implementation Focus:**
This plan addresses the singular goal of eliminating CLI crashes through surgical error boundary additions. Each task maps to one of the 4 critical gaps identified in research (MCP cleanup deferred). The integration test provides validation that all boundaries work together. No feature additions, no refactoring of working code—pure defensive hardening.
