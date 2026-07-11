---
title: Types Layer
summary: Centralized type aliases, callback protocols, and the canonical message model shared across all layers.
read_when: Adding a new callback signature, creating a new tool, or modifying message structures.
depends_on: []
feeds_into: [configuration, infrastructure, tools, core, ui]
when_to_read:
  - Adding a new callback signature
  - Creating a new tool
  - Modifying message structures
last_updated: "2026-07-11"
---

# Types Layer

**Package:** `src/tunacode/types/`

## What

Single source of truth for every type alias, callback protocol, and data structure used across layers. No runtime logic lives here -- only definitions.

## Key Files

| File              | Purpose |
|-------------------|---------|
| `__init__.py`     | Re-exports everything from the sub-modules below. Import from `tunacode.types` directly. |
| `base.py`         | Scalar aliases (`FilePath`, `ModelName`, `TokenCount`, `ToolCallId`, etc.), tool aliases (`ToolArgs`, `ToolResult` from tinyagent), and the typed user-config schema (`UserConfig`, `UserSettings`, `EnvConfig`, `RipgrepSettings`). |
| `callbacks.py`    | Async callback signatures (`StreamingCallback`, `ToolCallback`, `ToolResultCallback`, `ToolStartCallback`, `NoticeCallback`) and protocols (`StreamResultProtocol`, `ToolCallPartProtocol`). |
| `canonical.py`    | The canonical message model: `CanonicalMessage`, `CanonicalPart`, `CanonicalToolCall`, `CanonicalToolCallPart`, `CanonicalToolReturnPart`, `UsageMetrics`. Enums: `MessageRole`, `PartKind`, `ToolCallStatus`. |
| `dataclasses.py`  | Value objects: `ModelPricing`, `TokenUsage`, `CostBreakdown`. |
| `models_registry.py` | TypedDict schema and public aliases for the bundled registry document: `ModelsRegistryDocument`, `ModelConfig`, `ModelRegistry`, and supporting registry metadata types. |

## How

Every other layer imports from `tunacode.types`. The `__init__.py` re-export list is the public API surface. `ModelsRegistryDocument`, `ModelConfig`, and `ModelRegistry` are public aliases sourced from `models_registry.py`, while `ModelPricing`, `TokenUsage`, and `CostBreakdown` remain dataclasses. The configuration layer also publishes its persisted schema through `UserConfig`, `UserSettings`, `EnvConfig`, `RipgrepSettings`, and `LspSettings`, so configuration, core, and UI code can share one validated contract. If a type is not in `__all__`, it is internal.

`CanonicalMessage` / `CanonicalToolCall` form the domain vocabulary for messages flowing between the agent loop, tools, compaction, and the UI.

`UsageMetrics` tracks input/output tokens and cost per call, with an `.add()` method for session accumulation.

The user-config TypedDicts describe the exact persisted shape of `~/.config/tunacode.json` after defaults are merged:

- `UserConfig` holds `default_model`, `recent_models`, `env`, and nested `settings`.
- `UserSettings` holds execution, UI, and limit knobs such as `request_delay`, `global_request_timeout`, `max_command_output`, `max_tokens`, and `stream_agent_text`.
- `RipgrepSettings` and `LspSettings` model the nested subsystem-specific settings blocks.

## Why

Keeping types in a leaf package with zero runtime dependencies eliminates circular imports. The rest of the codebase can always import from `tunacode.types` without worrying about import order.
