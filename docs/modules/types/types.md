---
title: Types Layer
summary: Centralized type aliases, callback protocols, and the canonical message model shared across all layers.
read_when: Adding a new callback signature, creating a new tool, or modifying message structures.
depends_on: []
feeds_into: [configuration, infrastructure, tools, core, ui]
---

# Types Layer

**Package:** `src/tunacode/types/`

## What

Single source of truth for every type alias, callback protocol, and data structure used across layers. No runtime logic lives here -- only definitions.

## Key Files

| File              | Purpose |
|-------------------|---------|
| `__init__.py`     | Re-exports everything from the sub-modules below. Import from `tunacode.types` directly. |
| `base.py`         | Scalar aliases (`FilePath`, `ModelName`, `TokenCount`, `ToolCallId`, etc.) and small compound types (`DiffHunk`, `DiffLine`, `FileDiff`). |
| `callbacks.py`    | Async callback signatures (`StreamingCallback`, `ToolCallback`, `ToolResultCallback`, `ToolStartCallback`, `NoticeCallback`) and protocols (`StreamResultProtocol`, `ToolCallPartProtocol`). |
| `canonical.py`    | The canonical message model: `CanonicalMessage`, `CanonicalPart`, `CanonicalToolCall`, `CanonicalToolCallPart`, `CanonicalToolReturnPart`, `UsageMetrics`. Enums: `MessageRole`, `PartKind`, `ToolCallStatus`. |
| `dataclasses.py`  | Value objects: `ModelConfig`, `ModelPricing`, `ModelRegistry`, `TokenUsage`, `CostBreakdown`. |

## How

Every other layer imports from `tunacode.types`. The `__init__.py` re-export list is the public API surface. If a type is not in `__all__`, it is internal.

`CanonicalMessage` / `CanonicalToolCall` form the domain vocabulary for messages flowing between the agent loop, tools, compaction, and the UI.

`UsageMetrics` tracks input/output tokens and cost per call, with an `.add()` method for session accumulation.

## Why

Keeping types in a leaf package with zero runtime dependencies eliminates circular imports. The rest of the codebase can always import from `tunacode.types` without worrying about import order.
