---
title: "API Key UX Improvement - Junior-Executable Plan"
phase: Plan
date: "2026-02-19"
owner: "agent"
parent_research: "memory-bank/research/2026-02-19_api-key-ux-improvement.md"
git_commit_at_plan: "b8264e16"
tags: [plan, api-key-ux, ui, junior-handoff]
---

## Goal

When a user selects a model without a configured provider API key, do **not** dead-end. Instead, open an inline API key entry modal, let the user save the key, and immediately continue model switching.

## Final Decisions (No Open Questions)

1. **Config source policy:** keep current behavior. API keys come from `session.user_config["env"]` persisted to `~/.config/tunacode.json`. We are **not** adding `os.environ` fallback in this task.
2. **Recovery UX scope:** no provider dashboard/signup URLs in this task.
3. **Picker failure behavior:** if key entry is cancelled, user returns to chat (not back into picker). This is acceptable for this iteration.
4. **Entry point:** inject key-entry flow only into `/model` picker callback path (`on_model_selected`).
5. **Error renderer:** map `AuthenticationError` in `ui/renderers/errors.py` with API-key-specific recovery hints.
6. **Secret handling:** key must never be logged, notified, or rendered after entry.
7. **UI styling:** reuse existing `#api-key-input` and `#error-label` styles in `modals.tcss`; no CSS file changes required.
8. **Implementation order:** complete quick wins first (config path + error renderer), then new screen, then wiring, then tests.

## Non-goals

- `os.environ` key support
- Provider dashboard links in model registry schema
- Compaction key UX (`MissingCompactionApiKeyError`)
- Any agent loop, CI, deployment, or observability changes

## Preconditions (Run Before Editing)

1. Read `.claude/skills/neXTSTEP-ui/SKILL.md` (required by project rule for UI work).
2. Confirm baseline behavior manually once:
   - Run `uv run tunacode`
   - Execute `/model`
   - Pick a provider/model with missing key
   - Observe current dead-end behavior (toast + no model switch)

## Files To Change

1. `src/tunacode/ui/commands/model.py`
2. `src/tunacode/ui/renderers/errors.py`
3. `src/tunacode/ui/screens/api_key_entry.py` (new)
4. `tests/unit/ui/test_api_key_entry.py` (new)
5. `tests/unit/ui/test_error_renderer_authentication.py` (new)

## Execution Plan (Sequential, Junior Safe)

---

### Step 1 - Always show config path on picker validation failure

**File:** `src/tunacode/ui/commands/model.py`
**Target symbol:** `on_model_selected` callback inside `ModelCommand.execute`

**Change:**
- In `_validate_provider_api_key_with_notification(...)` call inside `on_model_selected`, change `show_config_path=False` to `show_config_path=True`.

**Why first:**
- One-line low-risk improvement; immediate user guidance even before inline entry screen exists.

**Done when:**
- Selecting a model without key logs both missing env var and config file path in `rich_log`.

---

### Step 2 - Add AuthenticationError recovery mapping

**File:** `src/tunacode/ui/renderers/errors.py`
**Target symbols:** `ERROR_SEVERITY_MAP`, `DEFAULT_RECOVERY_COMMANDS`

**Changes:**
1. Add `"AuthenticationError": "error"` in `ERROR_SEVERITY_MAP`.
2. Add `"AuthenticationError"` entry in `DEFAULT_RECOVERY_COMMANDS` with explicit API-key recovery actions:
   - `/model  # Pick model and enter API key`
   - `tunacode --setup  # Re-run guided setup`
   - `cat ~/.config/tunacode.json  # Verify env key is present`

**Important:**
- Do not add broad generic auth messaging. Keep commands concrete and actionable.

**Done when:**
- `render_exception(AuthenticationError("bad key"))` yields severity `error` and includes API-key recovery commands.

---

### Step 3 - Create ApiKeyEntryScreen

**File:** `src/tunacode/ui/screens/api_key_entry.py` (new)

**Create class:**
- `class ApiKeyEntryScreen(Screen[bool | None])`

**Constructor contract:**
- Inputs:
  - `provider_id: str`
  - `state_manager: StateManager`
- Store both on `self`.

**UI composition (must include):**
1. Title static (clear context: user must configure key)
2. Static showing provider (`provider_id`) and required env var (`get_provider_env_var(provider_id)`)
3. `Input(password=True, id="api-key-input")`
4. `Static("", id="error-label")`
5. Save button (`id="save-button"`) and Cancel button (`id="cancel-button"`)

**Behavior:**
- Escape key cancels (`dismiss(None)`).
- Save action:
  1. Read and `strip()` input
  2. If empty: update `#error-label` with clear message and return
  3. Resolve env var with `get_provider_env_var(provider_id)`
  4. Update `state_manager.session.user_config["env"][env_var] = api_key`
  5. Persist with `save_config(state_manager)`
  6. `dismiss(True)`
- Cancel action: `dismiss(None)`

**Error path:**
- If `save_config` raises, catch exception and surface message in `#error-label`; do not dismiss.

**Security rules:**
- Never show key value in `notify`, log, or error text.

**Done when:**
- Screen mounts correctly, validates empty input, saves non-empty key, and dismisses with `True` or `None`.

---

### Step 4 - Wire ApiKeyEntryScreen into model picker flow

**File:** `src/tunacode/ui/commands/model.py`
**Target symbol:** nested `on_model_selected` callback in `ModelCommand.execute`

**Required refactor (keep scope local to callback):**
1. Extract current successful model-switch block into a local helper function inside `execute` (same closure), e.g. `apply_model_selection(full_model: str) -> None`.
2. In `on_model_selected(full_model)`:
   - Return immediately on `None` (unchanged)
   - Run `_validate_provider_api_key_with_notification(..., show_config_path=True)`
   - If validation passes: call `apply_model_selection(full_model)`
   - If validation fails:
     1. Derive `provider_id = full_model.split(":", 1)[0]`
     2. Push `ApiKeyEntryScreen(provider_id, state_manager)`
     3. In its dismiss callback:
        - If result is `True`, call `apply_model_selection(full_model)`
        - If result is `None`, no-op

**Do not change:**
- Direct `/model provider:model` flow behavior (except Step 1 parity already done)
- Agent cache invalidation order in successful switch path

**Done when:**
- Picker flow with missing key becomes:
  - provider -> model -> key screen -> save -> model switched + resource bar updated

---

### Step 5 - Add focused tests (new files)

#### 5A. Screen behavior test

**File:** `tests/unit/ui/test_api_key_entry.py` (new)

**Cases:**
1. Empty input + save shows inline validation error and does not dismiss.
2. Valid input + save writes key into `session.user_config["env"]` and dismisses `True`.
3. Cancel dismisses `None`.

**Notes for implementation:**
- Follow existing async Textual test style (`async with app.run_test(headless=True) as pilot:`).
- Use `TextualReplApp(state_manager=StateManager())` harness and push the screen.

#### 5B. Error renderer auth mapping test

**File:** `tests/unit/ui/test_error_renderer_authentication.py` (new)

**Cases:**
1. `render_exception(AuthenticationError("bad key"))` returns `PanelMeta` severity `error`.
2. Rendered panel includes at least one API-key recovery command (`/model` or `tunacode --setup`).

**Test helper:**
- Define a local test exception class:
  - `class AuthenticationError(Exception): pass`
- This avoids relying on provider SDK imports in unit tests.

**Done when:**
- Both new test files pass.

---

## Manual Verification Checklist (Required)

Run once after Step 4 and after tests:

1. `uv run tunacode`
2. `/model`
3. Select provider/model with missing key
4. Confirm inline API key screen appears
5. Press cancel:
   - No crash
   - Model remains unchanged
6. Re-open `/model`, select same model, enter valid key, save:
   - Model switches
   - Success notification appears (`Model: ...`)
7. Restart app, run `/model` and verify provider now validates without missing-key toast (key persisted)

## Commands To Run (Exact)

1. `uv run pytest tests/unit/ui/test_api_key_entry.py -q`
2. `uv run pytest tests/unit/ui/test_error_renderer_authentication.py -q`
3. `uv run ruff check src/tunacode/ui/commands/model.py src/tunacode/ui/renderers/errors.py src/tunacode/ui/screens/api_key_entry.py tests/unit/ui/test_api_key_entry.py tests/unit/ui/test_error_renderer_authentication.py`

## Risks and Guardrails

| Risk | Guardrail |
|------|-----------|
| Key screen callback runs after picker dismissal | Expected in Textual callback chain; treat cancel as no-op and return to chat |
| Secret leakage via logs | Never interpolate key value into messages; only log env var names |
| Save failure leaves user stuck | Keep user on key screen and show explicit error in `#error-label` |
| Regression in existing direct `/model provider:model` path | Do not modify that branch except existing validation helper call parity |

## Definition of Done

All are true:

1. Missing-key picker flow no longer dead-ends.
2. User can enter key inline and complete model switch without restarting app.
3. `AuthenticationError` renders with API-key-specific recovery commands.
4. New unit tests pass.
5. Ruff check passes on touched files.

## Handoff Note

This plan is ready for junior execution as written. No architectural decisions remain open for this scope.
