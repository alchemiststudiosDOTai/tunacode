# Research -- Token Counting, Context Window & Pricing Audit

**Date:** 2026-02-11
**Phase:** Research

## Structure

| Layer | Purpose | Key Files |
|-------|---------|-----------|
| Parser | Extract usage from provider responses | `src/tunacode/core/agents/main.py:66-216` |
| Types | `UsageMetrics` dataclass | `src/tunacode/types/canonical.py:183-225` |
| State | Session accumulation (`last_call_usage`, `session_total_usage`) | `src/tunacode/core/types/state_structures.py:59-64` |
| Estimation | Heuristic token counting (4 chars/token) | `src/tunacode/utils/messaging/token_counter.py` |
| Facade | Re-exports estimation to UI layer | `src/tunacode/core/ui_api/messaging.py` |
| Compaction | Context compression when threshold exceeded | `src/tunacode/core/compaction/controller.py` |
| UI Display | Resource bar (%, model, cost) | `src/tunacode/ui/widgets/resource_bar.py`, `src/tunacode/ui/app.py:418-429` |

## Key Files

- `src/tunacode/core/agents/main.py:66-101` -> `_coerce_int()`, `_coerce_float()` defensive numeric coercion
- `src/tunacode/core/agents/main.py:104-158` -> `USAGE_PROMPT_TOKEN_KEYS`, `USAGE_COMPLETION_TOKEN_KEYS`, `USAGE_CACHED_TOKEN_KEYS`, `_first_present()`
- `src/tunacode/core/agents/main.py:161-175` -> `_parse_usage_cost()` handles scalar and dict cost shapes
- `src/tunacode/core/agents/main.py:178-216` -> `_parse_openrouter_usage()` main parser, returns `UsageMetrics | None`
- `src/tunacode/core/agents/main.py:586-611` -> `_handle_stream_turn_end()` records usage
- `src/tunacode/core/agents/main.py:626-659` -> `_record_usage_from_assistant_message()` sets `last_call_usage` and adds to `session_total_usage`
- `src/tunacode/core/agents/main.py:661-685` -> `_handle_stream_message_end()` also records usage
- `src/tunacode/core/compaction/controller.py:130-147` -> `should_compact()` threshold check
- `src/tunacode/core/compaction/controller.py:210-272` -> `_compact()` orchestration
- `src/tunacode/core/compaction/controller.py:331-356` -> `_generate_summary()` LLM call (usage not recorded)
- `src/tunacode/core/compaction/summarizer.py:43-65` -> `calculate_retention_boundary()`
- `src/tunacode/ui/widgets/resource_bar.py:39-58` -> `update_stats()` accepts `session_cost` param
- `src/tunacode/ui/app.py:418-429` -> `_update_resource_bar()` never passes `session_cost`
- `src/tunacode/types/canonical.py:183-225` -> `UsageMetrics` with `add()` for accumulation
- `src/tunacode/utils/messaging/token_counter.py:19` -> `CHARS_PER_TOKEN = 4`
- `src/tunacode/configuration/models.py:145-172` -> `get_model_context_window()`
- `src/tunacode/constants.py:31` -> `DEFAULT_CONTEXT_WINDOW = 200000`

## Patterns Found

### Two Parallel Token Systems
- **Heuristic estimation** (`len(text) // 4`): Used for context window budgeting (resource bar %, compaction threshold)
- **Provider-reported usage**: Parsed from API responses, stored in `session_total_usage`, persisted to disk
- These two systems are never compared or reconciled

### Multi-Format Usage Parser
- Priority-ordered key tuples (`USAGE_PROMPT_TOKEN_KEYS`, etc.) with `_first_present()` for first-match
- Defensive coercion handles strings, booleans, None
- 5 known shapes: OpenRouter raw, camelCase, normalized cacheRead, Alchemy Rust, OR cache_read_input_tokens

### Dual Event Recording (Defense-in-Depth)
- Both `message_end` and `turn_end` handlers call `_record_usage_from_assistant_message()`
- Intentionally added in `bb5a333d` per `.claude/debug_history/2026-02-11-rust-usage-shape-throughput-missing.md`
- No dedup guard exists -- if both events carry the same usage dict, `session_total_usage` is inflated 2x

### Compaction Threshold
- `threshold = max_tokens - 16384 (reserve) - 20000 (keep_recent)`
- For 200k window: 163,616 estimated tokens triggers compaction
- Retention boundary walks messages backwards, snaps to structurally valid split point

## Dependencies

- `core/agents/main.py` -> imports -> `types/canonical.py` (UsageMetrics)
- `core/agents/main.py` -> imports -> `core/types/state_structures.py` (UsageState via session)
- `core/compaction/controller.py` -> imports -> `utils/messaging/token_counter.py` (estimate_messages_tokens)
- `core/compaction/controller.py` -> imports -> `configuration/limits.py` (get_max_tokens)
- `ui/app.py` -> imports -> `core/ui_api/messaging.py` (estimate_messages_tokens facade)
- `ui/widgets/resource_bar.py` -> imports -> `core/ui_api/constants.py` (format strings)

## Issues Found

### 1. Potential Double-Counting (High)
- **Location**: `main.py:599-602` and `main.py:680-683`
- Both `turn_end` and `message_end` call `_record_usage_from_assistant_message()` which calls `session_total_usage.add()`
- No dedup guard (no message ID, no "already recorded" flag)
- **Severity depends on**: Whether tinyagent emits both events for the same assistant message with usage

### 2. Cost Display Always $0.00 (Medium)
- **Location**: `app.py:425-429`
- `_update_resource_bar()` never passes `session_cost` to `resource_bar.update_stats()`
- ResourceBar has full support for it (param exists, renders at line 103/117)
- `session.usage.session_total_usage.cost` is tracked and persisted but never wired to UI

### 3. Compaction Summary Usage Invisible (Low)
- **Location**: `controller.py:349-350`
- `_generate_summary()` makes LLM call, extracts content, discards usage
- Background summarization tokens/cost invisible to user

## Test Coverage

- `tests/unit/core/test_openrouter_usage_metrics.py` -- 6 tests covering all 5 parser shapes (all pass)
- `tests/unit/core/test_context_overflow_detection.py` -- overflow detection
- `tests/unit/core/test_compaction_controller_outcomes.py` -- compaction outcomes
- `tests/unit/core/test_compaction_summarizer.py` -- summarizer logic
- **Gap**: No integration test for accumulation logic (double-counting scenario)
- **Gap**: No test for cost display wiring
