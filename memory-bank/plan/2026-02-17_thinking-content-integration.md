---
title: "Thinking Delta Integration - Junior-Executable Plan"
phase: Plan
date: "2026-02-17"
owner: "agent"
parent_research: "memory-bank/research/2026-02-17_thinking-content-integration.md"
git_commit_at_plan: "b249ef37"
tags: [plan, thinking-content, reasoning, tinyagent, tui]
---

## Goal

Integrate tinyagent `thinking_delta` stream events into TunaCode Textual UI so reasoning content can be shown in a dedicated muted panel when the user enables it.

## Final Decisions (No Open Questions)

1. **UI gate:** reasoning display is controlled by `session.show_thoughts` (default `False`).
2. **Command location:** `/thoughts` is implemented in `src/tunacode/ui/commands/` (not in `app.py` inline parser).
3. **Display behavior:**
   - During request: show reasoning in `#thinking-output` when enabled.
   - After request completes or is cancelled: clear/hide the thinking panel.
4. **Toggle behavior mid-stream:**
   - Toggle OFF: hide panel immediately, keep in-memory buffer for this request.
   - Toggle ON: render current in-memory buffer immediately.
5. **Scope boundary:** this iteration is **TUI display only**. We do **not** change session persistence schema or sanitize stored tinyagent message payloads.
6. **Final assistant panel content:** UI final response renderer must use **text-only assistant blocks** (ignore `thinking` blocks) to keep reasoning separate from final answer.

## Preconditions

1. **UI design rule compliance (mandatory):** read and apply `.claude/skills/neXTSTEP-ui/SKILL.md` before UI edits.
2. Verify tinyagent in environment exposes thinking stream events:

```bash
uv run python - <<'PY'
from tinyagent.agent_types import STREAM_UPDATE_EVENTS
required = {"thinking_start", "thinking_delta", "thinking_end"}
missing = required - set(STREAM_UPDATE_EVENTS)
if missing:
    raise SystemExit(f"Missing thinking stream events: {sorted(missing)}")
print("thinking stream events present")
PY
```

## Files To Change

1. `src/tunacode/core/agents/main.py`
2. `src/tunacode/ui/renderers/thinking.py` (new)
3. `src/tunacode/ui/app.py`
4. `src/tunacode/ui/styles/layout.tcss`
5. `src/tunacode/ui/commands/thoughts.py` (new)
6. `src/tunacode/ui/commands/__init__.py`
7. `tests/unit/core/test_thinking_stream_routing.py` (new)
8. `tests/unit/ui/test_thinking_renderer.py` (new)
9. `tests/unit/ui/test_app_latest_response_text.py` (new)

---

## Milestones

| ID | Milestone | Outcome |
|----|-----------|---------|
| M1 | Core stream routing | `thinking_delta` routed to callback independently of text callback |
| M2 | UI rendering + widget | Thinking panel exists, styled, throttled, bounded |
| M3 | Command wiring | `/thoughts` toggles behavior through command system |
| M4 | Validation | Unit tests + manual reasoning-model verification pass |

---

## Task Breakdown

### Task 1 (M1): Add thinking callback plumbing in core orchestrator

**File:** `src/tunacode/core/agents/main.py`

**Changes:**
1. In `RequestOrchestrator.__init__`, add parameter:
   - `thinking_callback: StreamingCallback | None = None`
2. Store it as `self.thinking_callback`.
3. In top-level `process_request(...)`, add same optional parameter and pass it into `RequestOrchestrator(...)`.

**Important:** use existing type alias `StreamingCallback` (there is no `StreamCallback` type).

**Acceptance:**
- `uv run ruff check src/tunacode/core/agents/main.py`

---

### Task 2 (M1): Route `thinking_delta` in `_handle_message_update`

**File:** `src/tunacode/core/agents/main.py`

**Current blindspot to remove:** method currently returns immediately when `streaming_callback` is `None`, which would also drop thinking events.

**Required logic:**

```python
assistant_event = getattr(event, "assistant_message_event", None)
if not isinstance(assistant_event, dict):
    return

ev_type = assistant_event.get("type")
delta = assistant_event.get("delta")
if not isinstance(delta, str) or not delta:
    return

if ev_type == "text_delta":
    if self.streaming_callback is None:
        return
    await self.streaming_callback(delta)
    self.state_manager.session._debug_raw_stream_accum += delta
    return

if ev_type == "thinking_delta":
    if self.thinking_callback is None:
        return
    await self.thinking_callback(delta)
    return
```

Unhandled event types should return cleanly.

**Acceptance:**
- Text and thinking routing behavior verified by new unit test file in Task 7.

---

### Task 3 (M2): Add dedicated thinking renderer (muted, truncated)

**File:** `src/tunacode/ui/renderers/thinking.py` (new)

**Implement:**
1. `DEFAULT_THINKING_MAX_LINES: int = 10`
2. `def render_thinking(content: str, max_lines: int = DEFAULT_THINKING_MAX_LINES) -> Text:`
3. Render last `max_lines` lines only.
4. Prepend muted truncation marker when clipping occurs.
5. Use `STYLE_MUTED` from `tunacode.ui.styles`.

**Do not** import from non-existent `tunacode.ui.renderers.constants`.

**Acceptance:**
- `uv run ruff check src/tunacode/ui/renderers/thinking.py`
- Unit tests in Task 8.

---

### Task 4 (M2): Wire thinking state + widget in Textual app

**Files:**
- `src/tunacode/ui/app.py`
- `src/tunacode/ui/styles/layout.tcss`

**App changes:**
1. Add `self.thinking_output: Static` and compose widget:
   - `self.thinking_output = Static("", id="thinking-output")`
   - yield it between `streaming_output` and `editor`.
2. Add state constants/fields (symbolic constants, no magic literals):
   - `THINKING_BUFFER_CHAR_LIMIT: int = 20000`
   - reuse `STREAM_THROTTLE_MS` for thinking updates (or define `THINKING_THROTTLE_MS` explicitly equal).
   - `_current_thinking_text: str = ""`
   - `_last_thinking_update: float = 0.0`
3. Add methods:
   - `_hide_thinking_output()`
   - `_clear_thinking_state()` (buffer + timer + hide)
   - `_refresh_thinking_output(force: bool = False)`
   - `async _thinking_callback(delta: str)`
4. `_thinking_callback` rules:
   - Append delta to buffer.
   - Enforce buffer cap by trimming oldest chars.
   - If `show_thoughts` is false: return after buffering.
   - Throttle updates to avoid UI churn.
5. In `_process_request(...)`:
   - call `_clear_thinking_state()` before request starts.
   - call `_clear_thinking_state()` in `finally`.
6. Pass callback to process request call:
   - `thinking_callback=self._thinking_callback`
7. Update `_get_latest_response_text()` to extract only assistant `text` blocks (ignore `thinking` blocks).

**Style changes (`layout.tcss`):**
Add `#thinking-output` style similar to `#streaming-output`, but muted look and hidden by default:
- `display: none`
- subdued outline/color
- `#thinking-output.active { display: block; }`

**Acceptance:**
- `uv run ruff check src/tunacode/ui/app.py`
- App starts without Textual CSS parse errors.

---

### Task 5 (M3): Add `/thoughts` command via command registry

**Files:**
- `src/tunacode/ui/commands/thoughts.py` (new)
- `src/tunacode/ui/commands/__init__.py`

**Implement command class:**
- `name = "thoughts"`
- `description = "Toggle reasoning/thinking panel"`
- Toggles `app.state_manager.session.show_thoughts`.
- If enabled: call `app._refresh_thinking_output(force=True)`.
- If disabled: call `app._hide_thinking_output()`.
- Notify user with enabled/disabled status.

**Important:** do not add `elif command == ...` in `app.py`.

**Acceptance:**
- `uv run pytest tests/unit/ui/test_command_contracts.py -q`

---

### Task 6 (M4): Manual verification flow

**Run:**
```bash
uv run tunacode
```

**Checklist:**
1. Select a reasoning-capable model.
2. Run `/thoughts` → notification says enabled.
3. Send prompt requiring reasoning.
4. Confirm muted thinking panel appears and streams.
5. Run `/thoughts` during streaming:
   - panel hides immediately.
6. Run `/thoughts` again before request ends:
   - panel reappears with buffered reasoning.
7. Request completes:
   - thinking panel clears/hides.
   - final assistant panel shows only final answer text (no reasoning text).

---

### Task 7 (M4): Add core routing unit tests

**File:** `tests/unit/core/test_thinking_stream_routing.py` (new)

**Cases:**
1. `text_delta` calls streaming callback and appends debug accumulator.
2. `thinking_delta` calls thinking callback even when streaming callback is `None`.
3. Non-delta / wrong types are ignored.

**Acceptance:**
- `uv run pytest tests/unit/core/test_thinking_stream_routing.py -q`

---

### Task 8 (M4): Add renderer unit tests

**File:** `tests/unit/ui/test_thinking_renderer.py` (new)

**Cases:**
1. Short input returns unchanged text.
2. Long input truncates to last N lines with hidden-lines marker.
3. Empty/whitespace input renders safely.

**Acceptance:**
- `uv run pytest tests/unit/ui/test_thinking_renderer.py -q`

---

### Task 9 (M4): Add response extraction test (text-only)

**File:** `tests/unit/ui/test_app_latest_response_text.py` (new)

**Case:** assistant content containing both `thinking` and `text` returns only text via `_get_latest_response_text()`.

**Acceptance:**
- `uv run pytest tests/unit/ui/test_app_latest_response_text.py -q`

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Thinking stream floods UI updates | UI lag | Shared throttling + bounded buffer + line truncation |
| Command added in wrong place | `/thoughts` unreachable | Enforce command-module implementation + contract test |
| Final response still includes reasoning | UX/security confusion | Explicit text-only extraction in `_get_latest_response_text()` + unit test |
| tinyagent event contract differs | Feature no-op | preflight event-contract check before coding |

## Verification Gates

Run in this order:

1. `uv run ruff check src/tunacode/core/agents/main.py src/tunacode/ui/app.py src/tunacode/ui/commands src/tunacode/ui/renderers/thinking.py`
2. `uv run pytest tests/unit/core/test_thinking_stream_routing.py tests/unit/ui/test_thinking_renderer.py tests/unit/ui/test_app_latest_response_text.py tests/unit/ui/test_command_contracts.py -q`
3. `uv run ruff check --fix .`
4. `uv run pytest`

## Handoff Output (for junior)

When complete, junior should provide:
1. PR with only files listed in **Files To Change**.
2. Paste outputs of all four **Verification Gates**.
3. 1 short GIF/screenshot set showing `/thoughts` on/off behavior during a live request.

## References

- Research: `memory-bank/research/2026-02-17_thinking-content-integration.md`
- Stream routing: `src/tunacode/core/agents/main.py`
- Command registry: `src/tunacode/ui/commands/__init__.py`
- UI app: `src/tunacode/ui/app.py`
- Layout styles: `src/tunacode/ui/styles/layout.tcss`

## Final Gate

Plan is now explicit enough for junior execution without additional clarification.

**Next command:**
```bash
/context-engineer:execute "memory-bank/plan/2026-02-17_thinking-content-integration.md"
```
