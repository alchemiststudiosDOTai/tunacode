---
title: "Write Tools & LSP Diagnostics Fix - Plan"
phase: Plan
date: "2025-12-18"
owner: "Agent"
parent_research: "memory-bank/research/2025-12-18_write-tools-lsp-diagnostics-validation.md"
git_commit_at_plan: "291c385"
tags: [plan, write-tools, lsp, truncation, coding]
---

## Goal

- **Singular outcome:** Ensure LSP diagnostics are never truncated by restructuring the tool result composition to prioritize diagnostics over verbose diff content.

### Non-goals

- Performance optimization of Levenshtein fuzzy matching (Medium severity, separate effort)
- LSP multi-header parsing rewrite (High severity but requires protocol-level changes)
- Deployment, observability, or monitoring infrastructure

---

## Scope & Assumptions

### In Scope

1. Fix diagnostics truncation vulnerability (CRITICAL)
2. Add line-width cap to `_truncate_diff()`
3. Surface timeout failures to user (warn-level logging)

### Out of Scope

- LSP `_receive_one` multi-header support (requires protocol testing)
- `get_server_command` subcommand validation (requires version detection logic)
- Fuzzy matching algorithm optimization (acceptable tradeoff for correctness)
- Confirmation preview pre-truncation (Medium risk, separate effort)

### Assumptions

- Python 3.10+ runtime
- Rich library handles truncated strings gracefully
- Existing `MAX_CALLBACK_CONTENT` (50,000) remains the safety cap

---

## Deliverables

1. Modified `decorators.py`: Prepend diagnostics instead of append
2. Modified `update_file.py`: Add per-line width cap to `_truncate_diff()`
3. Modified `decorators.py`: Upgrade timeout logging from debug to warning
4. Modified `repl_support.py`: Smart truncation that preserves diagnostics block

---

## Readiness

### Preconditions

- [x] Research document validated all claims
- [x] Git state clean on master (291c385)
- [x] File locations confirmed with line numbers

### Key Constants

| Constant | Value | File |
|----------|-------|------|
| `MAX_CALLBACK_CONTENT` | 50,000 | constants.py:30 |
| `MAX_PANEL_LINE_WIDTH` | 200 | constants.py:32 |
| `TOOL_VIEWPORT_LINES` | 26 | constants.py:37 |

---

## Milestones

- **M1:** Diagnostics priority fix (truncation vulnerability)
- **M2:** Renderer hardening (line-width cap)
- **M3:** Observability improvement (timeout surfacing)
- **M4:** Integration validation

---

## Work Breakdown (Tasks)

### M1: Diagnostics Priority Fix

| ID | Task | Files | Acceptance |
|----|------|-------|------------|
| T1.1 | Restructure result composition to prepend diagnostics XML block before diff content | `decorators.py:188` | Diagnostics block appears FIRST in tool result string |
| T1.2 | Update `_truncate_for_safety()` to preserve diagnostics if present at start | `repl_support.py:136-142` | 55KB result with diagnostics at start preserves full diagnostics block |

**T1.1 Details:**
```python
# BEFORE (line 188):
result = f"{result}\n\n{diagnostics_output}"

# AFTER:
result = f"{diagnostics_output}\n\n{result}"
```

**T1.2 Details:**
- Detect if result starts with `<file_diagnostics`
- If so, find closing tag and preserve that block, truncate remainder
- Otherwise, simple head truncation (current behavior)

### M2: Renderer Hardening

| ID | Task | Files | Acceptance |
|----|------|-------|------------|
| T2.1 | Add per-line width cap using `MAX_PANEL_LINE_WIDTH` in `_truncate_diff()` | `update_file.py:102-113` | Lines >200 chars are truncated with `...` suffix |

**T2.1 Details:**
```python
def _truncate_diff(diff: str) -> tuple[str, int, int]:
    lines = diff.splitlines()
    total = len(lines)
    max_content = TOOL_VIEWPORT_LINES

    # NEW: Cap line width
    capped_lines = [
        line[:MAX_PANEL_LINE_WIDTH] + "..." if len(line) > MAX_PANEL_LINE_WIDTH else line
        for line in lines[:max_content]
    ]

    if total <= max_content:
        return "\n".join(capped_lines), total, total
    return "\n".join(capped_lines), max_content, total
```

### M3: Observability Improvement

| ID | Task | Files | Acceptance |
|----|------|-------|------------|
| T3.1 | Change timeout logging from `debug` to `warning` with user-visible message | `decorators.py:79-81` | Timeout emits warning-level log |

**T3.1 Details:**
```python
# BEFORE:
logger.debug("LSP diagnostics timed out for %s", filepath)

# AFTER:
logger.warning("LSP diagnostics timed out for %s (no type errors shown)", filepath)
```

### M4: Integration Validation

| ID | Task | Files | Acceptance |
|----|------|-------|------------|
| T4.1 | Manual test: large diff (>50KB) with type errors | N/A | Diagnostics visible in output |
| T4.2 | Manual test: minified JS file edit | N/A | No UI freeze, line truncated |
| T4.3 | Manual test: LSP timeout scenario | N/A | Warning appears in log |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Diagnostics block detection regex mismatch | Low | High | Use same pattern as `diagnostics.py:179` |
| Prepending diagnostics breaks existing parsers | Medium | Medium | Verify diagnostics renderer still finds block |
| Line truncation breaks syntax highlighting | Low | Low | Rich handles partial lines gracefully |

---

## Test Strategy

- **T1.2:** Add unit test for `_truncate_for_safety()` with diagnostics-prefixed content
- **T2.1:** Add unit test for `_truncate_diff()` with >200 char lines
- **T3.1:** No test needed (logging change only)

---

## References

### Research Document
- `memory-bank/research/2025-12-18_write-tools-lsp-diagnostics-validation.md`

### Key Code Sections
- `decorators.py:188` - diagnostics append location
- `repl_support.py:136-142` - safety truncation
- `update_file.py:102-113` - diff truncation
- `diagnostics.py:179` - diagnostics parsing regex
- `constants.py:30-37` - truncation constants

---

## Final Gate

| Item | Value |
|------|-------|
| Plan path | `memory-bank/plan/2025-12-18_write-tools-lsp-fix.md` |
| Milestone count | 4 |
| Task count | 6 (3 code + 3 validation) |
| Ready for coding | Yes |

**Next command:** `/context-engineer:execute "memory-bank/plan/2025-12-18_write-tools-lsp-fix.md"`
