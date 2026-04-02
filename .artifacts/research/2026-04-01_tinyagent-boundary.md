---
title: "tinyagent boundary map"
link: "tinyagent-boundary-map"
type: research
ontological_relations:
  - relates_to: [[docs/modules/utils/utils.md]]
  - relates_to: [[docs/modules/core/core.md]]
  - relates_to: [[docs/modules/tools/tools.md]]
tags: [research, tinyagent, boundary]
uuid: "b8d0d0c6-8b0d-4ff6-8f78-53f14ec7b8f5"
created_at: "2026-04-01T00:00:00-05:00"
---

## Structure
- `src/tunacode/core/types/state_structures.py:38-76` defines the in-memory conversation state as `list[AgentMessage]` and the runtime/session sub-states that carry it.
- `src/tunacode/core/agents/agent_components/agent_config.py:244-254` builds the active tool list from native tinyagent tools and applies only a concurrency wrapper.
- `src/tunacode/tools/` contains the native tinyagent tool modules referenced by the agent config; `bash.py:200-206` and `read_file.py:167-173` show the direct `AgentTool` exports.
- `src/tunacode/core/agents/main.py:104-131` serializes and deserializes tinyagent message models during the abort-cleanup path.
- `src/tunacode/core/agents/resume/sanitize.py:184-210` parses persisted dict messages for resume, validates them through the adapter, and returns typed resume-message dataclasses.
- `src/tunacode/utils/messaging/adapter.py:315-463` is the bidirectional translation layer between tinyagent message payloads and TunaCode canonical messages.

## Key Files
- `src/tunacode/utils/messaging/adapter.py:1-12` documents the boundary explicitly: in-memory runtime uses typed tinyagent models, persisted session JSON stores dicts at the serialization boundary, and canonical dataclasses sit in the middle.
- `src/tunacode/utils/messaging/adapter.py:315-343` converts tinyagent dicts or `AgentMessage` objects into `CanonicalMessage`.
- `src/tunacode/utils/messaging/adapter.py:346-463` converts canonical messages back to tinyagent dicts.
- `src/tunacode/utils/messaging/adapter.py:471-505` provides extraction helpers used by compaction and tool-history code.
- `src/tunacode/core/agents/main.py:104-131` defines `_serialize_agent_messages()` and `_deserialize_agent_messages()`, which work on tinyagent message models and dict payloads.
- `src/tunacode/core/agents/main.py:351-379` captures the abort-cleanup boundary: it serializes `session.conversation.messages`, runs resume cleanup, and deserializes back to typed tinyagent messages when cleanup changed the history.
- `src/tunacode/core/agents/main.py:497-527` converts native tool results into canonical tool-result objects before updating runtime tool state and invoking the UI callback.
- `src/tunacode/core/agents/agent_components/agent_config.py:208-255` wraps each native tool with a semaphore and returns the resulting `AgentTool` list.
- `src/tunacode/core/agents/helpers.py:57-144` parses usage payloads, extracts tool-result text, and canonicalizes native `AgentToolResult` values into TunaCode canonical tool results.
- `src/tunacode/core/agents/resume/sanitize.py:119-210` parses request, assistant, and tool-result content items from persisted dict messages and rejects unsupported roles or content types.
- `src/tunacode/core/agents/resume/sanitize.py:264-485` serializes the typed resume dataclasses back to tinyagent-style dict messages and mutates the message list during cleanup.
- `src/tunacode/ui/commands/compact.py:125-129` enforces that `/compact` operates on tinyagent message models only.
- `src/tunacode/infrastructure/cache/caches/agents.py:16-57` caches tinyagent `Agent` instances keyed by model name with version metadata.

## Patterns Found
- Native tinyagent message models are the in-memory form in `ConversationState.messages` and in request/stream processing.
- Dict payloads appear at persistence and resume boundaries, not as the primary in-memory representation.
- Canonical message dataclasses are used for normalization, extraction, and compaction helpers.
- Native tinyagent tools are registered directly as `AgentTool` objects with `execute(tool_call_id, args, signal, on_update)` handlers and `AgentToolResult` outputs.

## Dependencies
- `core/agents/main.py` imports `tinyagent.agent.Agent`, `tinyagent.agent_types.*`, `tunacode.utils.messaging.estimate_messages_tokens`, `canonicalize_tool_result`, and `resume.sanitize`.
- `core/agents/resume/sanitize.py` imports `adapter.to_canonical()` before its own structural parsing.
- `core/agents/agent_components/agent_config.py` imports the six active native tool modules directly and hands them to tinyagent.
- `core/compaction/controller.py:132-176` works on `list[AgentMessage]` and uses `estimate_messages_tokens()` from `tunacode.utils.messaging`.
- `docs/modules/utils/utils.md:37-71` states the adapter is the translation point between tinyagent dicts and canonical messages.
- `docs/modules/tools/tools.md:15-18` states the tools layer exposes native tinyagent tool contracts directly.
- `docs/modules/core/core.md:15-16,124-133` states the core layer runs the agent loop and serializes session messages as tinyagent dicts for persistence.

## Symbol Index
- `tunacode.utils.messaging.adapter.to_canonical()` at `src/tunacode/utils/messaging/adapter.py:315`
- `tunacode.utils.messaging.adapter.from_canonical()` at `src/tunacode/utils/messaging/adapter.py:442`
- `tunacode.utils.messaging.adapter.find_dangling_tool_calls()` at `src/tunacode/utils/messaging/adapter.py:495`
- `tunacode.core.agents.main._serialize_agent_messages()` at `src/tunacode/core/agents/main.py:104`
- `tunacode.core.agents.main._deserialize_agent_messages()` at `src/tunacode/core/agents/main.py:111`
- `tunacode.core.agents.main.RequestOrchestrator` at `src/tunacode/core/agents/main.py:134`
- `tunacode.core.agents.helpers.canonicalize_tool_result()` at `src/tunacode/core/agents/helpers.py:110`
- `tunacode.core.agents.resume.sanitize.sanitize_history_for_resume()` at `src/tunacode/core/agents/resume/sanitize.py:434`
- `tunacode.tools.bash.bash` at `src/tunacode/tools/bash.py:200`
- `tunacode.tools.read_file.read_file` at `src/tunacode/tools/read_file.py:167`
