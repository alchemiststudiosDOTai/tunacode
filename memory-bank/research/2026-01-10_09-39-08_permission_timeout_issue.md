# Research – Permission Timeout Issue

**Date:** 2026-01-10
**Owner:** context-engineer
**Phase:** Research

## Goal

Map out the permission system and understand why the user experiences timeout errors when they take too long to select an option for write tool confirmations.

---

## Problem Statement

The user reports:
- Permission system shows "[1] Yes  [2] Yes + Skip  [3] No" for write tools
- If the user doesn't select within the global timeout period, it errors out
- Users should be able to wait however long before selecting

---

## Findings

### 1. Permission System – "[1] [2] [3]" Options

**Location:** `src/tunacode/ui/app.py:511-586`

The confirmation panel is rendered in `_show_inline_confirmation()`:

```python
actions.append("[1]", style=f"bold {STYLE_SUCCESS}")
actions.append(" Yes  ")
actions.append("[2]", style=f"bold {STYLE_WARNING}")
actions.append(" Yes + Skip  ")
actions.append("[3]", style=f"bold {STYLE_ERROR}")
actions.append(" No")
```

Key handling in `on_key()`:
```python
if event.key == "1":
    response = ToolConfirmationResponse(approved=True, skip_future=False, abort=False)
elif event.key == "2":
    response = ToolConfirmationResponse(approved=True, skip_future=True, abort=False)
elif event.key == "3":
    response = ToolConfirmationResponse(approved=False, skip_future=False, abort=True)
```

### 2. User Input Waiting – No Timeout (By Design)

**Location:** `src/tunacode/ui/app.py:354-363`

```python
async def request_tool_confirmation(
    self, request: ToolConfirmationRequest
) -> ToolConfirmationResponse:
    if self.pending_confirmation is not None and not self.pending_confirmation.future.done():
        raise RuntimeError("Previous confirmation still pending")

    future: asyncio.Future[ToolConfirmationResponse] = asyncio.Future()
    self.pending_confirmation = PendingConfirmationState(future=future, request=request)
    self._show_inline_confirmation(request)
    return await future  # NO TIMEOUT - waits indefinitely
```

**Key Finding:** The user input waiting itself has NO timeout. The `await future` waits indefinitely for user response.

### 3. Root Cause – Global Timeout Wraps Everything

**Location:** `src/tunacode/core/agents/main.py:343-356`

```python
async def run(self) -> AgentRun:
    """Run the main request processing loop with optional global timeout."""
    from tunacode.core.agents.agent_components.agent_config import (
        _coerce_global_request_timeout,
    )

    timeout = _coerce_global_request_timeout(self.state_manager)
    if timeout is None:
        return await self._run_impl()

    try:
        return await asyncio.wait_for(self._run_impl(), timeout=timeout)
    except TimeoutError as e:
        raise GlobalRequestTimeoutError(timeout) from e
```

**Location:** `src/tunacode/configuration/defaults.py:24`

```python
"global_request_timeout": 90.0,
```

**The Problem:**
- The entire agent request loop (`_run_impl()`) is wrapped with `asyncio.wait_for(timeout=90)`
- User input waiting happens **inside** this loop (during tool execution callbacks)
- If the user takes >90 seconds to respond, the **global timeout expires** and cancels everything
- Even though the user input future itself has no timeout, the **parent context has a timeout**

### 4. Error Type

**Location:** `src/tunacode/exceptions.py:268-278`

```python
class GlobalRequestTimeoutError(TunaCodeError):
    """Raised when a request exceeds the global timeout limit."""

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Request exceeded global timeout of {timeout_seconds}s. "
            f"The model API may be slow or unresponsive. "
            f"Try increasing settings.global_request_timeout in tunacode.json "
            f"or check model API status."
        )
```

### 5. Timeout Constants Summary

| Timeout | Default | Location | Notes |
|---------|---------|----------|-------|
| `global_request_timeout` | 90.0s | Config | Wraps entire agent run |
| User input waiting | **NO TIMEOUT** | `app.py:354-363` | Waits indefinitely (but inside global timeout) |

---

## Key Patterns / Solutions Found

### Pattern 1: Nested Timeout Context

The timeout architecture has two layers:
1. **Outer layer:** Global timeout (90s) wraps the entire agent request
2. **Inner layer:** User input waiting (no timeout)

The problem is that the outer timeout doesn't pause for user interaction. When the agent is waiting for user input, the global timeout clock keeps ticking.

### Pattern 2: Authorization Flow

```
ToolHandler.should_confirm()
  → AuthorizationPolicy.get_authorization()
    → Rules evaluated (PlanModeBlockRule, ReadOnlyToolRule, etc.)
  → If CONFIRM:
    → create_confirmation_request()
    → request_tool_confirmation()
    → _show_inline_confirmation()  // Shows "[1] Yes [2] Yes+Skip [3] No"
    → await future  // NO timeout here
    → on_key() handles 1/2/3
```

### Pattern 3: Timeout Cascade

```
asyncio.wait_for(_run_impl(), timeout=90)
  └─> Tool execution callback
      └─> request_tool_confirmation()
          └─> await future  // No timeout, but parent has 90s timeout
```

---

## Knowledge Gaps

1. **How to pause global timeout during user interaction** – Need to find a way to temporarily disable or extend the global timeout when waiting for user input

2. **Where in the flow to inject timeout pausing** – Need to identify the right place to pause/resume the global timeout

3. **Impact on other timeouts** – Need to understand how pausing global timeout affects other time-based operations

4. **Alternative approaches** – Could consider:
   - Moving user input outside the global timeout context
   - Adding a separate "user interaction timeout" configuration
   - Using a timeout-aware Future that can be reset during user interaction

---

## References

- Permission UI: `src/tunacode/ui/app.py:511-586` – Confirmation panel and key handling
- Request confirmation: `src/tunacode/ui/app.py:354-363` – No timeout on future
- Global timeout: `src/tunacode/core/agents/main.py:343-356` – Wraps entire agent run
- Global timeout config: `src/tunacode/configuration/defaults.py:24`
- Authorization policy: `src/tunacode/tools/authorization/policy.py` – Rules for confirmation
- Tool handler: `src/tunacode/tools/authorization/handler.py` – Coordinates authorization flow
- GitHub Permalink (main): https://github.com/alchemiststudiosDOTai/tunacode/blob/b827de5b2bb93202b13a48a3b6f396fd26af0721/src/tunacode/ui/app.py#L511-L586
