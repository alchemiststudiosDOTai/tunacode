---
title: "agent_streaming.py codebase-locator findings"
link: "agent-streaming-locator"
type: research
ontological_relations:
  - relates_to: [[agent-core-research]]
tags: [research, agent_streaming]
uuid: "agent_streaming_locator_$(date +%s)"
created_at: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---

## Structure
- Target file path: `src/tunacode/core/agents/agent_components/agent_streaming.py`.
- Directory `src/tunacode/core/agents/` contains:
  - `src/tunacode/core/agents/main.py`
  - `src/tunacode/core/agents/helpers.py`
  - `src/tunacode/core/agents/__init__.py`
  - `src/tunacode/core/agents/agent_components/agent_config.py`
  - `src/tunacode/core/agents/agent_components/agent_helpers.py`
  - `src/tunacode/core/agents/agent_components/agent_session_config.py`
  - `src/tunacode/core/agents/agent_components/__init__.py`
  - `src/tunacode/core/agents/agent_components/agent_streaming.py`
  - `src/tunacode/core/agents/resume/sanitize.py`
  - `src/tunacode/core/agents/resume/sanitize_debug.py`
  - `src/tunacode/core/agents/resume/__init__.py`

## Key File Map
- `src/tunacode/core/agents/agent_components/agent_streaming.py:57` -> defines class `AgentStreamMixin`.
- `src/tunacode/core/agents/main.py:50` -> class `RequestOrchestrator` subclasses `AgentStreamMixin`.
- `src/tunacode/core/agents/helpers.py:36` -> defines shared dataclass `_TinyAgentStreamState`.
- `src/tunacode/core/agents/agent_components/__init__.py:11` -> exports package-level functions (no stream mixin export).
- `src/tunacode/core/agents/__init__.py:4` -> package exports `get_or_create_agent`, `invalidate_agent_cache`, and `process_request`.

## Dependency Links
- `src/tunacode/core/agents/agent_components/agent_streaming.py:35` imports `tunacode.core.agents.agent_components` as `ac`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:37` imports `_TinyAgentStreamState` and helper functions from `tunacode.core.agents.helpers`.
- `src/tunacode/core/agents/agent_components/agent_streaming.py:95` uses `_TinyAgentStreamState` state fields from `helpers._TinyAgentStreamState`.
- `src/tunacode/core/agents/main.py:37` imports `AgentStreamMixin` from `agent_streaming`.
- `src/tunacode/core/agents/main.py:50` -> `RequestOrchestrator(AgentStreamMixin)` indicates direct mixin composition.
- `src/tunacode/core/agents/main.py:140` calls `_run_stream` during normal flow.
- `src/tunacode/core/agents/main.py:214` calls `_run_stream` in overflow-retry flow.
- `src/tunacode/ui/app.py:338` imports `process_request` from `tunacode.core.agents.main` and runs it in `_process_request`.

## Notes
- No additional direct imports of `agent_streaming` were found outside `src/tunacode/core/agents/main.py` when searching `src/tunacode/core`.
- No direct re-export of `AgentStreamMixin` appears in `src/tunacode/core/agents/agent_components/__init__.py`.
