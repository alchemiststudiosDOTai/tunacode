# Research -- pydantic-ai Remnant Sweep (Pre-PR)
**Date:** 2026-02-07
**Owner:** agent
**Phase:** Research
**Branch:** tunacode-loop-replace
**Commit:** 2fb42cf26648171d0ce8a2b2ab509386090675fc

## Goal

Identify all remaining pydantic-ai references, shims, dead code, and stale configuration
across the codebase before opening the merge PR. The migration (Phases 1-10) is complete.
pydantic-ai is banned as a dependency; pydantic itself stays.

## Findings

### Runtime Code is CLEAN

Zero live `import pydantic_ai` or `from pydantic_ai` statements remain in `src/` or `tests/`.
No `TypeAdapter`, `ModelRequest`, `ModelResponse`, `ArgsJson`, `RunResult`, or `"parts"` key checks.
All test fixtures use tinyagent dict builders. All UI renderers exclusively handle dicts.

---

### HIGH PRIORITY -- Dead Code to Delete

| Item | File | Lines | Why |
|------|------|-------|-----|
| `model_dump()` fallback | [`src/tunacode/ui/main.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/src/tunacode/ui/main.py#L255-L263) | 255-263 | `_serialize_message()` has `model_dump()` and `__dict__` branches that are unreachable -- all messages are enforced as dicts at `state.py:167-171`. This silently accepts pydantic objects, contradicting the hard-break policy. |
| `check_query_satisfaction` stub | [`src/tunacode/core/agents/main.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/src/tunacode/core/agents/main.py#L540-L549) | 540-549 | Exported in `__init__.py` but never called anywhere. Always returns `True`. Docstring says "Legacy hook retained for compatibility." |
| `NormalizedUsage` + `normalize_request_usage` | [`src/tunacode/types/canonical.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/src/tunacode/types/canonical.py#L247-L291) | 247-291 | Exported from `types/__init__.py` but never imported or called anywhere else. Docstring references "pydantic-ai Usage objects." Dead migration bridge code. |

### MEDIUM PRIORITY -- Potentially Dead Module

| Item | File | Why |
|------|------|-----|
| `ResponseState` (state-machine version) | [`src/tunacode/core/agents/agent_components/response_state.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/src/tunacode/core/agents/agent_components/response_state.py) | Wraps `AgentStateMachine` but exposes "Legacy boolean flag" properties. Not imported by any other module. A separate plain `ResponseState` dataclass at `core/types/agent_state.py:7-14` is the one actually used. Contains `try/except Exception: pass` at L81-83 ("Best-effort: ignore invalid transition in legacy paths"). Entire file is likely dead. |

### HIGH PRIORITY -- Config / Docs to Update

| Item | File | Line(s) | Issue |
|------|------|---------|-------|
| CLAUDE.md | [`CLAUDE.md`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/CLAUDE.md#L105) | 105 | Says "We are in the middle of ripping out pydantic-ai. Expect some turbulence." -- migration is complete. |
| AGENTS.md | [`AGENTS.md`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/AGENTS.md#L107) | 107 | Says "pydantic-ai loop removal is in progress. Expect some turbulence." -- same. |
| dependabot.yml | [`.github/dependabot.yml`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/.github/dependabot.yml#L25) | 23-26 | Ignore rule for `pydantic-ai` version updates -- package no longer in dependencies. |
| .coderabbit.yaml | [`.coderabbit.yaml`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/.coderabbit.yaml) | 61, 83-84, 225-243 | Review instructions check for pydantic-ai frozen dataclasses, dual-format sanitization, `NoSetAttrOnPydantic` -- all obsolete. |
| pytest.ini | [`pytest.ini`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/pytest.ini#L35) | 35 | Comment says "transitive dep from pydantic-ai" -- pydantic-ai is gone; verify if the filter is still needed. |

### LOW PRIORITY -- Stale Caches

Orphaned `.pyc` files for deleted source modules (17 files across `src/tunacode/core/agents/` subdirs):
- `agent_components/__pycache__/`: result_wrapper, tool_buffer, message_handler, truncation_checker, openai_model, streaming, streaming_debug, tool_executor
- `__pycache__/`: research_agent, delegation_tools, debug_utils, history_preparer, request_logger
- `resume/__pycache__/`: filter, message_inspection, prune, summary

Also stale:
- `src/tunacode/types/__pycache__/pydantic_ai.cpython-{312,313}.pyc`
- `tests/architecture/__pycache__/test_pydantic_ratchet.cpython-313-pytest-9.0.1.pyc`
- `.mypy_cache/3.11/tunacode/types/pydantic_ai.{meta,data}.json`

### LOW PRIORITY -- Misleading Names (NOT dead, just rename-worthy)

| Item | File | Assessment |
|------|------|------------|
| `to_legacy_records()` | `src/tunacode/core/types/tool_registry.py:165` | Actively used by headless output. Name implies dead code but it's the current API. |
| `from_dict()` / `to_dict()` docstrings | `src/tunacode/types/canonical.py:207-224` | Docstrings say "legacy dict format" but these ARE the current serialization path. |
| `rich_log` property | `src/tunacode/ui/app.py:107-110` | Docstring says "Backward compatibility alias" but it's the primary API (20+ call sites). |
| `core/tinyagent/__init__.py` docstring | `src/tunacode/core/tinyagent/__init__.py:3-7` | Still says "Phase 1 scaffolding" and "No runtime behavior is wired up yet" -- stale. |

### INFORMATIONAL -- Source Comments Referencing pydantic-ai

14 files in `src/` contain comments/docstrings mentioning pydantic-ai in historical context
("Legacy pydantic-ai message formats are intentionally **not** supported", etc.).
These are informational only. The error message at `main.py:129-131` is actively used.
Cleanup is optional documentation hygiene.

### NOT ACTIONABLE -- Historical Records

Files in `.claude/delta/`, `.claude/debug_history/`, `.claude/JOURNAL.md`, `memory-bank/research/`,
`memory-bank/plan/`, and `handoff.md` contain historical references to pydantic-ai.
These document the migration and should be preserved as-is.

### NEEDS VERIFICATION

| Item | File | Question |
|------|------|----------|
| `.pre-commit-config.yaml:58` | mypy additional_dependencies | Lists `pydantic>=2.0` -- pydantic (not pydantic-ai) may still be needed for mypy type stubs since some code uses pydantic models. Verify before removing. |

## Key Patterns / Solutions Found

- **Hard-break enforcement is solid**: `state.py:167-171` raises on non-dict messages, `session_picker.py` handles dicts only.
- **Type names reused safely**: `TextPart`, `ToolCallPart`, etc. are now native dataclasses in `canonical.py`, not pydantic-ai imports.
- **`ensure_tinyagent_importable()` is active**: Called from `agent_config.py:241`, despite stale "Phase 1" docstring.

## Knowledge Gaps

- Whether the `ResponseState` state-machine version (`agent_components/response_state.py`) has any runtime path that reaches it (initial scan says no, but needs grep confirmation before deletion).
- Whether the OpenTelemetry filterwarnings in `pytest.ini` are still needed after removing pydantic-ai.
- Whether `pydantic>=2.0` in mypy pre-commit deps is still required.

## References

- Handoff: [`handoff.md`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/handoff.md)
- Session state (hard-break enforcement): [`src/tunacode/core/session/state.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/src/tunacode/core/session/state.py)
- Canonical types: [`src/tunacode/types/canonical.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/src/tunacode/types/canonical.py)
- Main agent loop: [`src/tunacode/core/agents/main.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/src/tunacode/core/agents/main.py)
- Headless serializer: [`src/tunacode/ui/main.py`](https://github.com/alchemiststudiosDOTai/tunacode/blob/2fb42cf/src/tunacode/ui/main.py)
