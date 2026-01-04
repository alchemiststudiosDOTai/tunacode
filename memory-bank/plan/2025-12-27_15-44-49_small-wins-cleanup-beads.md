---
title: "Small Wins Cleanup - Beads Plan"
phase: Plan
date: "2025-12-27 15:44:49"
owner: "Claude Code"
parent_research: "reports/SMALL_WINS_AUDIT.md"
git_commit_at_plan: "496be38"
beads_count: 10
tags: [plan, beads, cleanup, dead-code, refactoring]
---

## Goal

Remove 19 small wins identified in the Small Wins Audit across 5 implementation batches, focusing on dead code elimination, type safety improvements, and code clarity enhancements.

## Scope & Assumptions

### In Scope
- Delete completely unused files and functions (dummy.py, key_descriptions.py)
- Remove unused methods from CodeIndex class
- Fix mypy implicit Optional type annotations
- Consolidate duplicate constants
- Clean up backward compatibility code
- Package structure improvements

### Out of Scope
- Large architectural refactors (e.g., splitting ui/commands/__init__.py monolith)
- Performance optimizations
- Feature additions
- Batch 5 items (deferred to future)

### Assumptions
- All deletions verified via grep for zero references
- Test suite passes after each batch
- No external API users affected by deletions
- Git bisect friendly commits

## Deliverables

- 10 atomic commits removing dead code and improving code quality
- Cleaner codebase with reduced maintenance burden
- Improved type safety with mypy fixes

## Readiness

### Preconditions
- Repository at commit 496be38 (clean state)
- Test suite available: `uv run pytest`
- Linter available: `ruff check`
- Type checker available: `mypy`

### Verification Tools
- `grep` for finding usage references
- `uv run pytest` for testing
- `ruff check` for linting
- `mypy` for type checking

## Beads Overview

| ID | Title | Priority | Estimate | Dependencies | Tags |
|----|-------|----------|----------|--------------|------|
| tunacode-ory | Delete dummy.py - completely unused file | P0 | 15 min | - | dead-code, cleanup |
| tunacode-on0 | Delete key_descriptions.py - orphaned module | P0 | 15 min | - | dead-code, cleanup |
| tunacode-7sk | Remove unused CodeIndex methods | P1 | 20 min | - | dead-code, cleanup |
| tunacode-yed | Delete legacy ripgrep() wrapper function | P1 | 10 min | - | dead-code, cleanup |
| tunacode-25x | Remove unused shutdown_all() from lsp module | P1 | 10 min | - | dead-code, cleanup |
| tunacode-4fd | Fix implicit Optional type annotations | P2 | 30 min | - | mypy, type-safety |
| tunacode-ps6 | Remove ReactTool backward compatibility class | P2 | 20 min | - | technical-debt, cleanup |
| tunacode-d3r | Consolidate truncation notice constants | P2 | 20 min | - | clarity, cleanup |
| tunacode-5cg | Add proper exports to configuration package | P3 | 15 min | - | api, cleanup |
| tunacode-oz8 | Remove or populate ui/components directory | P3 | 10 min | - | structure, cleanup |

## Dependency Graph

```
All beads are independent (no dependencies):
tunacode-ory (P0) ─┐
tunacode-on0 (P0) ─┤
tunacode-7sk (P1) ─┤
tunacode-yed (P1) ─┤
tunacode-25x (P1) ─┼─> Ready to execute immediately
tunacode-4fd (P2) ─┤
tunacode-ps6 (P2) ─┤
tunacode-d3r (P2) ─┤
tunacode-5cg (P3) ─┤
tunacode-oz8 (P3) ─┘
```

**No dependency cycles detected**

## Bead Details

### tunacode-ory: Delete dummy.py - completely unused file
**Priority:** P0
**Dependencies:** None
**Estimate:** 15 minutes
**Tags:** dead-code, cleanup

**Summary:**
Remove dummy.py from root directory. File contains Greeter class and hello() function with zero imports/references.

**Acceptance Criteria:**
- [ ] dummy.py deleted from repository root
- [ ] No imports found in codebase (verified via grep)
- [ ] Tests pass after deletion

**Files:**
- dummy.py

**Notes:**
Confidence: 100% - completely orphaned file with zero references.

---

### tunacode-on0: Delete key_descriptions.py - orphaned module
**Priority:** P0
**Dependencies:** None
**Estimate:** 15 minutes
**Tags:** dead-code, cleanup

**Summary:**
Remove configuration/key_descriptions.py (267 lines). Entire module unused with 6 orphaned exports.

**Acceptance Criteria:**
- [ ] configuration/key_descriptions.py deleted
- [ ] No imports found for any exports (get_key_description, get_service_type_for_api_key, get_categories, get_configuration_glossary, KeyDescription, CONFIG_KEY_DESCRIPTIONS)
- [ ] Tests pass after deletion

**Files:**
- src/tunacode/configuration/key_descriptions.py

**Notes:**
Risk: Low - may be planned for unimplemented help features. Confirm deletion before proceeding.

---

### tunacode-7sk: Remove unused CodeIndex methods
**Priority:** P1
**Dependencies:** None
**Estimate:** 20 minutes
**Tags:** dead-code, cleanup

**Summary:**
Delete three unused methods from indexing/code_index.py: lookup(), find_imports(), get_stats().

**Acceptance Criteria:**
- [ ] lookup() method removed (line 352)
- [ ] find_imports() method removed (line 430)
- [ ] get_stats() method removed (line 512)
- [ ] No callers found in codebase (verified via grep)
- [ ] Tests pass after removal

**Files:**
- src/tunacode/indexing/code_index.py

**Notes:**
Risk: Low - no callers found for any of the three methods.

---

### tunacode-yed: Delete legacy ripgrep() wrapper function
**Priority:** P1
**Dependencies:** None
**Estimate:** 10 minutes
**Tags:** dead-code, cleanup

**Summary:**
Remove ripgrep() backward compatibility wrapper from tools/utils/ripgrep.py (line 280).

**Acceptance Criteria:**
- [ ] ripgrep() wrapper function deleted
- [ ] No callers found in codebase
- [ ] Tests pass after removal

**Files:**
- src/tunacode/tools/utils/ripgrep.py

**Notes:**
Risk: None - confirmed zero callers.

---

### tunacode-25x: Remove unused shutdown_all() from lsp module
**Priority:** P1
**Dependencies:** None
**Estimate:** 10 minutes
**Tags:** dead-code, cleanup

**Summary:**
Delete shutdown_all() function from lsp/__init__.py (line 117). Exported but never called.

**Acceptance Criteria:**
- [ ] shutdown_all() function removed
- [ ] No callers found in codebase
- [ ] Module exports updated if needed
- [ ] Tests pass after removal

**Files:**
- src/tunacode/lsp/__init__.py

**Notes:**
Risk: None - unused cleanup code not integrated.

---

### tunacode-4fd: Fix implicit Optional type annotations
**Priority:** P2
**Dependencies:** None
**Estimate:** 30 minutes
**Tags:** mypy, type-safety

**Summary:**
Fix mypy implicit Optional issues in state_transition.py and message_handler.py by changing default type annotations to use explicit Optional syntax.

**Acceptance Criteria:**
- [ ] state_transition.py:97 - fix implicit Optional
- [ ] message_handler.py:44 - fix implicit Optional
- [ ] Run mypy to verify fixes
- [ ] No regressions in tests

**Files:**
- src/tunacode/core/agents/agent_components/state_transition.py
- src/tunacode/core/agents/agent_components/message_handler.py

**Notes:**
Part of Batch 2: Type Safety Improvements. Change `def foo(x: T = None)` to `def foo(x: T | None = None)`.

---

### tunacode-ps6: Remove ReactTool backward compatibility class
**Priority:** P2
**Dependencies:** None
**Estimate:** 20 minutes
**Tags:** technical-debt, cleanup

**Summary:**
Delete ReactTool backward compatibility class from tools/react.py (lines 90-112).

**Acceptance Criteria:**
- [ ] ReactTool class removed
- [ ] No external callers found (verify with grep)
- [ ] Tests pass after removal

**Files:**
- src/tunacode/tools/react.py

**Notes:**
Risk: Medium - may have external users. Confirm no external dependencies before deletion.

---

### tunacode-d3r: Consolidate truncation notice constants
**Priority:** P2
**Dependencies:** None
**Estimate:** 20 minutes
**Tags:** clarity, cleanup

**Summary:**
Merge duplicate truncation constants into single constant in constants.py.
- tools/authorization/requests.py:11 - TRUNCATION_NOTICE
- ui/repl_support.py:40 - CALLBACK_TRUNCATION_NOTICE

**Acceptance Criteria:**
- [ ] Single TRUNCATION_NOTICE constant in constants.py
- [ ] All references updated to use consolidated constant
- [ ] Old constants removed from source files
- [ ] Tests pass after consolidation

**Files:**
- src/tunacode/constants.py
- src/tunacode/tools/authorization/requests.py
- src/tunacode/ui/repl_support.py

**Notes:**
Risk: None - simple constant consolidation with grep verification.

---

### tunacode-5cg: Add proper exports to configuration package
**Priority:** P3
**Dependencies:** None
**Estimate:** 15 minutes
**Tags:** api, cleanup

**Summary:**
Define proper exports in configuration/__init__.py or remove file if unnecessary.

**Acceptance Criteria:**
- [ ] configuration/__init__.py has proper __all__ exports or is removed
- [ ] Public API clearly documented
- [ ] Imports from configuration package work correctly

**Files:**
- src/tunacode/configuration/__init__.py

**Notes:**
Current file only contains comment '# Config package' with no exports.

---

### tunacode-oz8: Remove or populate ui/components directory
**Priority:** P3
**Dependencies:** None
**Estimate:** 10 minutes
**Tags:** structure, cleanup

**Summary:**
Either remove empty ui/components/ directory or populate with components. Currently only contains __init__.py.

**Acceptance Criteria:**
- [ ] Directory removed OR populated with component files
- [ ] No broken imports
- [ ] Tests pass

**Files:**
- src/tunacode/ui/components/

**Notes:**
Previous audit removed 3 unused UI component files in commit #205. Directory is now empty placeholder.

---

## Risks & Mitigations

### Technical Risks
1. **Hidden dependencies:** Code may be dynamically imported or used in ways grep cannot detect
   - Mitigation: Run full test suite after each deletion
   - Rollback: Git revert available if tests fail

2. **External API users:** ReactTool may have external consumers
   - Mitigation: Search wider codebase and check git history for usage patterns
   - Rollback: Revert commit if external users discovered

3. **Type fixing regressions:** mypy fixes may introduce runtime issues
   - Mitigation: Run tests, verify mypy output before/after
   - Rollback: Git revert if issues found

### Risk Assessment
- **Overall Risk:** Low
- **Confidence:** High (95%+ for deletions verified via grep)
- **Reversibility:** High (all changes atomic and reversible)

## Test Strategy

### Per-Bead Testing
- Each bead includes verification step in acceptance criteria
- Run `uv run pytest` after each completion
- For type fixes: run `mypy` before and after

### Batch Testing
- Batch 1 (P0-P1): All deletion beads
  - Test: Full test suite passes
  - Verification: No broken imports

- Batch 2 (P2): Type safety and constant consolidation
  - Test: mypy shows improvement
  - Verification: No runtime regressions

- Batch 3 (P3): Package structure
  - Test: Imports work correctly
  - Verification: API documentation updated

## References

### Research Document
- `reports/SMALL_WINS_AUDIT.md` - Full audit report with 19 identified small wins
- Sections B1-B8: Dead code findings
- Section C2: Type safety issues
- Section D3: Duplicate constants

### Implementation Batches (from research)
- **Batch 1:** Critical Dead Code Removal (< 30 min, 4-5 files)
- **Batch 2:** Type Safety Improvements (< 45 min, 2-3 files)
- **Batch 3:** Structural Cleanup (< 1 hour, 3-4 files)
- **Batch 4:** Technical Debt (< 1 hour, 2-3 files)
- **Batch 5:** (Deferred) Module Restructuring

### Key Files
- `dummy.py` - Root directory orphan
- `src/tunacode/configuration/key_descriptions.py` - 267-line orphan
- `src/tunacode/indexing/code_index.py` - 3 unused methods
- `src/tunacode/tools/utils/ripgrep.py` - Legacy wrapper
- `src/tunacode/lsp/__init__.py` - Unused shutdown function

## Ready Queue

All 10 beads are ready to execute immediately (no dependencies or blockers):

```
1. [P0] tunacode-ory: Delete dummy.py - completely unused file (15 min)
2. [P0] tunacode-on0: Delete key_descriptions.py - orphaned module (15 min)
3. [P1] tunacode-7sk: Remove unused CodeIndex methods (20 min)
4. [P1] tunacode-yed: Delete legacy ripgrep() wrapper function (10 min)
5. [P1] tunacode-25x: Remove unused shutdown_all() from lsp module (10 min)
6. [P2] tunacode-4fd: Fix implicit Optional type annotations (30 min)
7. [P2] tunacode-ps6: Remove ReactTool backward compatibility class (20 min)
8. [P2] tunacode-d3r: Consolidate truncation notice constants (20 min)
9. [P3] tunacode-5cg: Add proper exports to configuration package (15 min)
10. [P3] tunacode-oz8: Remove or populate ui/components directory (10 min)
```

**Total Estimated Time:** ~2.75 hours

## Final Gate

- Plan path: `memory-bank/plan/2025-12-27_15-44-49_small-wins-cleanup-beads.md`
- Beads created: 10
- Ready for execution: 10
- Blocked: 0
- Dependency cycles: 0
- Next command: `/context-engineer:execute-beads`

---

**North Star Rule:** A developer running `bd ready` can pick up ANY of these 10 beads and start coding immediately with zero ambiguity. Each bead is atomic, has clear acceptance criteria, and can be completed in a single focused session.
