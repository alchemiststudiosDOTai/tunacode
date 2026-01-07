---
title: "Tool Renderer Unification - Plan"
phase: Plan
date: "2026-01-07T16:30:00"
owner: "Claude"
parent_research: "memory-bank/research/2026-01-07_panel-architecture-map.md"
git_commit_at_plan: "e741b65"
tags: [plan, renderer, unification, coding]
---

## Goal

Unify 8 tool renderers under a single base class with decorator-based registration and shared zone builders, eliminating code duplication and manual routing.

**Non-goals:**
- Changing the visual output (panels must look identical after refactor)
- Adding new renderers or features
- Modifying the Textual widget layer
- Changing the message/callback flow

## Scope & Assumptions

**In scope:**
- Base renderer protocol/class with 4-zone structure
- Decorator-based auto-registration (`@tool_renderer("bash")`)
- Unified function signature enforcement
- Shared zone builder helpers (header, params, viewport, status)
- Refactoring all 8 existing renderers to use the base

**Out of scope:**
- Non-tool renderers (error, search, info panels)
- CSS/styling changes
- New renderer functionality

**Assumptions:**
- Rich library continues as rendering backend
- Existing 4-zone layout is the target pattern
- All renderers already have identical signatures: `(args, result, duration_ms) -> RenderableType | None`

## Deliverables

1. `src/tunacode/ui/renderers/tools/base.py` - Base class + protocol + registration decorator
2. `src/tunacode/ui/renderers/tools/zones.py` - Shared zone builder helpers
3. Refactored 8 renderer files using base class
4. Updated `src/tunacode/ui/renderers/tools/__init__.py` with auto-registration
5. Updated `src/tunacode/ui/renderers/panels.py` to use registry instead of manual map

## Readiness

**Preconditions:**
- All 8 renderers have identical signatures (verified)
- All renderers follow 4-zone pattern (verified)
- Constants already centralized in `src/tunacode/constants.py`

## Milestones

- **M1:** Base infrastructure (base.py + zones.py)
- **M2:** Registry + decorator working with one test renderer
- **M3:** Migrate all 8 renderers to base class
- **M4:** Integration with panels.py routing

## Work Breakdown (Tasks)

### M1: Base Infrastructure

| ID | Task | Owner | Est | Deps | Files |
|----|------|-------|-----|------|-------|
| T1 | Create `ToolRendererProtocol` with signature spec | Claude | S | - | `tools/base.py` |
| T2 | Create `BaseToolRenderer` abstract class with 4-zone template | Claude | M | T1 | `tools/base.py` |
| T3 | Create zone builders module | Claude | M | - | `tools/zones.py` |

**T1 Acceptance:** Protocol defines `__call__(args, result, duration_ms) -> RenderableType | None`

**T2 Acceptance:** Base class has abstract methods: `parse_result()`, `build_header()`, `build_params()`, `build_viewport()`, `build_status()` with default `render()` that composes zones.

**T3 Acceptance:** Zone helpers: `build_separator()`, `truncate_line()`, `truncate_output()`, `pad_to_min_height()`, `compose_4zone()`, `wrap_panel()`

### M2: Registry + Decorator

| ID | Task | Owner | Est | Deps | Files |
|----|------|-------|-----|------|-------|
| T4 | Implement `@tool_renderer("name")` decorator + registry dict | Claude | S | T1 | `tools/base.py` |
| T5 | Implement `get_renderer(name)` lookup function | Claude | S | T4 | `tools/base.py` |
| T6 | Convert `list_dir.py` as proof-of-concept | Claude | M | T2,T3,T4 | `tools/list_dir.py` |

**T4 Acceptance:** Decorator registers callable in `_RENDERER_REGISTRY` dict.

**T5 Acceptance:** Returns renderer or `None` for unknown tools.

**T6 Acceptance:** `list_dir.py` uses `BaseToolRenderer`, output unchanged.

### M3: Migrate All Renderers

| ID | Task | Owner | Est | Deps | Files |
|----|------|-------|-----|------|-------|
| T7 | Migrate `bash.py` | Claude | M | T6 | `tools/bash.py` |
| T8 | Migrate `read_file.py` | Claude | M | T6 | `tools/read_file.py` |
| T9 | Migrate `update_file.py` | Claude | M | T6 | `tools/update_file.py` |
| T10 | Migrate `glob.py` | Claude | M | T6 | `tools/glob.py` |
| T11 | Migrate `grep.py` | Claude | M | T6 | `tools/grep.py` |
| T12 | Migrate `web_fetch.py` | Claude | M | T6 | `tools/web_fetch.py` |
| T13 | Migrate `research.py` | Claude | M | T6 | `tools/research.py` |

**T7-T13 Acceptance:** Each renderer:
- Extends `BaseToolRenderer`
- Uses `@tool_renderer("name")` decorator
- Uses shared zone helpers
- Output visually identical to current

### M4: Integration

| ID | Task | Owner | Est | Deps | Files |
|----|------|-------|-----|------|-------|
| T14 | Update `__init__.py` with auto-registration on import | Claude | S | T7-T13 | `tools/__init__.py` |
| T15 | Replace `renderer_map` in `panels.py` with registry lookup | Claude | S | T14 | `renderers/panels.py` |
| T16 | Delete dead code (old renderer_map, duplicated helpers) | Claude | S | T15 | multiple |
| T17 | Run full test suite + manual visual verification | Claude | S | T16 | - |

**T14 Acceptance:** Importing `tools` package populates registry.

**T15 Acceptance:** `tool_panel_smart()` uses `get_renderer()` instead of hardcoded dict.

**T16 Acceptance:** No orphaned code, `ruff check` passes.

**T17 Acceptance:** `uv run pytest` passes, visual output unchanged.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Output regression (visual diff) | High | T17 includes manual visual comparison |
| Import cycle base <-> renderers | Medium | Keep base.py free of renderer imports |
| Performance (extra abstraction layer) | Low | Rich composition is the bottleneck, not Python calls |

## Test Strategy

- **T6:** Add one unit test for `list_dir` output structure after migration
- **T17:** Run existing test suite + manual panel rendering check

## References

- Research: `memory-bank/research/2026-01-07_panel-architecture-map.md`
- Current routing: `src/tunacode/ui/renderers/panels.py:513-522`
- Zone constants: `src/tunacode/constants.py:33-41`
- Existing renderers: `src/tunacode/ui/renderers/tools/*.py`

## Final Gate

| Metric | Value |
|--------|-------|
| Plan path | `memory-bank/plan/2026-01-07_16-30-00_renderer-unification.md` |
| Milestones | 4 |
| Tasks | 17 |
| Ready for coding | Yes |

**Next command:** `/context-engineer:execute "memory-bank/plan/2026-01-07_16-30-00_renderer-unification.md"`
