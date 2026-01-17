---
title: Messaging Seams and Test Decomposition
link: messaging-seams
type: doc
path: docs/codebase-map/architecture/messaging-seams.md
depth: 2
seams: [M]
ontological_relations:
  - relates_to: [[core-agents]]
  - affects: [[utils]]
tags:
  - messaging
  - invariants
  - testing
created_at: 2026-01-17T18:46:38.209948+00:00
updated_at: 2026-01-17T18:46:38.209948+00:00
uuid: d2c31804-d9b5-4d49-afbb-7831fb0b5593
---

# Messaging Seams and Test Decomposition

## Summary
This document enumerates the messaging seams and invariants that shape a conversation turn, and
records the decomposition strategy used to build targeted tests. The approach mirrors fractional
proof decomposition (https://theorem.dev/blog/anthropic-bug-test/): start with end-to-end
properties, split them into smaller sub-properties, and verify each seam with focused property-based
tests.

## Context
Messaging logic spans request/response ordering, tool-call pairing, response state transitions,
empty-response intervention, ReAct guidance injection, and session persistence. These seams define
the contract that keeps model messages valid, replayable, and deterministic across turns.
The long-term goal is to repeat this decomposition pattern for the rest of the codebase.

## Seams
- `src/tunacode/utils/messaging/message_order.py` - Validates `[System?] [Request]+ [Response]+`
  ordering, rejects mixed system/request parts, enforces request-before-response.
- `src/tunacode/utils/messaging/message_utils.py` - Extracts content from message objects and dicts.
- `src/tunacode/core/agents/main.py` - Tool-call pairing cleanup (`_remove_dangling_tool_calls`).
- `src/tunacode/core/agents/agent_components/response_state.py` - ResponseState transitions and
  completion detection.
- `src/tunacode/core/agents/main.py` - EmptyResponseHandler and ReactSnapshotManager behavior.
- `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py` - Tool call arg
  storage/consumption (`record_tool_call_args`, `consume_tool_call_args`).
- `src/tunacode/core/state.py` - Message serialization/deserialization for session persistence.
- `src/tunacode/ui/app.py` - Session replay renders requests/responses and skips non-user prompts.

## Changes
- Encoded end-to-end messaging invariants into seam-level properties.
- Documented decomposition steps to target rare edge cases with low compute cost.
- Anchored tests to real `pydantic_ai` message classes for compatibility assurance.

## Behavioral Impact
No runtime changes. The seams list is a roadmap for tests that preserve message integrity and replay
across the agent loop.

## Related Cards
- [[conversation-turns]]
- [[utils]]
