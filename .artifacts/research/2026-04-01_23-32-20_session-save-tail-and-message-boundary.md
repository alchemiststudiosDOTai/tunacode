---
title: "session save tail and message boundary map"
link: "session-save-tail-and-message-boundary-map"
type: research
ontological_relations:
  - relates_to: [[docs/modules/core/core.md]]
  - relates_to: [[docs/modules/ui/ui.md]]
  - relates_to: [[docs/modules/utils/utils.md]]
  - relates_to: [[docs/architecture/patterns/agent-message-serialization.md]]
tags: [research, session, persistence, ui, messaging]
uuid: "a4b7f6f1-1a94-4cfa-b495-849a82929b71"
created_at: "2026-04-01T23:32:20.690411-05:00"
---

## Structure
- `src/tunacode/core/session/` contains the persisted session state manager; `state.py:162-342` defines the session file path, message serialization/deserialization helpers, and `save_session()`.
- `src/tunacode/core/types/state_structures.py:38-76` defines the in-memory conversation/runtime/usage dataclasses used by `SessionState`.
- `src/tunacode/utils/messaging/` contains the message adapter and heuristic token counter; `adapter.py:315-337` is the tinyagent→canonical conversion path and `token_counter.py:35-66` is the per-message/per-history token scan.
- `src/tunacode/core/ui_api/messaging.py:29-36` is the UI-facing facade that forwards token estimation into `tunacode.utils.messaging`.
- `src/tunacode/ui/app.py:405-445` finalizes a request, renders the response panel, updates the resource bar, and then auto-saves the session.
- `src/tunacode/ui/renderers/agent_response.py:112-159` renders only the finalized response content and throughput text.
- `src/tunacode/core/compaction/controller.py:148-149,324-327` also reuses the same token estimator for threshold checks and compaction record updates.
- `docs/architecture/patterns/agent-message-serialization.md:1-152` documents the message-shape boundaries between tinyagent models, canonical dataclasses, and dict payloads.

## Key Files
- `AGENTS.md:110-115` records the repository rule: use tinyagent models directly in memory and keep dict payloads at real boundaries.
- `src/tunacode/core/types/state_structures.py:39-45` defines `ConversationState.messages` as `list[AgentMessage]` with a separate `total_tokens` field.
- `src/tunacode/core/session/state.py:169-173` serializes every in-memory tinyagent message with `message.model_dump(exclude_none=True)`.
- `src/tunacode/core/session/state.py:318-342` rebuilds the full `session_data` dict and writes it with `json.dump(..., indent=2)` inside `save_session()`.
- `src/tunacode/ui/app.py:430-445` awaits `self.state_manager.save_session()` after each completed request and logs `save_session_ms` plus `message_count`.
- `src/tunacode/ui/lifecycle.py:35-36` also saves the session during app unmount.
- `src/tunacode/ui/app.py:663-698` computes estimated conversation tokens by calling `_estimate_conversation_tokens(conversation.messages)` and forwarding to `core.ui_api.messaging.estimate_messages_tokens()`.
- `src/tunacode/ui/app.py:733-759` recomputes estimated tokens during `_update_resource_bar()` and, when the context panel is visible, calls `_refresh_context_panel()` which also estimates tokens at `src/tunacode/ui/app.py:659-676`.
- `src/tunacode/utils/messaging/token_counter.py:3-11` states that the token counter supports typed tinyagent messages in memory and JSON dicts at persistence boundaries.
- `src/tunacode/utils/messaging/token_counter.py:35-66` converts non-canonical messages through `to_canonical()` and loops the full message sequence to sum estimated tokens.
- `src/tunacode/utils/messaging/adapter.py:315-337` converts an `AgentMessage` or dict payload into `CanonicalMessage`, using `message.model_dump(exclude_none=True)` for non-dict messages at `adapter.py:308-312`.
- `src/tunacode/core/compaction/controller.py:148-149` estimates total history tokens in `should_compact()` before each compaction decision.
- `src/tunacode/core/compaction/controller.py:324-327` re-estimates `tokens_before` and `retained_tokens` when writing a new `CompactionRecord`.
- `src/tunacode/core/agents/main.py:320-322` uses `estimate_messages_tokens(conversation.messages)` when raising `ContextOverflowError`.
- `src/tunacode/ui/renderers/agent_response.py:112-145` formats the final response panel from the latest response content, output-token count, and duration only.

## Patterns Found
- In-memory conversation history is typed as tinyagent `AgentMessage` objects in `ConversationState.messages` (`src/tunacode/core/types/state_structures.py:42`).
- Session persistence converts that typed history to JSON dictionaries at save time in `StateManager._serialize_messages()` (`src/tunacode/core/session/state.py:169-173`) and converts dicts back to tinyagent models in `_deserialize_messages()` (`src/tunacode/core/session/state.py:206-219`).
- `save_session()` constructs the full persistence payload before the threaded file write begins; the `session_data` dict is assembled at `src/tunacode/core/session/state.py:325-338`, and the thread handoff occurs at `src/tunacode/core/session/state.py:341-342`.
- The token estimator is a full-history sum: `estimate_messages_tokens()` iterates every message (`src/tunacode/utils/messaging/token_counter.py:60-66`), and `estimate_message_tokens()` canonicalizes each non-canonical message first (`src/tunacode/utils/messaging/token_counter.py:42`).
- The canonicalization step for tinyagent messages uses `model_dump(exclude_none=True)` via `_coerce_agent_message_dict()` (`src/tunacode/utils/messaging/adapter.py:308-312`).
- UI token display uses estimator results rather than `ConversationState.total_tokens`; repository search `rg -n "conversation\.total_tokens" src/tunacode tests docs` returned no matches, while `ConversationState.total_tokens` is declared at `src/tunacode/core/types/state_structures.py:44` and referenced in a comment at `src/tunacode/ui/commands/clear.py:27`.
- `_update_resource_bar()` estimates tokens once at `src/tunacode/ui/app.py:739-748`; if the context panel is visible, it then triggers `_refresh_context_panel()` (`src/tunacode/ui/app.py:758-759`), which estimates tokens again at `src/tunacode/ui/app.py:663-676`.
- The same token-count helper is reused outside the UI in compaction and overflow paths (`src/tunacode/core/compaction/controller.py:148-149,324-327`; `src/tunacode/core/agents/main.py:320-322`).
- Final response rendering is scoped to one response string and metadata. `render_agent_response()` does not iterate the full conversation; it creates a `Markdown(content)` viewport and optional throughput status (`src/tunacode/ui/renderers/agent_response.py:136-145`).
- Additional `save_session()` call sites exist in UI lifecycle and commands: `src/tunacode/ui/lifecycle.py:35-36`, `src/tunacode/ui/commands/skills.py:75,88`, `src/tunacode/ui/commands/resume.py:128`, `src/tunacode/ui/commands/clear.py:52`, and `src/tunacode/ui/commands/compact.py:92`.

## Dependencies
- `src/tunacode/ui/app.py` imports `AgentMessage` from `tinyagent.agent_types` and calls `tunacode.core.ui_api.messaging.estimate_messages_tokens()` from `_estimate_conversation_tokens()` (`src/tunacode/ui/app.py:692-698`).
- `src/tunacode/core/ui_api/messaging.py:8-12` depends on `tinyagent.agent_types`, `tunacode.types.canonical`, and forwards to `tunacode.utils.messaging`.
- `src/tunacode/utils/messaging/token_counter.py:19-22` depends on `tinyagent.agent_types`, `tunacode.types.canonical`, and `tunacode.utils.messaging.adapter.to_canonical()`.
- `src/tunacode/utils/messaging/adapter.py:19-37` depends on tinyagent message types plus canonical message dataclasses from `tunacode.types.canonical`.
- `src/tunacode/core/session/state.py:22-26` depends on configuration defaults, public types, canonical `UsageMetrics`, and core state structures.
- `src/tunacode/core/compaction/controller.py` imports `estimate_messages_tokens` from `tunacode.utils.messaging` and writes compaction metadata back through `state_manager.session.compaction`.
- `src/tunacode/core/agents/main.py:51-76` depends on `estimate_messages_tokens`, compaction controller/types, logging, state protocols, and resume sanitization.
- `docs/architecture/patterns/agent-message-serialization.md` maps the same boundary in prose: tinyagent models, canonical dataclasses, and dict payloads participate in the current message flow.

## Symbol Index
- `tunacode.core.session.state.SessionState` — `src/tunacode/core/session/state.py:35`
- `tunacode.core.session.state.StateManager` — `src/tunacode/core/session/state.py:77`
- `tunacode.core.session.state.StateManager._serialize_messages()` — `src/tunacode/core/session/state.py:169`
- `tunacode.core.session.state.StateManager.save_session()` — `src/tunacode/core/session/state.py:318`
- `tunacode.core.types.state_structures.ConversationState` — `src/tunacode/core/types/state_structures.py:39`
- `tunacode.core.ui_api.messaging.estimate_messages_tokens()` — `src/tunacode/core/ui_api/messaging.py:29`
- `tunacode.utils.messaging.token_counter.estimate_message_tokens()` — `src/tunacode/utils/messaging/token_counter.py:35`
- `tunacode.utils.messaging.token_counter.estimate_messages_tokens()` — `src/tunacode/utils/messaging/token_counter.py:60`
- `tunacode.utils.messaging.adapter.to_canonical()` — `src/tunacode/utils/messaging/adapter.py:315`
- `tunacode.utils.messaging.adapter.get_content()` — `src/tunacode/utils/messaging/adapter.py:471`
- `tunacode.core.agents.main.RequestOrchestrator` — `src/tunacode/core/agents/main.py:134`
- `tunacode.core.agents.main.RequestOrchestrator._persist_agent_messages()` — `src/tunacode/core/agents/main.py:351`
- `tunacode.ui.renderers.agent_response.render_agent_response()` — `src/tunacode/ui/renderers/agent_response.py:112`
- `tunacode.ui.lifecycle.AppLifecycle` — `src/tunacode/ui/lifecycle.py:21`
