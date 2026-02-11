---
title: "pydantic-ai Hard Rip -- Final Sweep Plan"
phase: Plan
date: "2026-02-07T18:12:36"
owner: "agent"
parent_research: "memory-bank/research/2026-02-07_pydantic-ai-remnant-sweep.md"
git_commit_at_plan: "2fb42cf2"
tags: [plan, pydantic-ai, dead-code, cleanup]
---

## Goal

**HARD RIP: pydantic-ai is dead. Kill every trace.**

This is not a soft deprecation or gradual phase-out. The migration is finished. pydantic-ai is banned. Every remaining fallback branch, compatibility shim, "legacy" stub, stale config reference, and orphaned cache artifact must be deleted -- not commented out, not guarded, not renamed. Deleted.

After this sweep:
- Zero pydantic-ai artifacts remain in runtime code, configuration, documentation, or caches.
- No silent fallback paths exist that would accept pydantic-ai objects (violating the hard-break policy at `state.py:167-171`).
- All docs and configs unambiguously state: **pydantic-ai has been fully removed. tinyagent is the sole agent loop.**
- pydantic (the validation library) remains -- it is NOT pydantic-ai.

**Non-goals:**
- Renaming misleading-but-live symbols (e.g. `to_legacy_records()`, `rich_log`) -- separate PR.
- Rewriting historical records in `.claude/delta/`, `memory-bank/`, or `handoff.md`.
- Adding new tests beyond what's needed to verify deletions don't break anything.

## Scope & Assumptions

**In scope:**
- 4 dead code deletions (runtime)
- 5 config/doc updates (stale pydantic-ai language)
- ~27 orphaned cache files (.pyc, .mypy_cache)
- Export cleanup in `__init__.py` files after deletions

**Out of scope:**
- Informational comments referencing pydantic-ai in historical context (14 files -- these document the migration)
- `.pre-commit-config.yaml` mypy `pydantic>=2.0` dep (pydantic itself is still used, not pydantic-ai)
- OpenTelemetry filterwarnings in pytest.ini (only the comment is stale, the filter itself may still be needed)

**Assumptions:**
- Branch: `tunacode-loop-replace` (current)
- No code has changed since research (confirmed: HEAD = 2fb42cf2)
- All deletions are verified zero-consumer (grep-confirmed)

## Deliverables (DoD)

1. Zero `model_dump()` / `__dict__` fallback branches in `_serialize_message()`
2. Zero `check_query_satisfaction` function or export
3. Zero `NormalizedUsage` / `normalize_request_usage` definitions or exports
4. Zero `agent_components/response_state.py` file
5. CLAUDE.md and AGENTS.md say migration is **complete** (hard rip language)
6. dependabot.yml has no pydantic-ai ignore rule
7. .coderabbit.yaml has no pydantic-ai review checks
8. pytest.ini comment updated (no "transitive dep from pydantic-ai")
9. Zero orphaned .pyc files for deleted modules
10. `ruff check .` passes
11. `uv run pytest` passes

## Readiness (DoR)

- Research doc verified: all 11 items confirmed present at documented locations
- No drift since research commit
- Branch is clean (only untracked research doc)

## Milestones

- **M1: Dead code deletion** -- Remove 4 dead code items + their exports
- **M2: Config/docs update** -- Update 5 stale config/doc files with hard-rip language
- **M3: Cache cleanup** -- Delete ~27 orphaned .pyc and mypy cache files
- **M4: Verify** -- ruff + pytest pass, grep confirms zero pydantic-ai in active code

## Work Breakdown (Tasks)

### T1: Delete dead runtime code (M1) -- Priority 1
Delete the 4 dead code items and clean up their exports:

1. `src/tunacode/ui/main.py:259-263` -- remove `model_dump()`, `__dict__`, and `str()` fallback branches from `_serialize_message()`. Keep only the `isinstance(msg, dict)` path and raise `TypeError` for non-dicts (matches hard-break policy).
2. `src/tunacode/core/agents/main.py:540-549` -- delete `check_query_satisfaction()`. Remove from `__all__` in same file. Remove import and `__all__` entry in `src/tunacode/core/agents/__init__.py`.
3. `src/tunacode/types/canonical.py:247-291` -- delete `NormalizedUsage`, `normalize_request_usage`, `_read_usage_value`, and the associated constants/comments. Remove from `__all__` in same file. Remove imports and `__all__` entries in `src/tunacode/types/__init__.py`.
4. Delete entire file `src/tunacode/core/agents/agent_components/response_state.py`. Remove any `__init__.py` references if present.

**Acceptance Tests:**
- `ruff check .` passes
- `uv run pytest` passes
- `grep -r "check_query_satisfaction" src/ tests/` returns nothing
- `grep -r "NormalizedUsage\|normalize_request_usage" src/ tests/` returns nothing
- `grep -r "model_dump" src/tunacode/ui/main.py` returns nothing

**Files touched:**
- `src/tunacode/ui/main.py`
- `src/tunacode/core/agents/main.py`
- `src/tunacode/core/agents/__init__.py`
- `src/tunacode/types/canonical.py`
- `src/tunacode/types/__init__.py`
- `src/tunacode/core/agents/agent_components/response_state.py` (delete)
- `src/tunacode/core/agents/agent_components/__init__.py` (if references exist)

### T2: Update stale config and docs (M2) -- Priority 1
Update 5 files to replace "in progress" / "in the middle of" language with hard-rip-complete language:

1. `CLAUDE.md:105` -- Replace "We are in the middle of ripping out pydantic-ai. Expect some turbulence." with "pydantic-ai has been fully removed. tinyagent is the sole agent loop. pydantic (the validation library) remains as a dependency. Do NOT reintroduce pydantic-ai under any circumstance."
2. `AGENTS.md:107` -- Replace "pydantic-ai loop removal is in progress. Expect some turbulence." with equivalent hard-rip-complete language. Must be unambiguous: the migration is done, pydantic-ai is banned.
3. `.github/dependabot.yml:23-26` -- Delete the pydantic-ai ignore block.
4. `.coderabbit.yaml` -- Remove pydantic-ai references at lines 61, 83-84, and the entire `NoSetAttrOnPydantic` check at lines 225-243.
5. `pytest.ini:35` -- Change comment from "transitive dep from pydantic-ai" to "transitive dep from opentelemetry/logfire".

**Acceptance Tests:**
- `grep -ri "middle of ripping\|in progress.*pydantic-ai" CLAUDE.md AGENTS.md` returns nothing
- `grep -r "pydantic-ai" .github/dependabot.yml` returns nothing
- `grep -c "NoSetAttrOnPydantic" .coderabbit.yaml` returns 0

**Files touched:**
- `CLAUDE.md`
- `AGENTS.md`
- `.github/dependabot.yml`
- `.coderabbit.yaml`
- `pytest.ini`

### T3: Purge orphaned caches (M3) -- Priority 2
Delete all orphaned .pyc files and mypy cache entries for deleted modules:

1. 8 files in `src/tunacode/core/agents/agent_components/__pycache__/`
2. 5 files in `src/tunacode/core/agents/__pycache__/`
3. 4 files in `src/tunacode/core/agents/resume/__pycache__/`
4. 2 files in `src/tunacode/types/__pycache__/` (pydantic_ai.cpython-*)
5. 1 file in `tests/architecture/__pycache__/` (test_pydantic_ratchet.cpython-*)
6. 4 files in `.mypy_cache/3.11/` (tunacode/types/pydantic_ai.* and logfire integrations)
7. Also delete `response_state.cpython-313.pyc` from agent_components cache (its source is being deleted in T1)

**Acceptance Tests:**
- `find . -name "*.pyc" -path "*pydantic_ai*"` returns nothing
- `find . -name "*.pyc" -path "*test_pydantic_ratchet*"` returns nothing
- No .pyc files remain for modules that have no corresponding .py source

**Files touched:** ~28 cache files (delete only, no source changes)

### T4: Final verification (M4) -- Priority 1
Run the full validation suite:

1. `ruff check .`
2. `uv run pytest`
3. Grep sweep: confirm zero pydantic-ai in active source (excluding historical docs)
4. Verify no new import errors

**Acceptance Tests:**
- All commands exit 0
- `grep -r "pydantic.ai\|pydantic-ai\|from pydantic_ai\|import pydantic_ai" src/ tests/` returns nothing (excluding comments about the completed migration)

**Dependencies:** T1, T2, T3

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| Deleting `check_query_satisfaction` breaks an import chain | Test failure | Low (grep confirmed zero consumers) | Run pytest immediately after deletion | Import error in pytest |
| `_serialize_message` change breaks edge case where non-dict slips through | Runtime crash | Very low (state.py enforces dicts) | TypeError raise is correct behavior per hard-break policy | TypeError in logs |
| .coderabbit.yaml syntax error after multi-line deletion | CI review failure | Low | Validate YAML after edit | YAML parse error |

## Test Strategy

- Existing test suite (`uv run pytest`) is the gate. No new tests needed -- these are pure deletions of verified-dead code.
- If any test references deleted symbols, fix the import (grep confirms none do).

## References

- Research doc: `memory-bank/research/2026-02-07_pydantic-ai-remnant-sweep.md`
- Hard-break enforcement: `src/tunacode/core/session/state.py:167-171`
- tinyagent loop: `src/tunacode/core/tinyagent/`

## Tickets Created (4 of 4)

| Ticket ID | Title | Priority | Status | Milestone |
|-----------|-------|----------|--------|-----------|
| tun-b488 | Delete dead runtime code (model_dump fallback, check_query_satisfaction, NormalizedUsage, ResponseState) | P1 | open | M1 |
| tun-deea | Update stale config/docs: replace pydantic-ai 'in progress' with hard-rip-complete | P1 | open | M2 |
| tun-de83 | Purge ~28 orphaned .pyc and mypy cache files for deleted modules | P2 | open | M3 |
| tun-bcae | Final verification: ruff + pytest + grep sweep | P1 | open | M4 |

## Dependencies

```
tun-b488 ──┐
tun-deea ──┼──> tun-bcae (verification gate)
tun-de83 ──┘
```

tun-bcae depends on tun-b488, tun-deea, tun-de83 (verification runs last).
tun-b488, tun-deea, tun-de83 are independent of each other (can be parallelized).
