# Research - Ruff Lint Cleanup Map

**Date:** 2025-12-06
**Owner:** claude
**Phase:** Research

## Goal

Map all 40 ruff lint errors (B904, SIM102, SIM1xx, UP007/UP045) before implementing fixes. No shortcuts - every fix must be vetted for correctness and readability preservation.

## Summary

| Category | Count | Action |
|----------|-------|--------|
| B904 (exception chaining) | 16 | All need `from err` or `from None` |
| SIM102 (nested if) | 11 | 7 combine, 4 keep as-is |
| SIM103 (return condition) | 2 | 1 fix, 1 keep (early returns) |
| SIM108 (ternary) | 2 | Both can simplify |
| SIM110 (any/all) | 1 | Can simplify |
| SIM117 (with contexts) | 2 | Both can simplify |
| UP007/UP045 (type union) | 6 | All need `X \| Y` syntax |

---

## B904: Exception Re-raise Chaining (16 issues)

All exceptions raised within `except` blocks must use `from err` (chain) or `from None` (suppress).

### Decision Matrix
- **`from err`**: When the new exception is CAUSED BY the caught one (preserve traceback)
- **`from None`**: When REPLACING the exception entirely (hide internals)

| File | Line | Caught | Raised | Fix | Reason |
|------|------|--------|--------|-----|--------|
| `result_wrapper.py` | 34 | AttributeError | AttributeError | `from None` | Hide wrapper internals |
| `bash.py` | 83 | TimeoutError | ModelRetry | `from err` | Transform for LLM |
| `bash.py` | 96 | FileNotFoundError | ModelRetry | `from err` | Transform for LLM |
| `decorators.py` | 52 | Exception | ToolExecutionError | `from e` | Wraps original_error |
| `decorators.py` | 84 | FileNotFoundError | ModelRetry | `from err` | Transform for LLM |
| `decorators.py` | 86 | PermissionError | FileOperationError | `from e` | Wraps original_error |
| `decorators.py` | 90 | UnicodeDecodeError | FileOperationError | `from e` | Wraps original_error |
| `decorators.py` | 94 | OSError | FileOperationError | `from e` | Wraps original_error |
| `grep.py` | 199 | Exception | ToolExecutionError | `from e` | Generic wrapper |
| `update_file.py` | 38 | ValueError | ModelRetry | `from e` | Transform with context |
| `user_configuration.py` | 54 | JSONDecodeError | ConfigurationError | `from err` | Preserve line/col info |
| `user_configuration.py` | 56 | Exception | ConfigurationError | `from e` | Generic wrapper |
| `user_configuration.py` | 71 | PermissionError | ConfigurationError | `from e` | OS error transform |
| `user_configuration.py` | 75 | OSError | ConfigurationError | `from e` | OS error transform |
| `user_configuration.py` | 79 | Exception | ConfigurationError | `from e` | Generic wrapper |
| `command_parser.py` | 56 | JSONDecodeError | ValidationError | `from e` | Preserve parse error |

**Summary: 15 use `from err/e`, 1 use `from None`**

---

## SIM102: Nested If Statements (11 issues)

### Safe to Combine (7)

| File | Line | Reason |
|------|------|--------|
| `agent_helpers.py` | 210 | Guard chain for type checking |
| `node_processor.py` | 220 | Preconditions for transition |
| `node_processor.py` | 395 | Null checks chain |
| `file_filter.py` | 80 | Filter conditions |
| `editor.py` | 30-31 | Validation chain (flatten) |
| `code_index.py` | 262 | (Need verification) |
| `code_index.py` | 335 | (Need verification) |

### Keep As-Is (4)

| File | Line | Reason |
|------|------|--------|
| `download_ripgrep.py` | 132 | Logical OS/arch grouping - more readable |
| `ripgrep.py` | 34 | Same OS/arch pattern - symmetry |
| `bash.py` | 147 | Security check with exception - clarity |

---

## SIM103: Return Condition Directly (2 issues)

| File | Line | Action | Reason |
|------|------|--------|--------|
| `truncation_checker.py` | 78 | FIX | `return open_brackets > close_brackets` |
| `compaction.py` | 40 | KEEP | Early returns are explicit per CLAUDE.md |

---

## SIM108: Ternary Operator (2 issues)

| File | Line | Current | Fix |
|------|------|---------|-----|
| `ui_import_timer.py` | 157 | if/else block | `tuple(args.modules) if args.modules else DEFAULT_MODULES` |
| `command.py` | 149 | if/else block | `shlex.split(command) if isinstance(command, str) else command` |

---

## SIM110: Use any() (1 issue)

| File | Line | Current | Fix |
|------|------|---------|-----|
| `check_file_size.py` | 31 | for loop with return | `return any(path.match(pat) for pat in SKIP_GLOBS)` |

---

## SIM117: Combine Context Managers (2 issues)

| File | Line | Current | Fix |
|------|------|---------|-----|
| `download_ripgrep.py` | 54 | nested `with` | `with urlopen(url) as response, dest_path.open("wb") as f:` |
| `download_ripgrep.py` | 71 | triple nested | Use parenthesized context manager |

---

## UP007/UP045: Type Annotations (6 issues)

Python 3.11+ supports `X | Y` natively. No future import needed.

| File | Line | Current | Fix |
|------|------|---------|-----|
| `message_handler.py` | 10 | `Union[str, None]` | `str \| None` |
| `types.py` | 23 | `Union[ToolReturnPart, Any]` | `ToolReturnPart \| Any` |
| `types.py` | 151 | `Optional[Any]` | `Any \| None` |
| `types.py` | 163 | `Union[str, Path]` | `str \| Path` |
| `types.py` | 171 | `Optional[Exception]` | `Exception \| None` |
| `types.py` | 182 | `Union[bool, str]` | `bool \| str` |

**Also remove unused imports**: `Union`, `Optional` from `types.py` and `message_handler.py`

---

## Implementation Order

**Phase 1: Safe mechanical fixes (ruff --fix compatible)**
1. UP007/UP045 - Type annotations (6 files)
2. SIM108 - Ternary operators (2 files)
3. SIM110 - Use any() (1 file)
4. SIM117 - Context managers (1 file)

**Phase 2: B904 - Exception chaining (requires context)**
5. Add `from err` to 15 locations
6. Add `from None` to 1 location (result_wrapper.py)

**Phase 3: SIM102 - Nested if (judgment calls)**
7. Combine 7 nested if statements
8. Document why 4 are kept as-is

**Phase 4: SIM103 - Return condition**
9. Fix truncation_checker.py
10. Keep compaction.py as-is (per style guide)

---

## Files by Fix Count

| File | Fixes Needed |
|------|--------------|
| `types.py` | 5 |
| `decorators.py` | 5 |
| `user_configuration.py` | 5 |
| `download_ripgrep.py` | 4 |
| `bash.py` | 3 |
| `node_processor.py` | 2 |
| `message_handler.py` | 1 |
| `result_wrapper.py` | 1 |
| `grep.py` | 1 |
| `update_file.py` | 1 |
| `command_parser.py` | 1 |
| `agent_helpers.py` | 1 |
| `truncation_checker.py` | 1 |
| `file_filter.py` | 1 |
| `editor.py` | 2 |
| `ripgrep.py` | 1 (keep) |
| `compaction.py` | 1 (keep) |
| `ui_import_timer.py` | 1 |
| `command.py` | 1 |
| `check_file_size.py` | 1 |
| `code_index.py` | 2 |

---

## Knowledge Gaps

1. `code_index.py:262` and `:335` - Need to verify these SIM102 locations
2. Some files may have additional Union/Optional usages not flagged

## References

- Ruff rules: https://docs.astral.sh/ruff/rules/
- B904: https://docs.astral.sh/ruff/rules/raise-without-from-inside-except/
- SIM102: https://docs.astral.sh/ruff/rules/collapsible-if/
- UP007: https://docs.astral.sh/ruff/rules/non-pep604-annotation/
