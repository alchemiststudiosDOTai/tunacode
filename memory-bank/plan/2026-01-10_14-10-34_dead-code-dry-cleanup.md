---
title: "Dead Code Removal & DRY Cleanup – Plan"
phase: Plan
date: "2026-01-10T14:10:34"
owner: "context-engineer"
parent_research: "memory-bank/research/2026-01-10_agent_config_map.md"
git_commit_at_plan: "d3d0654"
tags: [plan, dead-code, dry, refactor, tool-renderers]
---

## Goal

**Remove confirmed dead code from `agent_config.py` and create `BaseToolRenderer` to eliminate ~35% duplication across 8 tool renderer files.**

This is a focused cleanup to reduce maintenance burden and improve code quality. We will NOT address medium/low priority DRY violations in this iteration.

## Scope & Assumptions

### In Scope
1. Remove `_read_prompt_from_path()` function (lines 182-202) from `agent_config.py`
2. Remove unused `_PROMPT_CACHE` module-level variable (line 41)
3. Create `BaseToolRenderer` base class in `ui/renderers/tools/base.py`
4. Migrate ONE renderer (bash.py) to use BaseToolRenderer as proof-of-concept

### Out of Scope (Future Iterations)
- Migrating all 8 renderers to BaseToolRenderer (defer to follow-up PR)
- Medium-priority DRY fixes (model_picker.py, panels.py, commands/__init__.py)
- Low-priority DRY fixes (text_match.py, constants.py)
- Type definitions cleanup in types/__init__.py

### Assumptions
- `_TUNACODE_CACHE` remains in use by `load_tunacode_context()` and must NOT be removed
- `clear_all_caches()` function clears `_PROMPT_CACHE` but will continue working (no-op on empty dict)
- BaseToolRenderer design follows existing NeXTSTEP 4-zone layout pattern

## Deliverables (DoD)

| Deliverable | Acceptance Criteria |
|-------------|---------------------|
| Dead code removed | `_read_prompt_from_path` and `_PROMPT_CACHE` removed from agent_config.py |
| BaseToolRenderer class | Created in `ui/renderers/tools/base.py` with shared utilities |
| bash.py migration | bash.py refactored to extend BaseToolRenderer, rendering unchanged |
| Tests pass | `uv run pytest` passes with no regressions |
| Lint clean | `ruff check --fix .` passes |

## Readiness (DoR)

- [x] Research complete (2026-01-10_agent_config_map.md)
- [x] Dead code confirmed (grep shows zero call sites for `_read_prompt_from_path`)
- [x] Duplication analysis complete (35% duplication in renderers)
- [x] Git working tree clean on master branch
- [x] Test suite available (`uv run pytest`)

## Milestones

| ID | Milestone | Description |
|----|-----------|-------------|
| M1 | Dead Code Removal | Remove unused function and cache from agent_config.py |
| M2 | BaseToolRenderer | Create base class with shared utilities |
| M3 | Proof Migration | Migrate bash.py to BaseToolRenderer |
| M4 | Validation | Run tests and lint, verify no regressions |

## Work Breakdown (Tasks)

### M1: Dead Code Removal

| Task | Summary | Files | Acceptance |
|------|---------|-------|------------|
| T1.1 | Remove `_PROMPT_CACHE` declaration | `agent_config.py:41` | Line deleted |
| T1.2 | Remove `_read_prompt_from_path` function | `agent_config.py:182-202` | Function deleted (21 lines) |
| T1.3 | Update `clear_all_caches()` | `agent_config.py:167-172` | Remove `_PROMPT_CACHE.clear()` call |
| T1.4 | Run lint | - | `ruff check --fix .` passes |

### M2: BaseToolRenderer

| Task | Summary | Files | Acceptance |
|------|---------|-------|------------|
| T2.1 | Create base.py with imports | `ui/renderers/tools/base.py` | Standard imports consolidated |
| T2.2 | Add shared constants | `base.py` | BOX_HORIZONTAL, SEPARATOR_WIDTH defined |
| T2.3 | Add `truncate_line()` static method | `base.py` | Matches existing impl |
| T2.4 | Add `truncate_content()` static method | `base.py` | Returns (str, shown, total) |
| T2.5 | Add `create_separator()` static method | `base.py` | Returns Text with dim style |
| T2.6 | Add `pad_viewport()` static method | `base.py` | Pads to MIN_VIEWPORT_LINES |
| T2.7 | Add `BaseToolRenderer` ABC | `base.py` | Abstract methods for 4 zones |
| T2.8 | Add `render()` template method | `base.py` | Assembles zones into Panel |

### M3: Proof Migration (bash.py)

| Task | Summary | Files | Acceptance |
|------|---------|-------|------------|
| T3.1 | Import BaseToolRenderer | `bash.py` | Import from base.py |
| T3.2 | Create BashRenderer class | `bash.py` | Extends BaseToolRenderer |
| T3.3 | Implement zone builders | `bash.py` | build_header, build_params, build_viewport, build_status |
| T3.4 | Update render_bash to delegate | `bash.py` | Calls BashRenderer().render() |
| T3.5 | Visual regression check | - | Render output unchanged |

### M4: Validation

| Task | Summary | Acceptance |
|------|---------|------------|
| T4.1 | Run test suite | `uv run pytest` passes |
| T4.2 | Run lint | `ruff check --fix .` passes |
| T4.3 | Manual smoke test | TUI renders bash tool results correctly |

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| BaseToolRenderer breaks existing render behavior | High | Low | Proof with one renderer first, visual comparison | Render output differs |
| clear_all_caches() breaks tests | Medium | Low | Keep function, just remove dead cache clear | Test failures in cache-related tests |
| Import cycles from base.py | Medium | Low | Keep base.py deps minimal (only constants, rich) | ImportError on startup |

## Test Strategy

**ONE test to add:** `tests/test_base_renderer.py`

```python
def test_truncate_line_preserves_short_lines():
    """Verify truncate_line returns short lines unchanged."""
    from tunacode.ui.renderers.tools.base import BaseToolRenderer

    short = "hello world"
    assert BaseToolRenderer.truncate_line(short) == short

    long = "x" * 200
    result = BaseToolRenderer.truncate_line(long)
    assert len(result) <= MAX_PANEL_LINE_WIDTH
    assert result.endswith("...")
```

## References

- Research: `memory-bank/research/2026-01-10_agent_config_map.md`
- Dead code location: `src/tunacode/core/agents/agent_components/agent_config.py:182-202`
- Renderer files: `src/tunacode/ui/renderers/tools/{bash,glob,grep,list_dir,read_file,web_fetch,research,update_file}.py`
- SectionLoader (replacement): `src/tunacode/core/prompting/loader.py:8-67`

## Alternative Approach

**Option B: Shared Utilities Only (No Base Class)**

Instead of BaseToolRenderer ABC, create only a `utils.py` with static helpers:
- Pros: Simpler, no class hierarchy
- Cons: Each renderer still has ~100 lines of boilerplate for zone assembly

**Recommendation:** Option A (BaseToolRenderer) is preferred for larger duplication reduction (~35% vs ~15%).

---

## Final Gate

| Item | Value |
|------|-------|
| Plan Path | `memory-bank/plan/2026-01-10_14-10-34_dead-code-dry-cleanup.md` |
| Milestones | 4 |
| Tasks | 17 |
| Gates | Tests pass, Lint clean, Visual regression |
| Est. Lines Changed | ~250 (remove ~25, add ~150 base.py, modify ~75 bash.py) |

**Next Command:** `/context-engineer:execute "memory-bank/plan/2026-01-10_14-10-34_dead-code-dry-cleanup.md"`
