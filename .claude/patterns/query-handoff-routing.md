---
title: Query handoff routing before main agent
status: active
date: 2026-02-25
scope: core/agents
---

## Summary

Add a small typed pre-routing step that transforms the raw user query into a compact handoff envelope for the main agent.

## Why

- Keeps routing logic isolated and fast.
- Preserves the original user query for task state and UI.
- Gives the main agent explicit intent hints (`debug`, `build`, `explain`, `general`, `command`).

## Implementation notes

- `QueryHandoff` is a frozen dataclass.
- `build_query_handoff(query)` does keyword routing and returns:
  - `original_query`
  - `route`
  - `handoff_instruction`
  - `message_for_main_agent`
- Slash commands (`/compact`, etc.) bypass wrapping and are passed through unchanged.

## Validation

- Unit tests assert route selection and command passthrough.
- `RequestOrchestrator` stores both `user_message` and routed `message` and uses the original message for `task.original_query` and empty-response follow-up.
