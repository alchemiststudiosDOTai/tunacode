---
title: "UI Dependency Violations – Plan"
phase: Plan
date: "2026-01-26_10-53-47"
owner: "Claude (context-engineer:plan)"
parent_research: "memory-bank/research/2026-01-26_ui-dependency-violations.md"
git_commit_at_plan: "9cbf3910"
tags: [plan, ui, dependency-direction, gate-2]
---

## Goal

Fix all UI layer dependency violations per Gate 2 (Dependency Direction). After this work, `ui/` will only import from `core/`, `types/`, `utils/`, and `configuration/` (classified as utils-level).

**Non-goals:**
- Refactoring core/tools layer internals
- Adding new features
- Changing any runtime behavior

## Scope & Assumptions

**In scope:**
- 3 imports from `tools/` (2 files)
- 1 import from `lsp/` (1 file)
- Architecture decision on `configuration/`

**Out of scope:**
- Performance optimization
- Test coverage expansion beyond verification

**Assumptions:**
- `configuration/` is utils-level (read-only static data)
- `StateManager` already exists and can be extended
- Tool results can include metadata (for IGNORE_PATTERNS_COUNT)

## Deliverables (DoD)

| Deliverable | Acceptance Criteria |
|-------------|---------------------|
| No ui→tools imports | `grep -r "from tunacode.tools" src/tunacode/ui/` returns empty |
| No ui→lsp imports | `grep -r "from tunacode.lsp" src/tunacode/ui/` returns empty |
| `utils/formatting.py` | Contains `truncate_diagnostic_message()` |
| ToolHandler via core | `StateManager` or `AgentRunner` exposes tool handler |
| Updated dependency graph | `layers.dot` shows 0 violations |

## Readiness (DoR)

- [x] Research doc complete
- [x] Branch exists: `ui-dependency-direction`
- [x] Current violations mapped with file:line
- [x] Fix strategies defined

## Milestones

- **M1:** Core layer exposes ToolHandler (P0)
- **M2:** Move utility functions to utils/ (P1, P2)
- **M3:** Verify all violations resolved
- **M4:** Update dependency graph documentation

## Work Breakdown (Tasks)

### Task 1: Expose ToolHandler via Core Layer (P0)
**Summary:** Remove direct `ToolHandler` imports from UI by exposing it through `StateManager`.

**Files:**
- `src/tunacode/core/state.py` – Add `tool_handler` property
- `src/tunacode/ui/main.py` – Use `state_manager.tool_handler`
- `src/tunacode/ui/repl_support.py` – Use `state_manager.tool_handler`

**Acceptance Tests:**
- `ui/main.py` has no `from tunacode.tools` imports
- `ui/repl_support.py` has no `from tunacode.tools` imports
- Tool authorization still works (manual test)

---

### Task 2: Move IGNORE_PATTERNS_COUNT to Tool Result (P1)
**Summary:** Remove `IGNORE_PATTERNS_COUNT` import by including count in tool result.

**Files:**
- `src/tunacode/tools/list_dir.py` – Add `ignore_count` to result dict
- `src/tunacode/ui/renderers/tools/list_dir.py` – Read from result

**Acceptance Tests:**
- `ui/renderers/tools/list_dir.py` has no `from tunacode.tools` imports
- Ignore count still displays correctly

---

### Task 3: Move truncate_diagnostic_message to Utils (P2)
**Summary:** Move text utility from LSP to utils layer.

**Files:**
- `src/tunacode/utils/formatting.py` – Create with function
- `src/tunacode/lsp/diagnostics.py` – Import from utils
- `src/tunacode/ui/renderers/tools/diagnostics.py` – Import from utils

**Acceptance Tests:**
- `ui/renderers/tools/diagnostics.py` has no `from tunacode.lsp` imports
- Function exists in `utils/formatting.py`
- Both LSP and UI use the same function

---

### Task 4: Document Configuration Architecture Decision (P3)
**Summary:** Formalize that `configuration/` is utils-level, not core-level.

**Files:**
- `CLAUDE.md` or architecture docs – Document decision
- `layers.dot` – Mark configuration edge as valid

**Acceptance Tests:**
- Architecture decision documented
- Dependency graph shows no violations

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| ToolHandler API mismatch | High | Low | Review current usage patterns | Compile errors |
| Circular import | Medium | Low | Test imports before committing | Import error |
| Missing tool auth | High | Low | Manual test after each change | Auth failures |

## Test Strategy

**Verification command:**
```bash
grep -r "from tunacode.tools" src/tunacode/ui/ && \
grep -r "from tunacode.lsp" src/tunacode/ui/
```

Both should return empty after all tasks complete.

## References

- Research: `memory-bank/research/2026-01-26_ui-dependency-violations.md`
- Gate 2: `CLAUDE.md` Dependency Direction section
- Dependency graph: `layers.dot`

---

## Tickets Created

| Ticket ID | Title | Priority | Status |
|-----------|-------|----------|--------|
| tun-7395 | Expose ToolHandler via StateManager | P1 | open |
| tun-dcb8 | Move IGNORE_PATTERNS_COUNT to tool result | P2 | open |
| tun-41f6 | Move truncate_diagnostic_message to utils | P2 | open |
| tun-7099 | Document configuration as utils-level | P3 | open |

## Dependencies

- tun-7395 (ToolHandler) has no dependencies - can start immediately
- tun-dcb8 (IGNORE_PATTERNS_COUNT) has no dependencies - can start immediately
- tun-41f6 (truncate_diagnostic_message) has no dependencies - can start immediately
- tun-7099 (Configuration decision) should be done last to update graphs
