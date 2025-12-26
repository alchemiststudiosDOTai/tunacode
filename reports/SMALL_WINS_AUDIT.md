# Small Wins Audit Report

**Date**: 2025-12-25
**Commit**: b8e7d32
**Branch**: master (clean)

---

## Executive Summary

| Category | Finding | Effort | Impact |
|----------|---------|--------|--------|
| Dead Code | 3 unused UI component files | XS | M |
| Duplication | callbacks.py duplicates repl_support.py | S | L |
| Constants | ~30 unused constants in constants.py | XS | S |
| Type Errors | 46 mypy errors across 14 files | S | M |
| Long Functions | 6 functions >100 lines | S | M |
| Test Coverage | Flat test structure, 17 tests for 100+ files | M | L |

**Top Quick Wins (XS/S effort, L/M impact):**
1. Remove duplicate `ui/callbacks.py` - import from `repl_support.py` instead
2. Delete 3 unused UI component files
3. Clean up ~30 unused constants
4. Fix implicit Optional type annotations (10 mypy errors)
5. Split `ui/commands/__init__.py` into separate command files

---

## Findings by Category

### A. Structure & Naming

#### Directory Organization

**Positive:**
- Clean module structure with `__init__.py` everywhere
- PEP 561 compliant (`py.typed` present)
- Clear separation: tools/, ui/, core/, utils/

**Observations:**

| Location | Issue | Suggestion |
|----------|-------|------------|
| `src/tunacode/cli/` | Only contains one `.tcss` file | Consider merging with `ui/` or removing |
| `tests/` | Flat structure (17 files, no subdirs) | Organize by module as test count grows |
| `src/tunacode/prompts/` + `src/tunacode/tools/prompts/` | Prompts in two locations | Acceptable separation, just document |

#### Naming Patterns

- All files follow snake_case convention
- Private classes use `_PascalCase` intentionally
- No violations found

---

### B. Dead Code & Orphans

#### Unused Files (DELETE CANDIDATES)

| File | Reason | Risk |
|------|--------|------|
| `src/tunacode/ui/callbacks.py` | Duplicates `repl_support.py` (5 functions, ~100 LOC) | Low - verify no imports first |
| `src/tunacode/ui/components/error_display.py` | Exported but never imported | Low - vestigial widget |
| `src/tunacode/ui/components/search_results.py` | Exported but never imported | Low - vestigial widget |
| `src/tunacode/ui/components/tool_panel.py` | Exported but never imported | Low - vestigial widget |

#### Unused Constants (`src/tunacode/constants.py`)

**Tool Name Aliases (lines 66-72)** - Never used, code uses `ToolName.X` directly:
```python
TOOL_READ_FILE = ToolName.READ_FILE
TOOL_WRITE_FILE = ToolName.WRITE_FILE
TOOL_UPDATE_FILE = ToolName.UPDATE_FILE
TOOL_BASH = ToolName.BASH
TOOL_GREP = ToolName.GREP
TOOL_LIST_DIR = ToolName.LIST_DIR
TOOL_GLOB = ToolName.GLOB
```

**Command Constants (lines 86-97)** - Never used:
```python
CMD_HELP, CMD_CLEAR, CMD_YOLO, CMD_MODEL, CMD_EXIT, CMD_QUIT
DESC_HELP, DESC_CLEAR, DESC_YOLO, DESC_MODEL, DESC_EXIT
```

**Panel Constants (lines 145-148)** - Never used:
```python
PANEL_ERROR, PANEL_MESSAGE_HISTORY, PANEL_MODELS, PANEL_AVAILABLE_COMMANDS
```

**UI String Constants (lines 136-143)** - Never used:
```python
UI_PROMPT_PREFIX, UI_DARKGREY_OPEN, UI_DARKGREY_CLOSE
UI_BOLD_OPEN, UI_BOLD_CLOSE, UI_KEY_ENTER, UI_KEY_ESC_ENTER
```

**Tool Categories (lines 83-84)** - Never used:
```python
WRITE_TOOLS, EXECUTE_TOOLS
```

#### Over-Exported Authorization Classes

`src/tunacode/tools/authorization/__init__.py` exports 10+ classes, only 2 used externally:
- **Keep**: `ToolHandler`, `create_default_authorization_policy`
- **Remove from exports**: `AuthContext`, `ToolRejectionNotifier`, `ConfirmationRequestFactory`, all Rule classes

#### Technical Debt Markers

**Result: ZERO TODO/FIXME/HACK/XXX comments found**

The only occurrences are:
- Variable names in `tools/todo.py` (e.g., `TODO_STATUS_PENDING`)
- Example text in prompt documentation

---

### C. Lint & Config Drifts

#### Ruff Results
```
All checks passed!
```

#### Mypy Results: 46 Errors in 14 Files

**Pattern 1: Implicit Optional (10 errors)**
```
src/tunacode/core/agents/agent_components/state_transition.py:97
src/tunacode/core/agents/agent_components/message_handler.py:44
```
Fix: Change `def foo(x: T = None)` to `def foo(x: T | None = None)`

**Pattern 2: Protocol Mismatches (15 errors)**
```
src/tunacode/ui/commands/__init__.py:106,122,192,201,224,229,247,265,276,280,298,300
src/tunacode/ui/app.py:142-156,261,267,280,288,311,462
```
Fix: `StateManagerProtocol` missing `list_sessions`, `save_session`, `load_session` methods

**Pattern 3: Type Annotation Gaps (10 errors)**
```
src/tunacode/core/state.py:257,276 - msg_adapter needs annotation
src/tunacode/core/agents/agent_components/agent_config.py:327-333 - provider type issues
src/tunacode/core/agents/research_agent.py:230 - output_type incompatibility
```

**Pattern 4: Callback Signature Mismatches (5 errors)**
```
src/tunacode/ui/callbacks.py:91 - update_subagent_progress args
src/tunacode/ui/app.py:102 - ShellRunnerHost.notify signature
```

**Full list by file:**
| File | Errors |
|------|--------|
| ui/commands/__init__.py | 13 |
| ui/app.py | 12 |
| core/agents/agent_components/agent_config.py | 4 |
| core/state.py | 2 |
| (10 other files) | 15 |

---

### D. Micro-Performance/Clarity

#### Long Functions (>100 lines)

| Function | File:Line | Lines | Complexity |
|----------|-----------|-------|------------|
| `block_anchor_replacer` | tools/utils/text_match.py:162 | 115 | 23 |
| `render_research_codebase` | ui/renderers/tools/research.py:132 | 163 | 20 |
| `render_bash` | ui/renderers/tools/bash.py:118 | 130 | 15 |
| `render_update_file` | ui/renderers/tools/update_file.py:130 | 108 | 9 |
| `render_grep` | ui/renderers/tools/grep.py:127 | 102 | 10 |
| `get_or_create_agent` | core/agents/agent_components/agent_config.py:340 | 102 | 8 |

#### High Cyclomatic Complexity (>15)

| Function | File:Line | Complexity |
|----------|-----------|------------|
| `create_fallback_response` | core/agents/agent_components/agent_helpers.py:180 | 26 |
| `block_anchor_replacer` | tools/utils/text_match.py:162 | 23 |
| `search_sync` | tools/glob.py:251 | 23 |
| `_is_ignored` | utils/system/gitignore.py:60 | 21 |
| `render_research_codebase` | ui/renderers/tools/research.py:132 | 20 |
| `_build_wrapped_display_text` | ui/widgets/editor.py:292 | 18 |
| `_index_python_file` | indexing/code_index.py:315 | 16 |

#### Large Files (>400 LOC)

| File | Lines | Notes |
|------|-------|-------|
| ui/renderers/panels.py | 550 | Could split by panel type |
| core/agents/main.py | 545 | Well-organized, acceptable |
| ui/app.py | 544 | Textual app lifecycle, acceptable |
| indexing/code_index.py | 526 | Focused, acceptable |
| tools/grep.py | 468 | Could extract strategies |
| core/agents/agent_components/agent_config.py | 441 | Acceptable |
| ui/commands/__init__.py | 429 | **Split into separate files** |
| core/state.py | 409 | Well-organized |

---

## Per-File Suggestions

| Path | Issue | Action | Risk | Priority |
|------|-------|--------|------|----------|
| `ui/callbacks.py` | Duplicates repl_support.py | Delete, update imports in app.py | Low | 1 |
| `ui/components/error_display.py` | Never imported | Delete | Low | 2 |
| `ui/components/search_results.py` | Never imported | Delete | Low | 2 |
| `ui/components/tool_panel.py` | Never imported | Delete | Low | 2 |
| `constants.py:66-97,136-148` | Unused constants | Delete lines | Low | 3 |
| `tools/authorization/__init__.py` | Over-exports | Reduce to 2 exports | Low | 4 |
| `core/agents/agent_components/state_transition.py:97` | Implicit Optional | Add `| None` | None | 5 |
| `core/agents/agent_components/message_handler.py:44` | Implicit Optional | Add `| None` | None | 5 |
| `types/state.py` | Missing protocol methods | Add list_sessions, save_session, load_session | Low | 6 |
| `ui/commands/__init__.py` | 429 LOC monolith | Split into per-command files | Low | 7 |

---

## Guardrails & Next Steps

### Batching Strategy

**Batch 1: Dead Code Cleanup (30 min)**
- Delete `ui/callbacks.py`
- Delete 3 unused component files
- Update `ui/components/__init__.py`
- Run tests

**Batch 2: Constants Cleanup (15 min)**
- Remove unused constants from `constants.py`
- Run tests

**Batch 3: Type Annotations (45 min)**
- Fix implicit Optional in 2 files
- Add missing protocol methods
- Run mypy to verify

**Batch 4: Module Split (1 hour)**
- Split `ui/commands/__init__.py` into separate command files
- Run tests

### PR Guidelines
- <=10 files per PR
- Add test for any deletion to verify no breakage
- Run full test suite before merge
- Each batch = 1 PR

### Not Addressed (Future Work)
- Long function refactoring (needs careful testing)
- Renderer pattern consolidation (architectural decision)
- Test organization restructuring (wait for more tests)

---

## Validation Checklist

- [x] Repository clean (no uncommitted changes)
- [x] Ruff passes
- [x] Mypy errors documented (46 total)
- [x] No TODO/FIXME debt markers
- [x] Report created at reports/SMALL_WINS_AUDIT.md
- [x] No modifications made (read-only audit)
