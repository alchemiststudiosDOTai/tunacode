# Research – Token Counting Logic
**Date:** 2026-02-01
**Phase:** Research

## Structure
- `src/tunacode/utils/messaging/` (adapter + token_counter)
- `src/tunacode/types/canonical.py` (canonical message + usage types)
- `src/tunacode/core/state.py` (session token count computation + persistence)
- `src/tunacode/core/types/state_structures.py` (ConversationState.total_tokens)
- `src/tunacode/core/agents/main.py` (token count refresh after message changes)
- `src/tunacode/core/agents/resume/` (prune/summary/filter using heuristic tokens)
- `src/tunacode/core/agents/agent_components/orchestrator/` (provider usage tokens)
- `src/tunacode/ui/app.py` (resource bar + response panel token display)
- `src/tunacode/ui/commands/__init__.py` (clear command preserves total_tokens)

## Key Files
- `src/tunacode/utils/messaging/token_counter.py:12-129` defines heuristic constants (`CHARS_PER_TOKEN=4`), `MessageTokenCacheEntry`, `MessageTokenCache`, `estimate_tokens`, `estimate_tokens_from_length`, `get_message_text_length`.
  - `MessageTokenCache.rebuild_total()` (line 34) iterates `messages`, uses `id(message)` as the cache key, calls `_get_or_update`, sums token counts, then `_prune`.
  - `_get_or_update()` (line 52) calls `get_message_text_length()` then `estimate_tokens_from_length()`.
  - `_prune()` (line 65) removes cache entries not in active ids.
  - `estimate_tokens()` (line 73) uses `len(text)` then `estimate_tokens_from_length()`.
  - `get_message_text_length()` (line 99) canonicalizes and computes part length.
- `src/tunacode/utils/messaging/adapter.py:57-205` defines `_get_parts()` and `to_canonical()` used by `token_counter` to normalize messages into `CanonicalMessage`.
- `src/tunacode/types/canonical.py:104-133` defines `CanonicalMessage` and `get_text_content()`; `UsageMetrics` at lines 184-214; `NormalizedUsage` at lines 260-289.
- `src/tunacode/core/state.py:65-75` `SessionState.update_token_count()` computes `conversation.total_tokens` via `MessageTokenCache.rebuild_total`. `adjust_token_count()` is defined at lines 72-75. Session persistence stores `total_tokens` at lines 273 and loads at lines 321-322.
- `src/tunacode/core/types/state_structures.py:24-33` `ConversationState.total_tokens` and `max_tokens` fields.
- `src/tunacode/core/agents/main.py:222,303,350,583,590,594,598` call `session.update_token_count()` after message list changes and cleanup.
- `src/tunacode/core/agents/resume/prune.py:100-224` uses `estimate_tokens` to compute token counts for tool return parts and pruning thresholds.
- `src/tunacode/core/agents/resume/summary.py:97-201` uses `estimate_tokens` to compute message totals for compaction and summary `token_count`.
- `src/tunacode/core/agents/resume/filter.py:52-76` `prepare_history()` combines summary filtering and pruning and returns `tokens_reclaimed`.
- `src/tunacode/core/agents/agent_components/orchestrator/usage_tracker.py:15-53` `update_usage()` reads provider usage via `normalize_request_usage()` and updates `UsageMetrics`.
- `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py:217-258` calls `update_usage()` on `model_response`.
- `src/tunacode/ui/app.py:217-236` uses `session.usage.last_call_usage.completion_tokens` for response metadata; `src/tunacode/ui/app.py:365-376` uses `conversation.total_tokens` for the resource bar.
- `src/tunacode/ui/commands/__init__.py:77-105` clear command preserves `conversation.total_tokens` and resets usage metrics.

## Patterns Found
- **Conversation token total (heuristic)**:
  - `SessionState.update_token_count()` → `MessageTokenCache.rebuild_total()` → `_get_or_update()` → `get_message_text_length()` → `_canonicalize_message()` → `to_canonical()` → `_canonical_text_length()`; then `estimate_tokens_from_length()` divides character length by `CHARS_PER_TOKEN`.
  - Cache keys are `id(message)` and `_prune()` removes entries not in the current message list.
- **Heuristic token estimates in resume/compaction**:
  - `estimate_tokens()` is called in `resume/prune.py` (tool-output pruning) and `resume/summary.py` (summary threshold + summary token_count).
- **Provider usage tokens**:
  - `orchestrator.update_usage()` reads `model_response.usage`, normalizes it via `normalize_request_usage()`, and updates `session.usage.last_call_usage` and `session.usage.session_total_usage`.
- **Display**:
  - Resource bar reads `conversation.total_tokens` (heuristic count).
  - Response panels read `session.usage.last_call_usage.completion_tokens` (provider usage).

## Dependencies
- `core/state.py` imports `MessageTokenCache` from `tunacode.utils.messaging`.
- `utils/messaging/token_counter.py` imports `CanonicalMessage` and `to_canonical`.
- `core/agents/resume/prune.py` and `core/agents/resume/summary.py` import `estimate_tokens`.
- `core/agents/agent_components/orchestrator/usage_tracker.py` imports `UsageMetrics` and `normalize_request_usage` from `types/canonical.py`.
- UI modules read `conversation.total_tokens` and `session.usage.last_call_usage`.

## Symbol Index
- `tunacode.utils.messaging.token_counter` exports `MessageTokenCache`, `estimate_tokens`, `get_message_text_length` (`utils/messaging/__init__.py:16-20`).
- `tunacode.core.agents.resume` exports `prune_old_tool_outputs`, `filter_compacted`, `prepare_history`, `SummaryMessage`, `should_compact`, `generate_summary` (`core/agents/resume/__init__.py:15-41`).
- `tunacode.core.agents.agent_components.orchestrator.usage_tracker` exports `update_usage` (`usage_tracker.py:15`).
- `tunacode.types.canonical` exports `CanonicalMessage`, `UsageMetrics`, `NormalizedUsage`, `normalize_request_usage` (`types/canonical.py:104-319`).
