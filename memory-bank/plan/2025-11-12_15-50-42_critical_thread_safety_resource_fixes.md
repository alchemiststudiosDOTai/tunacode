---
title: "Critical Thread Safety & Resource Leak Fixes – Plan"
phase: Plan
date: "2025-11-12_15-50-42"
owner: "Claude Planning Agent"
parent_research: "memory-bank/research/2025-11-12_15-48-04_ai_agent_system_mapping.md"
git_commit_at_plan: "d6b564e"
tags: [plan, thread-safety, resource-management, critical-fixes]
---

## Goal

**SINGULAR FOCUS:** Eliminate critical thread safety violations and resource leaks in the agent state machine that are causing race conditions, data corruption, and memory leaks.

**Success Criteria:** Thread-safe state transitions with zero race conditions, guaranteed resource cleanup in all code paths, validated by comprehensive testing.

**Non-Goals:**
- Performance optimization (beyond fixing the critical issues)
- Import surface regression fixes (separate effort)
- Silent error masking improvements (separate effort)
- New feature development

## Scope & Assumptions

### In Scope
1. **Thread Safety**: Complete synchronization of state machine in `state_transition.py`
2. **Resource Cleanup**: Proper context managers and cleanup in `node_processor.py` error paths
3. **Validation**: One comprehensive golden baseline test to validate fixes
4. **Documentation**: Update .claude KB with fix patterns

### Out of Scope
- Import surface regression (high severity, but separate concern)
- Performance bottleneck optimization
- State mutation consistency across entire codebase
- Message format standardization

### Assumptions
1. Current test suite passes (277 tests passing, 12 skipped)
2. `.venv` and `uv` package management is configured
3. Thread safety issues are isolated to state machine component
4. Resource leaks are primarily in node processor error paths

### Constraints
- Must maintain backward compatibility
- Zero breaking changes to public APIs
- All existing 277 tests must continue passing
- Follow TDD: Red → Green → Blue workflow

## Deliverables (DoD)

1. **Thread-Safe State Machine**
   - All state transitions protected by proper locking
   - Zero race conditions (validated by stress testing)
   - Lock usage patterns consistent and correct
   - Acceptance: Concurrent state transition test passes 1000x iterations

2. **Resource Cleanup**
   - Context managers for all resource acquisitions
   - Cleanup in error paths (try/finally blocks)
   - No leaked file handles, memory, or connections
   - Acceptance: Resource leak test shows zero leaks after error scenarios

3. **Golden Baseline Test** (ONE TEST MAXIMUM)
   - Comprehensive test validating thread safety and resource cleanup
   - Tests concurrent state transitions under load
   - Tests error path resource cleanup
   - Acceptance: Test passes consistently (100 runs)

4. **Knowledge Base Updates**
   - Update `.claude/debug_history/` with fix session
   - Update `.claude/patterns/` with thread-safe state machine pattern
   - Run `claude-kb add` for each fix with error→solution context
   - Run `claude-kb sync --verbose` and `claude-kb validate`

## Readiness (DoR)

### Prerequisites
- [x] Research document complete and validated
- [x] Current codebase state captured (commit: d6b564e)
- [x] Test environment ready (`hatch run test` works)
- [ ] Code review of `state_transition.py` to identify all lock issues
- [ ] Code review of `node_processor.py` to identify all resource leak points

### Required Access
- Write access to `src/tunacode/core/agents/agent_components/`
- Write access to `tests/`
- Write access to `.claude/`

### Data/Fixtures
- Existing test fixtures in `tests/` can be reused
- May need new fixture for concurrent state transitions

## Milestones

### M1: Architecture Analysis & Lock Strategy (Day 1)
**Goal:** Understand current threading model and design comprehensive lock strategy

**Deliverables:**
- Complete code review of `state_transition.py` identifying all race conditions
- Thread safety design document with lock ordering and deadlock prevention
- Decision on lock granularity (coarse vs fine-grained)

**Gates:**
- Lock strategy reviewed and approved
- No potential deadlock scenarios identified
- Clear lock acquisition order established

### M2: Thread Safety Implementation (Day 2-3)
**Goal:** Implement thread-safe state machine with proper synchronization

**Deliverables:**
- Thread locks protecting all critical sections
- Atomic state transitions (no partial updates visible)
- Consistent lock usage patterns throughout state machine
- Code passes `ruff check --fix .`

**Gates:**
- All state mutations protected by locks
- Lock acquisition/release paired correctly
- No nested lock acquisitions (deadlock prevention)
- Static analysis passes

### M3: Resource Cleanup Implementation (Day 3-4)
**Goal:** Guarantee resource cleanup in all code paths

**Deliverables:**
- Context managers for resource acquisition in `node_processor.py`
- Try/finally blocks ensuring cleanup in error paths
- Explicit resource release in all exception handlers
- Code passes `ruff check --fix .`

**Gates:**
- All resource acquisitions wrapped in context managers
- All error paths have cleanup code
- No `except` blocks without cleanup
- Static analysis passes

### M4: Testing & Validation (Day 4-5)
**Goal:** Validate fixes with ONE comprehensive golden baseline test

**Deliverables:**
- ONE golden baseline test covering:
  - Concurrent state transitions (multi-threaded)
  - Resource cleanup in error scenarios
  - No race conditions under load
- Test passes consistently (100 iterations)
- All existing 277 tests still pass

**Gates:**
- Golden baseline test written and passing
- Existing test suite passes (277 tests)
- No regressions introduced
- Test run: `hatch run test` succeeds

### M5: Documentation & Knowledge Base (Day 5)
**Goal:** Document fixes and patterns for future reference

**Deliverables:**
- `.claude/debug_history/2025-11-12_thread_safety_resource_fixes.md`
- `.claude/patterns/thread_safe_state_machine.md`
- KB entries via `claude-kb add` for each fix
- `claude-kb sync --verbose` and `claude-kb validate` pass

**Gates:**
- All KB entries created and validated
- Pattern documentation complete and actionable
- Knowledge drift check passes
- Ready for commit

## Work Breakdown (Tasks)

### Task 1: State Machine Thread Safety Analysis
**Owner:** context-synthesis subagent
**Estimate:** 2 hours
**Dependencies:** None
**Milestone:** M1

**Description:** Deep analysis of `state_transition.py` to identify all race conditions and design lock strategy.

**Acceptance Tests:**
- All state mutation points identified
- All shared state access points catalogued
- Lock strategy document created with clear rationale
- No deadlock potential in proposed design

**Files/Interfaces:**
- Read: `src/tunacode/core/agents/agent_components/state_transition.py`
- Document: Lock strategy and race condition catalogue

### Task 2: Resource Leak Analysis
**Owner:** codebase-analyzer subagent
**Estimate:** 2 hours
**Dependencies:** None
**Milestone:** M1

**Description:** Analyze `node_processor.py` to identify all resource acquisition and error paths lacking cleanup.

**Acceptance Tests:**
- All resource acquisitions catalogued (files, connections, memory)
- All error paths analyzed for cleanup gaps
- Resource cleanup strategy document created
- Priority order for fixes established

**Files/Interfaces:**
- Read: `src/tunacode/core/agents/agent_components/node_processor.py`
- Document: Resource leak catalogue and cleanup strategy

### Task 3: Implement Thread-Safe State Transitions
**Owner:** Developer (Execution Phase)
**Estimate:** 4 hours
**Dependencies:** Task 1
**Milestone:** M2

**Description:** Add proper locking to state machine ensuring atomic transitions.

**Acceptance Tests:**
- All state mutations protected by `threading.Lock`
- Lock acquisition/release properly paired
- No nested lock acquisitions
- `ruff check --fix .` passes

**Files/Interfaces:**
- Edit: `src/tunacode/core/agents/agent_components/state_transition.py`
- Pattern: Use `with self._lock:` for all state mutations
- Ensure lock is instance variable: `self._lock = threading.Lock()`

### Task 4: Implement Resource Cleanup
**Owner:** Developer (Execution Phase)
**Estimate:** 4 hours
**Dependencies:** Task 2
**Milestone:** M3

**Description:** Add context managers and try/finally blocks for guaranteed cleanup.

**Acceptance Tests:**
- All resource acquisitions use context managers
- All error handlers include cleanup code
- No bare `except Exception:` without cleanup
- `ruff check --fix .` passes

**Files/Interfaces:**
- Edit: `src/tunacode/core/agents/agent_components/node_processor.py`
- Pattern: Use `with` statements for file/connection handling
- Pattern: Use `try/finally` for manual resource management

### Task 5: Create Golden Baseline Test
**Owner:** Developer (Execution Phase)
**Estimate:** 3 hours
**Dependencies:** Task 3, Task 4
**Milestone:** M4

**Description:** ONE comprehensive test validating thread safety and resource cleanup.

**Acceptance Tests:**
- Test spawns multiple threads performing concurrent state transitions
- Test validates no race conditions (consistent state)
- Test validates resource cleanup in error scenarios (no leaks)
- Test passes 100 consecutive iterations
- Test run time < 30 seconds

**Files/Interfaces:**
- Create: `tests/golden_baseline_thread_safety_resources.py`
- Uses: `threading`, `pytest`, resource monitoring utilities
- Validates: State consistency, no leaked resources

### Task 6: Validate Test Suite
**Owner:** Developer (Execution Phase)
**Estimate:** 1 hour
**Dependencies:** Task 3, Task 4, Task 5
**Milestone:** M4

**Description:** Run full test suite to ensure no regressions.

**Acceptance Tests:**
- All 277 existing tests still pass
- New golden baseline test passes
- Total test count: 278 (277 + 1)
- `hatch run test` succeeds with zero failures

**Files/Interfaces:**
- Run: `hatch run test`
- Verify: No test failures, no new skips

### Task 7: Update Knowledge Base
**Owner:** Developer (Execution Phase)
**Estimate:** 2 hours
**Dependencies:** Task 6
**Milestone:** M5

**Description:** Document fixes and patterns in .claude KB.

**Acceptance Tests:**
- Debug history entry created with error→solution pairs
- Pattern entry created with reusable thread-safe state machine pattern
- KB entries added via `claude-kb add` with proper component tagging
- `claude-kb sync --verbose` shows no drift
- `claude-kb validate` passes

**Files/Interfaces:**
- Create: `.claude/debug_history/2025-11-12_thread_safety_resource_fixes.md`
- Create: `.claude/patterns/thread_safe_state_machine.md`
- Run: `claude-kb add debug --component agent.state --summary "Thread safety fixes" --error "Race conditions in state transitions" --solution "Added threading.Lock for atomic state updates"`
- Run: `claude-kb add pattern --component agent.state --summary "Thread-safe state machine pattern"`
- Run: `claude-kb sync --verbose`
- Run: `claude-kb validate`

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| **Deadlock Introduction** | HIGH - System hangs | MEDIUM | Follow strict lock acquisition order, avoid nested locks, use lock timeout testing | Lock design review gate (M1) |
| **Performance Degradation** | MEDIUM - Slower state transitions | MEDIUM | Use fine-grained locks where possible, benchmark before/after | Performance testing in M4 |
| **Breaking API Changes** | HIGH - Downstream failures | LOW | Maintain all public interfaces, only modify internals | API compatibility check in M2 |
| **Test Flakiness** | MEDIUM - False positives | MEDIUM | Run tests 100x iterations, use deterministic thread coordination | Test validation in M4 |
| **Resource Leak in New Code** | HIGH - New leaks introduced | LOW | Code review all new context managers, validate with leak test | Resource testing in M3 |
| **Incomplete Error Path Coverage** | MEDIUM - Some leaks remain | MEDIUM | Systematic error path analysis in Task 2, comprehensive testing | Error path review in M1 |

## Test Strategy

### ONE Golden Baseline Test (Maximum Allowed)

**File:** `tests/golden_baseline_thread_safety_resources.py`

**Test Coverage:**

1. **Thread Safety Validation**
   - Spawn 10 threads performing concurrent state transitions
   - Each thread performs 100 state changes
   - Validate final state consistency (no corruption)
   - Validate no race conditions occurred

2. **Resource Cleanup Validation**
   - Trigger error scenarios in node processing
   - Validate all file handles closed (use `lsof` or resource tracking)
   - Validate all memory freed (check for reference cycles)
   - Run 10 error iterations, validate zero leaked resources

3. **Integration Validation**
   - Combine threading + error scenarios
   - Validate thread-safe error handling
   - Validate cleanup under concurrent error conditions

**Test Structure:**
```python
class TestThreadSafetyAndResources:
    def test_concurrent_state_transitions(self):
        """Validate thread-safe state machine under concurrent load."""
        # Spawn 10 threads, 100 transitions each
        # Assert consistent final state
        pass

    def test_resource_cleanup_on_errors(self):
        """Validate resource cleanup in error paths."""
        # Trigger errors, check for leaks
        # Assert zero leaked resources
        pass

    def test_concurrent_error_handling(self):
        """Validate thread-safe error handling with cleanup."""
        # Combine threading + errors
        # Assert thread safety + no leaks
        pass
```

### Existing Test Suite
- All 277 existing tests MUST continue passing
- Run full suite: `hatch run test`
- Zero tolerance for regressions

## References

### Research Documents
- [memory-bank/research/2025-11-12_15-48-04_ai_agent_system_mapping.md](memory-bank/research/2025-11-12_15-48-04_ai_agent_system_mapping.md) - Parent research
- Lines 79-89: Critical thread safety and resource leak issues

### Implementation Files
- [src/tunacode/core/agents/agent_components/state_transition.py](src/tunacode/core/agents/agent_components/state_transition.py:40-106) - State machine requiring thread safety fixes
- [src/tunacode/core/agents/agent_components/node_processor.py](src/tunacode/core/agents/agent_components/node_processor.py) - Node processor requiring resource cleanup

### Testing Files
- [tests/](tests/) - Existing test suite (277 tests)
- Will create: `tests/golden_baseline_thread_safety_resources.py` (1 new test)

### Documentation
- [documentation/agent/main-agent-architecture.md](documentation/agent/main-agent-architecture.md) - Architecture context
- [docs/reviews/main_agent_refactor_issues.md](docs/reviews/main_agent_refactor_issues.md) - Known issues

## Agents

This plan will deploy **3 subagents** (maximum allowed) in parallel during analysis phase:

1. **context-synthesis** - Deep analysis of thread safety issues in state machine
2. **codebase-analyzer** - Deep analysis of resource leaks in node processor
3. *(Reserve 1 slot for execution phase if needed)*

## Alternative Approach

**If thread safety fixes prove too risky or complex:**

**Alternative: Single-Threaded State Machine with Queue**
- Replace multi-threaded state access with single-threaded event queue
- All state mutations serialized through queue
- Eliminates race conditions by design (no locks needed)
- Trade-off: Slightly higher latency, but guaranteed safety

**Decision Point:** M1 gate - if lock strategy reveals high deadlock risk or complexity, pivot to queue-based approach.

## Final Gate

### Plan Summary
- **Plan File:** `memory-bank/plan/2025-11-12_15-50-42_critical_thread_safety_resource_fixes.md`
- **Milestones:** 5 (M1: Analysis, M2: Thread Safety, M3: Resource Cleanup, M4: Testing, M5: Documentation)
- **Tasks:** 7 (2 analysis, 3 implementation, 2 validation/documentation)
- **Gates:** 15 specific quality gates across all milestones
- **Critical Success Factor:** SINGULAR FOCUS on eliminating race conditions and resource leaks

### Next Command
Once this plan is approved, execute with:

```bash
/context-engineer:execute "memory-bank/plan/2025-11-12_15-50-42_critical_thread_safety_resource_fixes.md"
```

### Execution Guidance
- Follow TDD: Red (failing test) → Green (passing fix) → Blue (refactor)
- Run `ruff check --fix .` after each code change
- Commit frequently with focused diffs
- Update .claude KB after each fix (don't batch)
- Validate with `hatch run test` before moving to next task

---

**Ready for Execution:** This plan focuses exclusively on the two CRITICAL issues identified in research, uses exactly ONE new test, deploys maximum 3 subagents, and provides clear gates for quality validation. NO CODING in this plan - all implementation deferred to execution phase.
