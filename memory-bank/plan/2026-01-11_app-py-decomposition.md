---
title: "app.py Decomposition – Plan"
phase: Plan
date: "2026-01-11"
owner: "user"
parent_research: null
git_branch: "ui/welcome-screen-spacing"
tags: [plan, refactor, cohesion, ui]
---

## Goal

**Decompose `src/tunacode/ui/app.py` (663 lines) into focused modules with clear single responsibilities.**

Current state: One large file mixing lifecycle, welcome/logo, request processing, streaming, shell, confirmations, and key handling.

Target state: Core app shell (~200 lines) delegating to specialized modules.

## Current Structure (Problem)

```
app.py (663 lines)
├── IMPORTS (1-76)
├── CONSTANTS (77-78)
└── TextualReplApp
    ├── Class Attrs (82-94)
    ├── LIFECYCLE (96-188) ─────────────── OK
    ├── STARTUP/WELCOME (190-312) ──────── MIXED (indexing + logo + welcome)
    ├── REQUEST PROCESSING (314-402) ───── OK
    ├── INPUT HANDLING (404-423) ───────── OK (small)
    ├── CONFIRMATION FLOWS (424-471) ───── MIXED (tool + plan + replay)
    ├── STREAMING (472-521) ────────────── OK
    ├── ACTIONS/CANCEL (523-549) ───────── OK
    ├── SHELL (551-561) ────────────────── OK (small, delegated)
    └── UI STATE (563-662) ─────────────── MIXED (resource bar + keys + confirmations)
```

## Target Structure

```
src/tunacode/ui/
├── app.py                  # Core shell: lifecycle, compose, routing (~250 lines)
├── welcome.py              # Logo generation + welcome message (~80 lines)
├── startup.py              # Index worker + startup tasks (~60 lines)
├── streaming.py            # Streaming state + callbacks (~80 lines)
├── confirmation_ui.py      # Inline confirmation rendering (~60 lines)
└── (existing files unchanged)
    ├── plan_approval.py
    ├── repl_support.py
    ├── shell_runner.ps
    └── ...
```

## Scope

### In Scope

| Extract         | From Lines | To File              | Functions/Methods                                                 |
| --------------- | ---------- | -------------------- | ----------------------------------------------------------------- |
| Welcome         | 232-312    | `welcome.py`         | `_generate_logo()`, `_show_welcome()`                             |
| Startup         | 190-230    | `startup.py`         | `_startup_index_worker()`                                         |
| Streaming       | 472-521    | `streaming.py`       | `streaming_callback()`, `_update_streaming_panel()`, pause/resume |
| Confirmation UI | 581-628    | `confirmation_ui.py` | `_show_inline_confirmation()`                                     |

### Out of Scope

- Request processing logic (already clean)
- Shell runner (already extracted)
- Plan approval (already extracted)
- Key handling (stays in app.py, just dispatches)

## Deliverables (DoD)

| Deliverable          | Acceptance Criteria                               |
| -------------------- | ------------------------------------------------- |
| `welcome.py`         | Contains logo + welcome, app.py imports and calls |
| `startup.py`         | Contains index worker, app.py imports and calls   |
| `streaming.py`       | Contains streaming logic, app.py delegates        |
| `confirmation_ui.py` | Contains inline confirmation render               |
| `app.py` reduced     | < 300 lines, no mixed-concern groups              |
| Tests pass           | `uv run pytest`                                   |
| Lint clean           | `uv run ruff check --fix .`                       |

## Milestones

| ID  | Milestone                  | Description                   |
| --- | -------------------------- | ----------------------------- |
| M1  | Extract welcome.py         | Logo + welcome message        |
| M2  | Extract startup.py         | Index worker                  |
| M3  | Extract streaming.py       | Streaming state/callbacks     |
| M4  | Extract confirmation_ui.py | Inline confirmation rendering |
| M5  | Validation                 | Tests, lint, smoke test       |

## Work Breakdown

### M1: welcome.py

| Task | Summary                            | Acceptance                 |
| ---- | ---------------------------------- | -------------------------- |
| T1.1 | Create `welcome.py` with imports   | File exists                |
| T1.2 | Move `_generate_logo()`            | Function works standalone  |
| T1.3 | Move `_show_welcome()`             | Function works standalone  |
| T1.4 | Update `app.py` to import and call | Welcome displays correctly |

### M2: startup.py

| Task | Summary                            | Acceptance                |
| ---- | ---------------------------------- | ------------------------- |
| T2.1 | Create `startup.py`                | File exists               |
| T2.2 | Move `_startup_index_worker()`     | Function works standalone |
| T2.3 | Update `app.py` to import and call | Indexing works on startup |

### M3: streaming.py

| Task | Summary                                             | Acceptance                                  |
| ---- | --------------------------------------------------- | ------------------------------------------- |
| T3.1 | Create `streaming.py` with `StreamingHandler` class | File exists                                 |
| T3.2 | Move streaming state vars                           | `_streaming_paused`, `_stream_buffer`, etc. |
| T3.3 | Move `streaming_callback()`                         | Callback works                              |
| T3.4 | Move `_update_streaming_panel()`                    | Panel updates                               |
| T3.5 | Move `pause_streaming()`, `resume_streaming()`      | Pause/resume works                          |
| T3.6 | Update `app.py` to use handler                      | Streaming unchanged                         |

### M4: confirmation_ui.py

| Task | Summary                            | Acceptance                      |
| ---- | ---------------------------------- | ------------------------------- |
| T4.1 | Create `confirmation_ui.py`        | File exists                     |
| T4.2 | Move `_show_inline_confirmation()` | Function works standalone       |
| T4.3 | Update `app.py` to import and call | Confirmation displays correctly |

### M5: Validation

| Task | Summary           | Acceptance                                 |
| ---- | ----------------- | ------------------------------------------ |
| T5.1 | Run tests         | `uv run pytest` passes                     |
| T5.2 | Run lint          | `uv run ruff check --fix .` passes         |
| T5.3 | Manual smoke test | TUI starts, welcome shows, streaming works |
| T5.4 | Line count check  | `app.py` < 300 lines                       |

## Design Decisions

### D1: Standalone functions vs. classes?

**Decision:** Standalone functions for welcome/startup, class for streaming.

**Rationale:**

- `_generate_logo()` and `_show_welcome()` are stateless - just need `rich_log` passed in
- `_startup_index_worker()` is stateless - just needs `rich_log` passed in
- Streaming has 5+ related state variables - warrants a `StreamingHandler` class

### D2: Where do streaming state vars live?

**Decision:** `StreamingHandler` instance owned by `TextualReplApp`.

```python
# app.py
self.streaming = StreamingHandler(self)

# Later
await self.streaming.handle_chunk(chunk)
self.streaming.pause()
```

### D3: How to pass dependencies?

**Decision:** Pass minimal dependencies explicitly.

```python
# welcome.py
def generate_logo() -> Text | None: ...
def show_welcome(rich_log: RichLog) -> None: ...

# startup.py
async def run_startup_index(rich_log: RichLog) -> None: ...
```

No app reference unless absolutely needed. Keeps modules testable.

## Risks

| Risk                      | Impact | Mitigation                                       |
| ------------------------- | ------ | ------------------------------------------------ |
| Circular imports          | High   | Keep new modules leaf-level, no app.py imports   |
| Streaming race conditions | Medium | Keep all state in StreamingHandler, single owner |
| Subtle behavior change    | Medium | Manual smoke test after each milestone           |

## Execution Order

1. M1 (welcome) - Lowest risk, most isolated
2. M2 (startup) - Also isolated
3. M4 (confirmation_ui) - Simple extraction
4. M3 (streaming) - Most complex, do last
5. M5 (validation) - Final gate

## References

- Current file: `src/tunacode/ui/app.py`
- Existing extractions: `plan_approval.py`, `shell_runner.py`, `repl_support.py`
