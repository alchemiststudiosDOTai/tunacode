---
title: "Rich Panel to Textual CSS Migration -- Plan"
phase: Plan
date: "2026-02-07T12:24:34"
owner: "agent"
parent_research: "memory-bank/research/2026-02-07_12-19-02_rich-panel-to-textual-css-migration.md"
git_commit_at_plan: "1cf75e4a"
tags: [plan, ui, rich-panel, textual-css, copy-on-select, nextstep, migration]
---

## Goal

Replace all 12 Rich `Panel()` calls with native Textual CSS-styled `CopyOnSelectStatic` widgets so that text selection and copy-to-clipboard works correctly inside panel content. The fix: renderers return bare `Group(*parts)` content (no Panel wrapper), and `ChatContainer.write()` applies CSS classes for borders, padding, and colors.

**Non-goals:**
- Do NOT change the content rendering logic inside any renderer (Text, Syntax, Table, Markdown construction stays identical)
- Do NOT redesign the 4-zone panel layout
- Do NOT touch streaming infrastructure (currently disabled)
- Do NOT add new dependencies

## Scope & Assumptions

**In scope:**
- Remove `Panel()` wrapper from all 12 call sites
- Move title/subtitle into content as styled `Text` lines (Rich Panel `title` becomes first line of `Group`, `subtitle` becomes last line)
- Connect orphaned `.tool-panel`, `.error-panel`, `.search-panel` CSS classes to `CopyOnSelectStatic` widgets via `ChatContainer.write()`
- Adjust `panel_widths.py` to remove Panel border overhead from width calculations
- Define the missing `.expand` CSS class in TCSS
- Remove `from rich.panel import Panel` from all 5 files
- Clean up `Style` imports where they become unused

**Out of scope:**
- Streaming panel changes (streaming is currently disabled)
- New test coverage beyond a single smoke test
- Changes to NeXTSTEP theme (3D bevel CSS already exists)

**Assumptions:**
- Textual CSS borders do NOT break text selection (confirmed: CSS borders are rendered by the compositor, not as box-drawing characters in the text buffer)
- `CopyOnSelectStatic` inherits `border`, `padding`, `margin` CSS properties from its `Static` base
- The 4-zone layout is already constructed as `Group(header, context, viewport, footer)` -- only the outer `Panel()` wrapper is removed

## Deliverables (DoD)

1. All 12 `Panel()` calls removed -- renderers return `Group(*parts)` with title/subtitle inlined
2. `ChatContainer.write()` applies CSS class (`.tool-panel`, `.error-panel`, `.search-panel`, `.agent-panel`) and sets `border_title`/`border_subtitle` OR inlines them
3. CSS classes connected -- panels visually identical (border color, padding, background)
4. Copy-on-select works for all panel content (manual verification)
5. `ruff check --fix .` passes
6. No new type errors

## Readiness (DoR)

- Research complete: `memory-bank/research/2026-02-07_12-19-02_rich-panel-to-textual-css-migration.md`
- Git clean on master at `1cf75e4a`
- CSS infrastructure exists (`panels.tcss`, `theme-nextstep.tcss`)
- No blocking dependencies

## Milestones

- **M1: Foundation** -- Create shared `write_panel()` method on `ChatContainer` that applies CSS classes, border_title, border_subtitle. Define `.expand` and `.agent-panel` CSS classes.
- **M2: Tool panels** -- Migrate `BaseToolRenderer.render()` and `UpdateFileRenderer.render()` (2 sites, fixes 8 tool renderers)
- **M3: Panels module** -- Migrate all 7 `RichPanelRenderer` methods in `panels.py`
- **M4: Agent + Search** -- Migrate `agent_response.py` (2 sites) and `search.py` (1 site)
- **M5: Cleanup** -- Remove `Panel` imports, remove unused `Style` imports, adjust `panel_widths.py`, run ruff

## Work Breakdown (Tasks)

### Task 1: ChatContainer.write() panel support + CSS classes (M1)

**Summary:** Extend `ChatContainer.write()` to accept panel metadata (css_class, title, subtitle, border_color) and apply them as Textual widget properties. Add `.agent-panel` and `.expand` CSS class definitions to TCSS.

**Files:**
- `src/tunacode/ui/widgets/chat.py` -- add params to `write()`, apply CSS classes + `border_title`/`border_subtitle`
- `src/tunacode/ui/styles/panels.tcss` -- add `.agent-panel` class, add `.expand` class
- `src/tunacode/ui/styles/widgets.tcss` -- add `.chat-message` base styles if missing

**Acceptance:**
- `write(renderable, css_class="tool-panel", border_title="bash [done]", border_subtitle="14:30:05")` produces a widget with CSS border and title
- `.expand` class sets `width: 1fr`
- Existing `write()` calls without new params still work (backward compatible)

### Task 2: Migrate tool panel renderers (M2)

**Summary:** Change `BaseToolRenderer.render()` and `UpdateFileRenderer.render()` to return content `Group(*parts)` plus panel metadata dict instead of `Panel(...)`. Update callers to pass metadata through to `ChatContainer.write()`.

**Files:**
- `src/tunacode/ui/renderers/tools/base.py` -- return `(content, panel_meta)` tuple or a `PanelContent` dataclass
- `src/tunacode/ui/renderers/tools/update_file.py` -- same pattern
- `src/tunacode/ui/renderers/panels.py` -- update `tool_panel_smart()` to pass metadata through
- `src/tunacode/ui/app.py` -- update `on_tool_result_display()` to unpack metadata and pass to `write()`

**Acceptance:**
- All 8 tool renderers display with CSS borders
- Title shows tool name + status
- Subtitle shows timestamp
- Border color reflects tool state (success/error/warning)
- Copy-on-select works within tool panels

### Task 3: Migrate RichPanelRenderer methods (M3)

**Summary:** Change all 7 `RichPanelRenderer` methods to return content + metadata instead of `Panel(...)`. This covers: `render_tool()`, `render_diff_tool()`, `render_error()`, `render_search_results()`, `render_info()`, `render_success()`, `render_warning()`.

**Files:**
- `src/tunacode/ui/renderers/panels.py` -- all 7 methods
- `src/tunacode/ui/app.py` -- update callers to unpack metadata

**Acceptance:**
- Error panels use `.error-panel` CSS class
- Search panels use `.search-panel` CSS class
- Info/success/warning panels use appropriate CSS class variants
- Visual appearance matches current Rich Panel rendering

### Task 4: Migrate agent response + search renderers (M4)

**Summary:** Change `render_agent_streaming()`, `render_agent_response()`, and `SearchDisplayRenderer.render_empty_results()` to return content + metadata.

**Files:**
- `src/tunacode/ui/renderers/agent_response.py` -- both functions
- `src/tunacode/ui/renderers/search.py` -- `render_empty_results()`
- `src/tunacode/ui/app.py` -- update callers

**Acceptance:**
- Agent response panels use `.agent-panel` CSS class
- Streaming panel (when re-enabled) uses same CSS infrastructure
- Empty search results display correctly
- Copy-on-select works for agent markdown content

### Task 5: Cleanup + width adjustment (M5)

**Summary:** Remove all `from rich.panel import Panel` imports. Remove `Style` imports where no longer needed. Adjust `panel_widths.py` to remove Panel border overhead. Run `ruff check --fix .`.

**Files:**
- `src/tunacode/ui/renderers/panels.py` -- remove Panel import, clean Style
- `src/tunacode/ui/renderers/agent_response.py` -- remove Panel import, clean Style
- `src/tunacode/ui/renderers/search.py` -- remove Panel import, clean Style
- `src/tunacode/ui/renderers/tools/base.py` -- remove Panel import, clean Style
- `src/tunacode/ui/renderers/tools/update_file.py` -- remove Panel import, clean Style
- `src/tunacode/ui/renderers/panel_widths.py` -- adjust `TOOL_PANEL_HORIZONTAL_INSET`

**Acceptance:**
- `ruff check .` passes
- No `Panel` imports remain
- `grep -r "from rich.panel" src/` returns nothing
- Tool panel widths are correct (no extra border padding)

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| Textual CSS borders also break text selection | High | Low | Test early with a single panel (Task 1) before migrating all 12 | Copy-on-select fails with CSS borders |
| `border_title` not supported on `Static` subclass | Medium | Medium | Fall back to inlining title as first `Text` line in content | Widget shows no title |
| NeXTSTEP 3D bevel breaks with new CSS classes | Low | Low | Theme overrides already target `.tool-panel` class | Visual regression |
| Callers expect `Panel` return type | High | Medium | Define a `PanelContent` dataclass to carry content + metadata | Type errors at call sites |
| Width calculations produce wrong sizes | Medium | Medium | Task 5 adjusts TOOL_PANEL_HORIZONTAL_INSET; test with narrow terminal | Content truncation or overflow |

## Test Strategy

- One manual verification test: render each panel type, confirm visual appearance and copy-on-select
- `ruff check .` as automated gate
- No new unit tests in this migration (test coverage is a separate effort)

## References

- Research: `memory-bank/research/2026-02-07_12-19-02_rich-panel-to-textual-css-migration.md`
- Prior research: `memory-bank/research/2026-02-07_copy-on-select-panel-issue.md`
- Panel CSS: `src/tunacode/ui/styles/panels.tcss`
- NeXTSTEP theme: `src/tunacode/ui/styles/theme-nextstep.tcss`
- Panel widths: `src/tunacode/ui/renderers/panel_widths.py`
- ChatContainer: `src/tunacode/ui/widgets/chat.py`

## Tickets Created (5)

| Ticket ID | Title | Priority | Status | Milestone |
|-----------|-------|----------|--------|-----------|
| tun-d8b2 | ChatContainer.write() panel support + CSS classes | P1 | open | M1 |
| tun-f47b | Migrate tool panel renderers to CSS panels | P1 | open | M2 |
| tun-928a | Migrate RichPanelRenderer methods to CSS panels | P2 | open | M3 |
| tun-d020 | Migrate agent response + search renderers to CSS panels | P2 | open | M4 |
| tun-e497 | Cleanup: remove Panel imports + adjust panel_widths | P3 | open | M5 |

## Dependencies

```
tun-d8b2 (foundation)
  |
  +---> tun-f47b (tool panels)  --+
  +---> tun-928a (panel module) --+--> tun-e497 (cleanup)
  +---> tun-d020 (agent+search) --+
```

Tasks 2, 3, 4 can run in parallel after Task 1 completes. Task 5 runs last after all migrations finish.
