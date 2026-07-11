---
title: Types Layer
summary: Centralized type aliases, callback protocols, per-tool argument schemas, and usage metrics shared across all layers.
read_when: Adding a new callback signature, creating a new tool, or changing a tool's argument schema.
depends_on: []
feeds_into: [configuration, infrastructure, tools, core, ui]
when_to_read:
  - Adding a new callback signature
  - Creating a new tool or changing its argument schema
  - Working with usage metrics or the models registry
last_updated: "2026-07-11"
---

# Types Layer

**Package:** `src/tunacode/types/`

## What

Single source of truth for every type alias, callback protocol, and data structure used across layers. No runtime logic lives here -- only definitions (plus the small `UsageCost` / `UsageMetrics` value objects in `__init__.py`).

## Key Files

| File              | Purpose |
|-------------------|---------|
| `__init__.py`     | Re-exports everything from the sub-modules below and defines `UsageCost` / `UsageMetrics`. Import from `tunacode.types` directly. |
| `base.py`         | Scalar aliases (`FilePath`, `ModelName`, `TokenCount`, `ToolCallId`, etc.), tool aliases (`ToolArgs`, `ToolResult` -- re-exported from tinyagent's `JsonObject` / `AgentToolResult`), and the typed user-config schema (`UserConfig`, `UserSettings`, `EnvConfig`, `RipgrepSettings`). |
| `callbacks.py`    | Callback signatures (`StreamingCallback`, `ToolCallback`, `ToolResultCallback`, `ToolStartCallback`, `NoticeCallback`) and protocols (`StreamResultProtocol`, `ToolCallPartProtocol`). |
| `tool_args.py`    | Per-tool argument schemas (`BashArgs`, `ReadFileArgs`, `WriteFileArgs`, `WebFetchArgs`, `HashlineEditArgs`). TypedDicts with `total=False`; declare the JSON keys each tool renderer reads from the model's tool call. |
| `dataclasses.py`  | Value objects: `ModelPricing`, `TokenUsage`, `CostBreakdown`. |
| `models_registry.py` | TypedDict schema and public aliases for the bundled registry document: `ModelsRegistryDocument`, `ModelConfig`, `ModelRegistry`, and supporting registry metadata types. |

## How

Every other layer imports from `tunacode.types`. The `__init__.py` re-export list is the public API surface.

There is no tunacode-local message model: agent messages are tinyagent's pydantic models (`AgentMessage` and friends), and `ToolArgs` / `ToolResult` alias tinyagent's `JsonObject` / `AgentToolResult`. See `docs/architecture/types-and-io-interfaces.md` for the full data-boundary map.

Tool arguments flow untyped (`ToolArgs`) from the model's tool call through the event stream to the UI; each tool renderer narrows to its schema from `tool_args.py` at `parse_result` (`cast(ReadFileArgs, args or {})`). The schemas use `total=False` because model output is untrusted -- every key may be missing, so readers keep defensive `.get()` defaults. Adding a tool with new arguments means adding its TypedDict here.

`UsageMetrics` tracks input/output tokens and cost per call, with an `.add()` method for session accumulation; its `to_dict()` / `from_dict()` shape is what `session_total_usage` stores in the session file.

The user-config TypedDicts describe the exact persisted shape of `~/.config/tunacode.json` after defaults are merged:

- `UserConfig` holds `default_model`, `recent_models`, `env`, and nested `settings`.
- `UserSettings` holds execution, UI, and limit knobs such as `request_delay`, `global_request_timeout`, `max_command_output`, `max_tokens`, and `stream_agent_text`.
- `RipgrepSettings` models the nested ripgrep settings block.

## Why

Keeping types in a leaf package with zero runtime dependencies eliminates circular imports. The rest of the codebase can always import from `tunacode.types` without worrying about import order.
