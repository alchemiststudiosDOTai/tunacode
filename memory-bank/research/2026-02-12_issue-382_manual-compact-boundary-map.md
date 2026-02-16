# Research – Issue #382 Manual `/compact` Boundary Flow
**Date:** 2026-02-12
**Phase:** Research

## Structure
- `src/tunacode/ui/commands/`
  - `compact.py` — manual `/compact` command implementation (`src/tunacode/ui/commands/compact.py:1`)
  - `__init__.py` — command registry includes `"compact": CompactCommand()` (`src/tunacode/ui/commands/__init__.py:514`)
- `src/tunacode/core/compaction/`
  - `controller.py` — compaction orchestration and outcome notices (`src/tunacode/core/compaction/controller.py:88`)
  - `summarizer.py` — retention boundary and transcript serialization (`src/tunacode/core/compaction/summarizer.py:37`)
  - `types.py` — compaction statuses, reasons, and dataclasses (`src/tunacode/core/compaction/types.py:18`)
  - `prompts.py` — summary prompt templates (`src/tunacode/core/compaction/prompts.py:1`)
- `src/tunacode/core/agents/`
  - `main.py` — request-time auto compaction and overflow retry force compaction (`src/tunacode/core/agents/main.py:358`, `src/tunacode/core/agents/main.py:378`)
  - `agent_components/agent_config.py` — tinyagent `transform_context` compaction path (`src/tunacode/core/agents/agent_components/agent_config.py:288`)
- `src/tunacode/core/session/`
  - `state.py` — session stores `compaction` record and `_compaction_controller` cache (`src/tunacode/core/session/state.py:41`, `src/tunacode/core/session/state.py:61`)
- `tests/`
  - `tests/unit/core/test_compaction_controller_outcomes.py` — force_compact outcome contracts (`tests/unit/core/test_compaction_controller_outcomes.py:79`)
  - `tests/unit/core/test_compaction_summarizer.py` — retention boundary policy tests (`tests/unit/core/test_compaction_summarizer.py:75`)
  - `tests/test_compaction.py` — integration flow test (`tests/test_compaction.py:89`)

## Key Files
- `src/tunacode/ui/commands/compact.py:28` → `CompactCommand`
- `src/tunacode/ui/commands/compact.py:35` → `CompactCommand.execute`
- `src/tunacode/ui/commands/compact.py:58` → manual path calls `controller.force_compact(...)`
- `src/tunacode/ui/commands/compact.py:24` → `COMPACT_SKIPPED_NOTICE = "Compaction skipped (no eligible boundary)."`
- `src/tunacode/ui/commands/compact.py:73` → calls `build_compaction_notice(compaction_outcome)`
- `src/tunacode/ui/commands/compact.py:75` → emits `COMPACT_SKIPPED_NOTICE` when notice builder returns `None`

- `src/tunacode/core/compaction/controller.py:148` → `check_and_compact(...)`
- `src/tunacode/core/compaction/controller.py:175` → `force_compact(...)`
- `src/tunacode/core/compaction/controller.py:184` → `force_compact` delegates to `check_and_compact(..., force=True, allow_threshold=True)`
- `src/tunacode/core/compaction/controller.py:209` → `_compact(...)`
- `src/tunacode/core/compaction/controller.py:216` → computes `boundary = self._summarizer.calculate_retention_boundary(...)`
- `src/tunacode/core/compaction/controller.py:219` → logs skip with reason `COMPACTION_REASON_NO_VALID_BOUNDARY`
- `src/tunacode/core/compaction/controller.py:220` → returns skip outcome for `no_valid_boundary`
- `src/tunacode/core/compaction/controller.py:468` → `build_compaction_notice(...)`

- `src/tunacode/core/compaction/summarizer.py:43` → `calculate_retention_boundary(...)`
- `src/tunacode/core/compaction/summarizer.py:145` → `_find_threshold_index(...)`
- `src/tunacode/core/compaction/summarizer.py:169` → `_snap_to_valid_boundary(...)`
- `src/tunacode/core/compaction/summarizer.py:175` → `_is_valid_boundary(...)`
- `src/tunacode/core/compaction/summarizer.py:217` → assistant boundary validity depends on `stop_reason is not None`
- `src/tunacode/core/compaction/summarizer.py:221` → tool-result message role check

- `src/tunacode/core/compaction/types.py:27` → `COMPACTION_REASON_NO_VALID_BOUNDARY`
- `src/tunacode/core/compaction/types.py:68` → `CompactionOutcome`
- `src/tunacode/core/compaction/types.py:84` → `CompactionRecord`

- `src/tunacode/core/agents/main.py:358` → `_compact_history_for_request(...)` calls `check_and_compact(...)`
- `src/tunacode/core/agents/main.py:364` → auto path callsite
- `src/tunacode/core/agents/main.py:378` → `_force_compact_history(...)`
- `src/tunacode/core/agents/main.py:383` → force path callsite
- `src/tunacode/core/agents/main.py:352` → compaction notice creation via `build_compaction_notice(...)`

- `src/tunacode/core/agents/agent_components/agent_config.py:288` → `_build_transform_context(...)`
- `src/tunacode/core/agents/agent_components/agent_config.py:297` → `check_and_compact(...)` call in transform_context
- `src/tunacode/core/agents/agent_components/agent_config.py:301` → `allow_threshold=False`
- `src/tunacode/core/agents/agent_components/agent_config.py:303` → `inject_summary_message(...)`

- `tests/unit/core/test_compaction_controller_outcomes.py:79` → `test_force_compact_empty_history_returns_no_boundary_skip`
- `tests/unit/core/test_compaction_controller_outcomes.py:93` → expects `COMPACTION_REASON_NO_VALID_BOUNDARY`
- `tests/unit/core/test_compaction_summarizer.py:75` → `test_retention_boundary_snaps_to_zero_when_no_valid_boundary_exists`

## Patterns Found
- **Manual command entry pattern**
  - `src/tunacode/ui/commands/__init__.py:514` (`"compact": CompactCommand()`)
  - `src/tunacode/ui/commands/compact.py:35` (`execute` command handler)

- **Manual compaction invocation pattern**
  - `src/tunacode/ui/commands/compact.py:58` (`controller.force_compact(...)`)
  - `src/tunacode/core/compaction/controller.py:175` (`force_compact`)
  - `src/tunacode/core/compaction/controller.py:184` (`force_compact` delegates to `check_and_compact`)

- **Boundary gate pattern**
  - `src/tunacode/core/compaction/controller.py:216` (`calculate_retention_boundary`)
  - `src/tunacode/core/compaction/controller.py:219` / `:220` (`no_valid_boundary` skip branch)
  - `src/tunacode/core/compaction/summarizer.py:43` (`calculate_retention_boundary`)
  - `src/tunacode/core/compaction/summarizer.py:175` (`_is_valid_boundary`)

- **User-facing skip message propagation pattern**
  - `src/tunacode/ui/commands/compact.py:73` (`build_compaction_notice`)
  - `src/tunacode/ui/commands/compact.py:75` (fallback `COMPACT_SKIPPED_NOTICE`)
  - `src/tunacode/core/compaction/controller.py:468` (`build_compaction_notice` implementation)

- **Automatic/background compaction path pattern**
  - `src/tunacode/core/agents/main.py:364` (`check_and_compact` in request flow)
  - `src/tunacode/core/agents/agent_components/agent_config.py:297` (`check_and_compact` in transform_context)
  - `src/tunacode/core/agents/agent_components/agent_config.py:301` (`allow_threshold=False`)

## Dependencies
- `src/tunacode/ui/commands/compact.py:9` → imports `tunacode.core.compaction.controller`
- `src/tunacode/ui/commands/compact.py:14` → imports `COMPACTION_STATUS_COMPACTED` from `tunacode.core.compaction.types`
- `src/tunacode/ui/commands/compact.py:15` → imports `estimate_messages_tokens` from `tunacode.core.ui_api.messaging`

- `src/tunacode/core/compaction/controller.py:23` → imports `ContextSummarizer` from `tunacode.core.compaction.summarizer`
- `src/tunacode/core/compaction/controller.py:24` → imports compaction constants and dataclasses from `tunacode.core.compaction.types`
- `src/tunacode/core/compaction/controller.py:10` / `:11` → imports tinyagent message/model stream primitives

- `src/tunacode/core/compaction/summarizer.py:14` → imports prompt templates from `tunacode.core.compaction.prompts`
- `src/tunacode/core/compaction/summarizer.py:12` → imports token estimation and content helpers from `tunacode.utils.messaging`

- `src/tunacode/core/agents/main.py:35` → imports compaction controller utilities
- `src/tunacode/core/agents/main.py:41` → imports `CompactionOutcome`
- `src/tunacode/core/agents/agent_components/agent_config.py:44` → imports `get_or_create_compaction_controller`

- `src/tunacode/core/session/state.py:21` → imports `CompactionRecord`
- `src/tunacode/core/session/state.py:41` → session field `compaction: CompactionRecord | None`
- `src/tunacode/core/session/state.py:61` → session runtime cache `_compaction_controller`

## Symbol Index
- `src/tunacode/ui/commands/compact.py:28` → `CompactCommand`
- `src/tunacode/ui/commands/compact.py:35` → `CompactCommand.execute(self, app, args)`
- `src/tunacode/ui/commands/compact.py:92` → `_coerce_history(messages)`

- `src/tunacode/core/compaction/controller.py:88` → `CompactionController`
- `src/tunacode/core/compaction/controller.py:119` → `set_status_callback(...)`
- `src/tunacode/core/compaction/controller.py:124` → `reset_request_state(...)`
- `src/tunacode/core/compaction/controller.py:129` → `should_compact(...)`
- `src/tunacode/core/compaction/controller.py:148` → `check_and_compact(...)`
- `src/tunacode/core/compaction/controller.py:175` → `force_compact(...)`
- `src/tunacode/core/compaction/controller.py:192` → `inject_summary_message(...)`
- `src/tunacode/core/compaction/controller.py:209` → `_compact(...)`
- `src/tunacode/core/compaction/controller.py:442` → `get_or_create_compaction_controller(state_manager)`
- `src/tunacode/core/compaction/controller.py:457` → `apply_compaction_messages(state_manager, messages)`
- `src/tunacode/core/compaction/controller.py:468` → `build_compaction_notice(outcome)`

- `src/tunacode/core/compaction/summarizer.py:37` → `ContextSummarizer`
- `src/tunacode/core/compaction/summarizer.py:43` → `calculate_retention_boundary(...)`
- `src/tunacode/core/compaction/summarizer.py:67` → `serialize_messages(...)`
- `src/tunacode/core/compaction/summarizer.py:95` → `summarize(...)`
- `src/tunacode/core/compaction/summarizer.py:145` → `_find_threshold_index(...)`
- `src/tunacode/core/compaction/summarizer.py:169` → `_snap_to_valid_boundary(...)`
- `src/tunacode/core/compaction/summarizer.py:175` → `_is_valid_boundary(...)`

- `src/tunacode/core/compaction/types.py:47` → `__all__`
- `src/tunacode/core/compaction/types.py:68` → `CompactionOutcome`
- `src/tunacode/core/compaction/types.py:84` → `CompactionRecord`

## Structural Script Availability (Observed)
- `scripts/structure-map.sh` → command not found in repo (`bash` exit code 127)
- `scripts/ast-scan.sh` → command not found in repo (`bash` exit code 127)
- `scripts/symbol-index.sh` → command not found in repo (`bash` exit code 127)
