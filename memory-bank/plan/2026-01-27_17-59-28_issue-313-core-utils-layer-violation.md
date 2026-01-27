---
title: "Issue #313: Core → Utils Layer Violation – Plan"
phase: Plan
date: "2026-01-27T17:59:28Z"
owner: "Claude (planning agent)"
parent_research: "memory-bank/research/2026-01-27_11-53-37_issue-313-core-utils-layer-violation.md"
git_commit_at_plan: "b367bad8"
tags: [plan, architecture, layer-violation, refactor]
---

## Goal

**SINGULAR FOCUS:** Eliminate all 24 direct imports from `tunacode.utils` in `tunacode.core` by either:
1. Moving modules to foundation layers (`configuration/`, `types/`)
2. Inlining tiny utilities
3. Re-routing through Layer 2 (`tools/`)

**Non-goals:**
- Adding new functionality
- Changing behavior
- Refactoring beyond import paths
- Creating new abstractions

## Scope & Assumptions

**In scope:**
- 24 imports across 13 core files
- 8 utils modules that core imports from
- Moving/inlining code to comply with layer architecture

**Out of scope:**
- UI layer imports (separate issue)
- Tools layer lateral imports (#314)
- Test file imports

**Assumptions:**
- Foundation layers (`types/`, `configuration/`) can be imported by any layer
- Moving code preserves all existing behavior exactly
- No new tests needed (pure refactor, existing tests validate behavior)

## Deliverables (DoD)

| Deliverable | Acceptance Criteria |
|-------------|---------------------|
| Zero core→utils imports | `grep -r "from tunacode.utils" src/tunacode/core/ \| wc -l` returns 0 |
| All tests pass | `uv run pytest` exits 0 |
| Type checking passes | `uv run mypy src/tunacode/core/ --ignore-missing-imports` no new errors |
| Ruff passes | `uv run ruff check src/tunacode/` no errors |

## Readiness (DoR)

- [x] Research document complete with full import inventory
- [x] Current branch: `fix-layer-violation-core-utils-313`
- [x] Architecture diagram available: `docs/architecture/layers_html.html`
- [x] All 8 utils modules identified with fix strategies

## Milestones

- **M1:** Phase 1 - Inline tiny modules (formatting, DotDict) - 2 imports eliminated
- **M2:** Phase 2 - Move config modules to configuration/ - 9 imports eliminated
- **M3:** Phase 3 - Route messaging through tools/messaging/ - 10 imports eliminated
- **M4:** Phase 4 - Move parsing to tools/ and file_filter to infrastructure/ - 3 imports eliminated
- **M5:** Cleanup and verification - 0 core→utils imports remain

## Work Breakdown (Tasks)

### Task 1: Inline tiny utilities (M1)
**Summary:** Inline `utils/formatting.py` and `DotDict` directly into core files
**Files touched:**
- `src/tunacode/core/formatting.py` - inline `truncate_diagnostic_message` function
- `src/tunacode/core/agents/main.py` - inline `DotDict` class (14 lines)
- Delete: `src/tunacode/utils/formatting.py`
- Delete: `src/tunacode/utils/ui/helpers.py` (if only contains DotDict)

**Acceptance:**
- [ ] `core/formatting.py` contains function body, not import
- [ ] `core/agents/main.py` contains DotDict class
- [ ] utils files deleted
- [ ] Tests pass

### Task 2: Move config modules to configuration/ (M2)
**Summary:** Move `utils/config/`, `utils/limits.py`, `utils/system/paths.py`, `utils/system/ignore_patterns.py` to foundation
**Files touched:**
- Move: `utils/config/user_configuration.py` → `configuration/user_config.py`
- Move: `utils/limits.py` → `configuration/limits.py`
- Move: `utils/system/paths.py` → `configuration/paths.py`
- Move: `utils/system/ignore_patterns.py` → `configuration/ignore_patterns.py`
- Update 6 core files imports: `agent_config.py`, `user_configuration.py`, `state.py`, `system_paths.py`, `file_filter.py`, and any utils files that import these

**Acceptance:**
- [ ] All 4 modules exist in `configuration/`
- [ ] Core files import from `configuration/` not `utils/`
- [ ] Old utils locations deleted
- [ ] Tests pass

### Task 3: Route messaging through tools/messaging/ (M3)
**Summary:** Create `tools/messaging/` facade that re-exports from `utils/messaging/`. Core imports from Layer 2, respecting the architecture.
**Files touched:**
- Create: `src/tunacode/tools/messaging/__init__.py` (re-exports from utils.messaging)
- Update 6 core files: `sanitize_debug.py`, `summary.py`, `prune.py`, `sanitize.py`, `state.py`, `messaging.py`
- Keep: `utils/messaging/` stays where it is (Layer 3)

**Acceptance:**
- [ ] `tools/messaging/__init__.py` exists and re-exports messaging functions
- [ ] Core imports from `tools.messaging` not `utils.messaging`
- [ ] `utils/messaging/` remains in place (Layer 3)
- [ ] Tests pass

### Task 4: Move parsing to tools/ and file_filter to infrastructure/ (M4)
**Summary:** Move tool-specific parsing to Layer 2, file_filter to infrastructure
**Files touched:**
- Move: `utils/parsing/` → `tools/parsing/`
- Move: `utils/ui/file_filter.py` → `infrastructure/file_filter.py`
- Create: `src/tunacode/infrastructure/__init__.py`
- Update: `core/agents/.../tool_dispatcher.py`, `core/file_filter.py`

**Acceptance:**
- [ ] `tools/parsing/` exists with all parsing modules
- [ ] `infrastructure/file_filter.py` exists
- [ ] Core imports from `tools.parsing` and `infrastructure`
- [ ] Tests pass

### Task 5: Final cleanup and verification (M5)
**Summary:** Delete empty directories, verify zero violations
**Actions:**
- Delete empty `utils/` subdirectories
- Run verification: `grep -r "from tunacode.utils" src/tunacode/core/`
- Run full test suite
- Update `docs/architecture/DEPENDENCY_MAP.md` if needed

**Acceptance:**
- [ ] `grep -r "from tunacode.utils" src/tunacode/core/ | wc -l` returns 0
- [ ] All tests pass
- [ ] Ruff check passes
- [ ] DEPENDENCY_MAP.md reflects new structure

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| Circular imports after moves | High | Medium | Move in dependency order (leaf nodes first) | Import error on test run |
| Breaking tools layer that also imports utils | Medium | High | Check tools imports before each move | grep before delete |
| UI layer has direct utils imports | Medium | Medium | Out of scope - document for future | Note in PR |

## Test Strategy

**No new tests** - this is a pure refactor. Existing tests validate behavior preservation:
- `uv run pytest` - full suite
- `uv run ruff check` - linting
- `uv run mypy src/tunacode/core/ --ignore-missing-imports` - type checking

## References

- Research: `memory-bank/research/2026-01-27_11-53-37_issue-313-core-utils-layer-violation.md`
- Issue: https://github.com/alchemiststudiosDOTai/tunacode/issues/313
- Architecture: `docs/architecture/layers_html.html`
- Related: #311 (core→types, closed), #312 (core→configuration, closed)

---

## Tickets Created

| Ticket ID | Title | Priority | Status |
|-----------|-------|----------|--------|
| tun-b098 | Phase 1: Inline tiny utilities (formatting, DotDict) | P1 | open |
| tun-b9c8 | Phase 2: Move config modules to configuration/ | P1 | open |
| tun-8812 | Phase 3: Route messaging through tools/messaging/ facade | P1 | open |
| tun-a3d5 | Phase 4: Move parsing to tools/ and file_filter to infrastructure/ | P2 | open |
| tun-7246 | Phase 5: Final cleanup and verification | P2 | open |

## Dependencies

```
tun-b098 (Phase 1: Inline)
    ↓
tun-b9c8 (Phase 2: Config modules)
    ↓
tun-8812 (Phase 3: Messaging facade)
    ↓
tun-a3d5 (Phase 4: Parsing + file_filter)
    ↓
tun-7246 (Phase 5: Cleanup)
```

Sequential execution required - each phase depends on the previous completing successfully.
