# NOTES.md — PR #378 Integration Plan

## Context
- Branch: `compaction-new`
- PR: #378 — **feat: implement context compaction system with overflow retry**
- Goal: integrate reviewer feedback cleanly with small, focused diffs.

---

## Claim-by-Claim Validation (2026-02-11)

### 1) `_compact()` has hidden side effects (mutates + returns)
**Status: CONFIRMED**

Evidence:
- `src/tunacode/core/compaction/controller.py:209`
  - `_compact()` writes session state directly:
  - `self._state_manager.session.conversation.messages = retained_messages`
- `src/tunacode/core/agents/main.py:349-350`
  - Caller also sets state:
  - `compacted_history = await self._compact_history_for_request(history)`
  - `conversation.messages = compacted_history`
- Same double-write pattern also exists in manual command path:
  - `src/tunacode/ui/commands/compact.py:63`

Action:
- Make controller pure (return compacted messages only); callers own all mutation.

---

### 2) `CompactCommand` doesn’t inherit `Command`
**Status: CONFIRMED**

Evidence:
- `src/tunacode/ui/commands/compact.py:21`
  - `class CompactCommand:` (no base class)
- `src/tunacode/ui/commands/__init__.py:514`
  - registry uses `cast(Command, CompactCommand())`

Action:
- `class CompactCommand(Command)` and remove cast workaround.

---

### 3) `compact.py` imports from wrong layer (`core.ui_api`)
**Status: DISPUTED / NOT A BUG (current architecture)**

Evidence:
- `src/tunacode/ui/commands/compact.py:10`
  - imports from `tunacode.core.ui_api.messaging`
- `src/tunacode/core/ui_api/messaging.py:28-30`
  - facade comment explicitly states:
  - “UI is not allowed to import from `tunacode.utils` directly.”
  - “This facade ... preserves dependency direction.”
- `src/tunacode/core/ui_api/__init__.py`
  - dependency design: `ui -> core.ui_api -> ...`

Action:
- Keep current import unless we do a broader architecture change.

---

### 4) Compaction silently disabled for non-OpenRouter providers
**Status: MOSTLY CONFIRMED (with nuance)**

Evidence:
- `src/tunacode/core/compaction/controller.py:289-291`
  - `_build_model()` raises ValueError for non-openrouter.
- `src/tunacode/core/compaction/controller.py:197`
  - broad `except Exception` logs error and returns original messages.
- No explicit user-facing reason is emitted from controller on this path.
- `/compact` can then report generic skip:
  - `src/tunacode/ui/commands/compact.py` uses `COMPACT_SKIPPED_NOTICE` when compaction record count is unchanged.

Nuance:
- tinyagent model path is already openrouter-only (`agent_config.py`), so many non-openrouter sessions cannot run requests anyway.
- Still, fail-safe path is opaque/misleading for manual `/compact` and config edge cases.

Action:
- Add explicit notice/warning when compaction is skipped due to unsupported provider (or missing API key for summarization).

---

### 5) Unrelated pydantic-ai files in PR
**Status: CONFIRMED**

Evidence (present in PR file list):
- `memory-bank/execute/2026-02-07_18-30-00_pydantic-ai-hard-rip.md`
- `memory-bank/plan/2026-02-07_18-12-36_pydantic-ai-hard-rip.md`
- `memory-bank/research/2026-02-07_pydantic-ai-remnant-sweep.md`

Action:
- Drop from this PR or split to separate PR/commit.

---

### 6) Test coverage gaps
**Status: CONFIRMED**

Evidence:
- Compaction tests exist only in `tests/test_compaction.py` (happy-path integration + legacy load).
- No tests currently found for:
  - boundary snap-to-zero
  - explicit tool call/result split guard
  - empty message list behavior
  - summarizer failure fail-safe path
  - `_is_context_overflow_error` matching

Action:
- Add focused unit/integration tests for each missing case.

---

### 7) `_find_threshold_index` should use `<=` not `<`
**Status: DISPUTED (needs team decision)**

Evidence:
- Current code: `src/tunacode/core/compaction/summarizer.py:153`
  - `if accumulated_tokens < keep_recent_tokens: continue`
- With current logic, boundary is chosen when suffix tokens are `>= keep_recent_tokens`.
- This already satisfies “retain at least threshold” semantics.
- Changing to `<=` would retain *more* messages when exactly equal.

Action:
- Keep current behavior unless product intent is “strictly more than threshold when equal.”
- If changed, add explicit tests documenting expected equality behavior.

---

### 8) Research docs are large
**Status: CONFIRMED (size concern is valid, policy decision pending)**

Evidence:
- Large docs in this PR:
  - `memory-bank/research/2026-02-07_18-06-58_compaction-system.md` (412 lines)
  - `memory-bank/research/2026-02-10_21-29-05_compaction-system-mapping.md` (378 lines)
  - `memory-bank/plan/2026-02-11_04-15-37_compaction-system.md` (244 lines)

Action:
- Decide whether to keep in this feature PR or move to a docs/research PR.

---

## Implementation Plan (updated)

### Phase 1 — Confirmed blockers
- [ ] B1: Remove controller state mutation side effect.
- [ ] B2: Make `CompactCommand` inherit `Command`; remove cast.
- [ ] B3: Add explicit user-facing reason when compaction cannot run.

### Phase 2 — Test and hygiene
- [ ] N1: Add missing tests (boundary/tool-pair/empty/fail-safe/overflow matcher).
- [ ] N2: Decide and document threshold equality semantics (`<` vs `<=`).
- [ ] N3: Remove unrelated pydantic-ai memory-bank files from this PR.
- [ ] N4: Decide whether to trim/move large research docs.

---

## Validation Checklist
- [ ] `uv run pytest tests/test_compaction.py tests/unit/core/test_exceptions.py`
- [ ] `uv run pytest`
- [ ] `uv run ruff check --fix .`
- [ ] `uv run ruff .`

---

## Reviewer Reply Plan
When fixes are pushed, reply claim-by-claim with:
- ✅ fixed + commit SHA + file paths
- ⚖️ discussed/disputed items + rationale (for claim #3 and #7)
