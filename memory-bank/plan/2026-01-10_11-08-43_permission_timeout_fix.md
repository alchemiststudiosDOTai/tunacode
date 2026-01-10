---
title: "Permission Timeout Fix – Plan"
phase: Plan
date: "2026-01-10T11:08:43"
owner: "context-engineer"
parent_research: "memory-bank/research/2026-01-10_09-39-08_permission_timeout_issue.md"
git_commit_at_plan: "b827de5"
tags: [plan, timeout, permission, ui, coding]
---

## Goal

Fix the permission timeout issue where users are forced to respond within the global timeout period (90s default) when presented with tool confirmation prompts like "[1] Yes [2] Yes+Skip [3] No". Users should be able to wait indefinitely before responding.

**Non-goals:**
- Changing how permissions work otherwise
- Modifying the global timeout behavior for non-user-interaction scenarios
- Adding new configuration options for user interaction timeout

## Scope & Assumptions

### In Scope
- Modifying the global timeout handling to exclude time spent waiting for user input
- Ensuring `request_tool_confirmation()` is not subject to global timeout
- Ensuring `request_plan_approval()` is not subject to global timeout (same pattern)

### Out of Scope
- Observability/deployment considerations
- Comprehensive test coverage beyond basic validation
- Performance optimization

### Assumptions
- Python 3.11+ with standard asyncio library
- Existing `asyncio.wait_for()` pattern in `main.py` cannot be easily paused
- The cleanest solution is to shield user interaction futures from cancellation

## Deliverables

1. **Modified `src/tunacode/core/agents/main.py`** – Updated timeout handling that pauses during user interaction
2. **Modified `src/tunacode/ui/app.py`** – Added pause/resume signaling for user interaction
3. **New `src/tunacode/core/agents/timeout_state.py`** – Shared timeout state for coordination
4. **Updated `docs/codebase-map/modules/core-agents.md`** – Document timeout pause mechanism
5. **Updated `docs/codebase-map/modules/ui-overview.md`** – Document pause signaling in confirmation flow
6. **Updated `docs/codebase-map/modules/exceptions.md`** – Clarify GlobalRequestTimeoutError behavior

## Readiness

### Preconditions
- Git repo at commit `b827de5` or later
- Python 3.11+ with `uv` package manager
- Existing `src/tunacode/ui/app.py` with `request_tool_confirmation()` method
- Existing `src/tunacode/core/agents/main.py` with `run()` and `_run_impl()` methods

### Sample Input for Verification
```python
# Reproduce the issue:
# 1. Start tunacode
# 2. Trigger a write tool that requires confirmation
# 3. Wait >90 seconds before pressing 1/2/3
# 4. Should get GlobalRequestTimeoutError
```

## Milestones

| Milestone | Description |
|-----------|-------------|
| M1 | Create timeout pause mechanism (shared state + pause context) |
| M2 | Wire up pause signaling in UI layer (confirmation requests) |
| M3 | Integrate pause mechanism into agent timeout handling |
| M4 | Basic test + verification |
| M5 | Update documentation (core-agents, ui-overview, exceptions) |

## Work Breakdown (Tasks)

### T-001: Create Timeout Pause Mechanism
| Field | Value |
|-------|-------|
| **Summary** | Create shared timeout state object and pause context manager |
| **Owner** | Developer |
| **Estimate** | Medium |
| **Dependencies** | None |
| **Target Milestone** | M1 |
| **Files Touched** | `src/tunacode/core/agents/timeout_state.py` (new) |

**Implementation Details:**
- Create `TimeoutPauseState` class with `is_paused: bool` flag
- Create `timeout_paused()` context manager that sets/clears the flag
- Use `asyncio.Event` or threading primitive for thread-safe signaling if needed

**Acceptance Test:**
```python
# Test that pause state can be set and cleared
state = TimeoutPauseState()
assert not state.is_paused
async with state.timeout_paused():
    assert state.is_paused
assert not state.is_paused
```

---

### T-002: Add Pause State to Agent
| Field | Value |
|-------|-------|
| **Summary** | Add TimeoutPauseState instance to MainAgent class |
| **Owner** | Developer |
| **Estimate** | Small |
| **Dependencies** | T-001 |
| **Target Milestone** | M1 |
| **Files Touched** | `src/tunacode/core/agents/main.py` |

**Implementation Details:**
- Add `self._timeout_pause_state = TimeoutPauseState()` in `__init__`
- Expose via property for UI layer access
- Consider passing through StateManager if cleaner

**Acceptance Test:**
```python
# Test that agent has timeout pause state
agent = MainAgent(...)
assert agent.timeout_pause_state is not None
assert hasattr(agent.timeout_pause_state, 'is_paused')
```

---

### T-003: Wire Up Pause Signaling in UI
| Field | Value |
|-------|-------|
| **Summary** | Add pause/resume calls in request_tool_confirmation() and request_plan_approval() |
| **Owner** | Developer |
| **Estimate** | Medium |
| **Dependencies** | T-002 |
| **Target Milestone** | M2 |
| **Files Touched** | `src/tunacode/ui/app.py` |

**Implementation Details:**
- Get reference to `timeout_pause_state` from agent via `state_manager`
- Wrap `await future` with `async with timeout_pause_state.timeout_paused():`
- Do the same for `request_plan_approval()`

**Code Change Preview:**
```python
# In request_tool_confirmation():
async with timeout_pause_state.timeout_paused():
    return await future
```

**Acceptance Test:**
```python
# Test that timeout is paused during confirmation
# (Requires integration test or manual verification)
```

---

### T-004: Modify Agent Timeout Handling
| Field | Value |
|-------|-------|
| **Summary** | Update run() to respect pause state during timeout |
| **Owner** | Developer |
| **Estimate** | Medium |
| **Dependencies** | T-001, T-002 |
| **Target Milestone** | M3 |
| **Files Touched** | `src/tunacode/core/agents/main.py` |

**Implementation Details:**
- Create custom `wait_for_with_pause()` function
- When paused, use `asyncio.shield()` to protect inner future from cancellation
- Or: Loop with deadline extension while paused
- Replace `asyncio.wait_for()` with custom implementation

**Code Approach:**
```python
async def wait_for_with_pause(aw, timeout, pause_state):
    """Like asyncio.wait_for but pauses timeout when pause_state.is_paused."""
    if timeout is None:
        return await aw
    deadline = time.monotonic() + timeout
    while True:
        if pause_state.is_paused:
            # Extend deadline while paused, wait a bit
            deadline = time.monotonic() + timeout
            await asyncio.sleep(0.1)
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        try:
            return await asyncio.wait_for(aw, timeout=min(remaining, 1.0))
        except asyncio.TimeoutError:
            if not pause_state.is_paused:
                raise
            # Paused became true during wait, retry
```

**Acceptance Test:**
```python
# Test that timeout is extended during pause
pause_state = TimeoutPauseState()
async def slow_operation():
    await asyncio.sleep(0.1)
    async with pause_state.timeout_paused():
        await asyncio.sleep(0.5)  # Simulate user taking time
    await asyncio.sleep(0.1)
    return "done"

# Should succeed even though total > timeout if paused time is excluded
result = await wait_for_with_pause(slow_operation(), timeout=0.3, pause_state=pause_state)
assert result == "done"
```

---

### T-005: Add Plan Approval Pause Support
| Field | Value |
|--------------|
| **Summary** | Ensure request_plan_approval() also pauses timeout |
| **Owner** | Developer |
| **Estimate** | Small |
| **Dependencies** | T-003 |
| **Target Milestone** | M3 |
| **Files Touched** | `src/tunacode/ui/app.py` |

**Implementation Details:**
- Apply same pause pattern to `request_plan_approval()` if it uses a future
- Verify it follows the same async future pattern

**Acceptance Test:**
```python
# Manual verification: trigger plan approval and wait >90s
```

---

### T-006: Basic Integration Test
| Field | Value |
|-------|-------|
| **Summary** | Create basic test verifying timeout pause works end-to-end |
| **Owner** | Developer |
| **Estimate** | Small |
| **Dependencies** | T-004 |
| **Target Milestone** | M4 |
| **Files Touched** | `tests/test_timeout_pause.py` (new) |

**Implementation Details:**
- Create test that simulates user interaction exceeding global timeout
- Verify no GlobalRequestTimeoutError is raised
- Keep test minimal (unit test style, not full integration)

**Acceptance Test:**
```python
# Test in tests/test_timeout_pause.py
async def test_timeout_pause_during_user_confirmation():
    """Verify timeout doesn't expire while waiting for user input."""
    # This test will need to mock the UI components
    # or use a simplified version of the flow
```

---

### T-007: Update core-agents.md Documentation
| Field | Value |
|-------|-------|
| **Summary** | Document timeout pause mechanism and timeout_state.py module |
| **Owner** | Developer |
| **Estimate** | Small |
| **Dependencies** | T-001, T-002, T-004 |
| **Target Milestone** | M5 |
| **Files Touched** | `docs/codebase-map/modules/core-agents.md` |

**Implementation Details:**
- Add section on "Timeout Management" after "State Management"
- Document `TimeoutPauseState` class and its purpose
- Document `wait_for_with_pause()` function and how it extends deadlines
- Explain the pause/resume coordination between agent and UI layers
- Update the Message Flow diagram to show timeout pause interaction

**Content to Add:**
```markdown
### Timeout Management

#### timeout_state.py
- **TimeoutPauseState** - Shared state for coordinating timeout pauses during user interaction
- **timeout_paused()** - Context manager that sets/clears pause flag
- **wait_for_with_pause()** - Custom async wait that extends deadline while paused

**Pause Flow:**
```
Agent run() → wait_for_with_pause(_run_impl(), timeout=90)
  → Tool execution → request_tool_confirmation()
    → UI sets pause_state.is_paused = True
    → wait_for_with_pause() extends deadline
    → User responds → UI clears pause_state.is_paused
    → Normal timeout countdown resumes
```
```

**Acceptance Test:**
```python
# Documentation includes:
# - TimeoutPauseState class description
# - timeout_paused() context manager
# - wait_for_with_pause() function
# - Updated flow diagram
```

---

### T-008: Update ui-overview.md Documentation
| Field | Value |
|-------|-------|
| **Summary** | Document timeout pause signaling in tool confirmation flow |
| **Owner** | Developer |
| **Estimate** | Small |
| **Dependencies** | T-003, T-005 |
| **Target Milestone** | M5 |
| **Files Touched** | `docs/codebase-map/modules/ui-overview.md` |

**Implementation Details:**
- Update "Tool Confirmation Flow" section to show pause signaling
- Add note about `timeout_paused()` context manager usage
- Document how `request_tool_confirmation()` coordinates with agent timeout

**Content to Update:**
```markdown
### Tool Confirmation Flow
```
Tool call → request_tool_confirmation() → timeout_paused() context
  → _show_inline_confirmation()
  → User input (1/2/3) → on_key() → Authorization decision → Tool execution
  → timeout_paused() exit
```

**Timeout Coordination:**
- `request_tool_confirmation()` uses `async with timeout_pause_state.timeout_paused()`
- This signals the agent's `wait_for_with_pause()` to extend the deadline
- Users can wait indefinitely without triggering GlobalRequestTimeoutError
```

**Acceptance Test:**
```python
# Documentation includes:
# - Updated Tool Confirmation Flow with pause signaling
# - Note about timeout_paused() usage
# - Explanation of coordination with agent timeout
```

---

### T-009: Update exceptions.md Documentation
| Field | Value |
|-------|-------|
| **Summary** | Clarify GlobalRequestTimeoutError behavior regarding user interaction |
| **Owner** | Developer |
| **Estimate** | Small |
| **Dependencies** | T-004 |
| **Target Milestone** | M5 |
| **Files Touched** | `docs/codebase-map/modules/exceptions.md` |

**Implementation Details:**
- Update `GlobalRequestTimeoutError` description to note user interaction exclusion
- Clarify that timeout only applies to actual agent processing time
- Add note about the timeout pause mechanism

**Content to Update:**
```markdown
### GlobalRequestTimeoutError
Request timeout:
- Overall request exceeded timeout (excluding user interaction time)
- Agent iteration limit
- Unproductive limit reached

**Note:** Time spent waiting for user input (tool confirmations, plan approvals)
does NOT count toward the global timeout. The timeout clock pauses during
user interaction and resumes when the agent continues processing.
```

**Acceptance Test:**
```python
# Documentation includes:
# - Updated GlobalRequestTimeoutError description
# - Note about user interaction time exclusion
# - Reference to timeout pause mechanism
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `asyncio.shield()` may cause unintended timeout prevention | High | Carefully scope shield only to user interaction future, not entire agent run |
| Pause state not properly cleared (leaves timeout paused) | Medium | Use context manager pattern for guaranteed cleanup |
| Race condition between pause state and timeout check | Medium | Use proper async primitives (Event, Lock) |
| Solution doesn't work with current asyncio.wait_for pattern | Medium | Prototype the wait_for_with_pause function first |

## Test Strategy

- **T-001**: Unit test for TimeoutPauseState class
- **T-002**: Property check (agent has pause state)
- **T-003**: Manual verification only (UI layer)
- **T-004**: Unit test for wait_for_with_pause function
- **T-006**: Basic integration test
- **T-007**: Documentation verification (core-agents.md includes timeout section)
- **T-008**: Documentation verification (ui-overview.md includes pause flow)
- **T-009**: Documentation verification (exceptions.md includes timeout note)

## References

- Research: `memory-bank/research/2026-01-10_09-39-08_permission_timeout_issue.md`
- Permission UI: `src/tunacode/ui/app.py:511-586`
- Global timeout: `src/tunacode/core/agents/main.py:343-356`
- Confirmation request: `src/tunacode/ui/app.py:354-363`

## Final Gate

**Plan Summary:**
- Plan file: `memory-bank/plan/2026-01-10_11-08-43_permission_timeout_fix.md`
- Milestones: 5 (setup, UI wiring, agent integration, testing, documentation)
- Tasks: 9
- Approach: Create shared timeout pause state, wire up in UI layer, integrate into agent timeout handling with custom wait_for_with_pause function, update documentation

**Next Step:**
```bash
/execute "memory-bank/plan/2026-01-10_11-08-43_permission_timeout_fix.md"
```

**Ready for coding:** Yes
