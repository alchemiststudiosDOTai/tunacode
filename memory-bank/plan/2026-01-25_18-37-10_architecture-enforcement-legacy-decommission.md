# Architecture Enforcement & Legacy Decommission – Plan

---
title: "Architecture Enforcement & Legacy Decommission – Plan"
phase: Plan
date: "2026-01-25_18-37-10"
owner: "Claude (planning agent)"
parent_research: "memory-bank/research/2026-01-25_18-34-28_task09-task10-architecture-legacy.md"
git_commit_at_plan: "92732f50"
tags: [plan, architecture, legacy-decommission, task-09, task-10]
---

## Goal

**Singular Objective:** Establish automated architecture enforcement and complete legacy path decommissioning in ONE focused execution pass.

**Success Criteria:**
1. Architecture tests exist that fail on dependency violations
2. Legacy `get_message_content()` is deleted from production code
3. All tests pass (`uv run pytest`)

**Non-Goals:**
- Moving `core/limits.py` (deferred - requires separate PR)
- Adding SessionState field count tests (deferred - needs threshold decision)
- Comprehensive import chain depth tests (deferred - nice-to-have)

---

## Scope & Assumptions

### In Scope
- Create `tests/architecture/test_layer_dependencies.py` (ONE test file)
- Delete `get_message_content()` from `message_utils.py`
- Remove legacy export from `messaging/__init__.py`
- Update 3 test files to remove legacy references

### Out of Scope
- `core/limits.py` relocation (architectural debt, separate PR)
- SessionState complexity tests (needs team decision on field limit)
- Import chain depth analysis (future enhancement)

### Assumptions
- Branch `master` is current and clean
- All 3 production call sites already migrated (verified)
- Test suite currently passes

---

## Deliverables (DoD)

| Deliverable | Acceptance Criteria |
|-------------|---------------------|
| `tests/architecture/test_layer_dependencies.py` | Tests pass; would fail if `core/` imported `ui/` |
| Deleted `message_utils.py:get_message_content()` | Function removed, file may be deleted if empty |
| Updated `messaging/__init__.py` | No `get_message_content` export |
| Updated test files | No imports of `get_message_content` |
| All tests green | `uv run pytest` exits 0 |

---

## Readiness (DoR)

| Prerequisite | Status |
|--------------|--------|
| Research complete | ✅ Verified with sub-agents |
| Git state clean | ✅ Only untracked research doc |
| Target files identified | ✅ Exact line numbers confirmed |
| Auto-discovery pattern available | ✅ From `test_tool_conformance.py:18-54` |

---

## Milestones

| Milestone | Description | Gate |
|-----------|-------------|------|
| M1 | Architecture test skeleton | Test file exists and imports work |
| M2 | Dependency direction test | Test passes (core→ui violation would fail) |
| M3 | Legacy deletion | `get_message_content` removed |
| M4 | Test file cleanup | All test files updated |
| M5 | Final validation | `uv run pytest` passes |

---

## Work Breakdown (Tasks)

### Task 1: Create architecture test directory and file
**Milestone:** M1
**Owner:** Executor
**Dependencies:** None

**Files:**
- CREATE: `tests/architecture/__init__.py` (empty)
- CREATE: `tests/architecture/test_layer_dependencies.py`

**Implementation:**
```python
# tests/architecture/test_layer_dependencies.py
"""Architecture enforcement tests for dependency direction."""
import ast
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent.parent / "src" / "tunacode"

FORBIDDEN_IMPORTS = {
    "core": ["tunacode.ui"],      # core cannot import ui
    "tools": ["tunacode.ui", "tunacode.core"],  # tools cannot import ui or core
    "utils": ["tunacode.ui", "tunacode.core", "tunacode.tools"],  # utils is lowest
    "types": ["tunacode.ui", "tunacode.core", "tunacode.tools"],  # types is lowest
}

# Known violations to fix in future PRs
KNOWN_VIOLATIONS = {
    "tunacode.tools.read_file": ["tunacode.core.limits"],  # Issue: limits.py misplaced
    "tunacode.tools.bash": ["tunacode.core.limits"],
}

def get_imports(filepath: Path) -> list[str]:
    """Extract all import statements from a Python file."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports

def discover_modules(package: str) -> list[tuple[str, Path]]:
    """Find all Python modules in a package."""
    package_dir = SRC_DIR / package
    if not package_dir.exists():
        return []

    modules = []
    for py_file in package_dir.rglob("*.py"):
        if py_file.stem.startswith("_"):
            continue
        rel = py_file.relative_to(SRC_DIR)
        module_name = "tunacode." + str(rel.with_suffix("")).replace("/", ".")
        modules.append((module_name, py_file))
    return modules

class TestLayerDependencies:
    """Verify dependency direction: ui → core → tools → utils/types."""

    @pytest.mark.parametrize("package", ["core", "tools", "utils", "types"])
    def test_no_forbidden_imports(self, package: str):
        """Each layer must not import from upper layers."""
        forbidden = FORBIDDEN_IMPORTS.get(package, [])
        if not forbidden:
            pytest.skip(f"No forbidden imports defined for {package}")

        violations = []
        for module_name, filepath in discover_modules(package):
            # Skip known violations (tracked for future fix)
            known = KNOWN_VIOLATIONS.get(module_name, [])

            for imp in get_imports(filepath):
                for forbidden_prefix in forbidden:
                    if imp.startswith(forbidden_prefix):
                        if imp not in known and not any(imp.startswith(k) for k in known):
                            violations.append(f"{module_name} imports {imp}")

        assert not violations, f"Forbidden imports found:\n" + "\n".join(violations)
```

**Acceptance Tests:**
- [ ] `tests/architecture/` directory exists
- [ ] `test_layer_dependencies.py` imports without error
- [ ] Test passes when no violations exist

---

### Task 2: Delete legacy get_message_content function
**Milestone:** M3
**Owner:** Executor
**Dependencies:** Task 1 (architecture test in place)

**Files:**
- EDIT: `src/tunacode/utils/messaging/message_utils.py` - Delete lines 6-34
- EDIT: `src/tunacode/utils/messaging/__init__.py` - Remove export (lines 16, 21)

**Acceptance Tests:**
- [ ] `get_message_content` not in `message_utils.py`
- [ ] `get_message_content` not exported from `messaging/__init__.py`
- [ ] Imports from `tunacode.utils.messaging` still work for other functions

---

### Task 3: Update test files to remove legacy references
**Milestone:** M4
**Owner:** Executor
**Dependencies:** Task 2

**Files:**
- EDIT: `tests/unit/core/test_message_utils.py` - Delete entire file (only tests legacy function)
- EDIT: `tests/unit/types/test_adapter.py` - Remove lines 29, 301-324 (parity tests)
- EDIT: `tests/parity/test_message_parity.py` - Remove legacy comparison (lines 19, 73, 75)

**Acceptance Tests:**
- [ ] No test file imports `get_message_content`
- [ ] `uv run pytest tests/unit/types/test_adapter.py` passes
- [ ] `uv run pytest tests/parity/` passes

---

### Task 4: Final validation
**Milestone:** M5
**Owner:** Executor
**Dependencies:** Tasks 1-3

**Commands:**
```bash
uv run pytest tests/architecture/
uv run pytest
uv run ruff check src/tunacode/utils/messaging/
```

**Acceptance Tests:**
- [ ] All architecture tests pass
- [ ] Full test suite passes
- [ ] No ruff errors in messaging module

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| Hidden production usage of `get_message_content` | High | Low | Research verified zero usage; grep before delete | Import error at runtime |
| Architecture test false positives | Medium | Medium | Known violations list; exclude infrastructure layers | Tests fail on valid code |
| Test file edits break other tests | Medium | Low | Run full suite after each edit | pytest failures |

---

## Test Strategy

**ONE new test file:** `tests/architecture/test_layer_dependencies.py`

This test:
- Uses `ast.parse()` for static analysis (no imports executed)
- Parametrizes by package for clear failure messages
- Maintains `KNOWN_VIOLATIONS` dict for tracked tech debt
- Fails fast on new violations, allowing existing ones

---

## References

| Reference | Location |
|-----------|----------|
| Research doc | `memory-bank/research/2026-01-25_18-34-28_task09-task10-architecture-legacy.md` |
| Auto-discovery pattern | `tests/integration/tools/test_tool_conformance.py:18-54` |
| Legacy function | `src/tunacode/utils/messaging/message_utils.py:6-34` |
| Canonical adapter | `src/tunacode/utils/messaging/adapter.py:280-318` |
| Task 09 spec | `.claude/task/task_09_architecture_enforcement_tests.md` |
| Task 10 spec | `.claude/task/task_10_legacy_path_decommission.md` |

---

## Alternative Approach (Deferred)

**Comprehensive architecture enforcement** would include:
- `core/limits.py` relocation to `utils/config/limits.py`
- SessionState field count test (threshold TBD)
- Import chain depth analysis
- Circular dependency detection

This is deferred to a separate PR to keep execution focused.

---

## Execution Command

```
/context-engineer:execute "memory-bank/plan/2026-01-25_18-37-10_architecture-enforcement-legacy-decommission.md"
```
