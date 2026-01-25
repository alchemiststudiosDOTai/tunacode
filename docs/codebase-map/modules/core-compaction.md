---
title: Core Compaction
path: src/tunacode/core/compaction.py
type: file
depth: 1
description: Context window management and tool output pruning
exports: [prune_old_tool_outputs, get_prune_thresholds, is_tool_return_part, count_user_turns, estimate_part_tokens, prune_part_content]
seams: [M]
---

# Core Compaction

## Purpose

Manages context window limits by pruning old tool outputs from conversation history while preserving recent context. Uses a backward-scanning algorithm to identify and replace old tool outputs with placeholders.

## When Pruning Occurs

Pruning is triggered **proactively** at the start of each agent request, before the agent iteration loop begins:

```
Location: core/agents/main.py:367-372
```

```python
# In RequestOrchestrator._run_impl()
session_messages = self.state_manager.session.conversation.messages
_, tokens_reclaimed = prune_old_tool_outputs(session_messages, self.model)
message_history = list(session_messages)
```

This ensures context is compacted before sending to the provider, not reactively after overflow.

## Pruning Algorithm

The `prune_old_tool_outputs()` function at lines 160-238 implements a 4-phase algorithm:

### Phase 1: Backward Scanning (lines 187-204)

Iterates through messages **newest to oldest**:
- Identifies tool return parts using `is_tool_return_part()`
- Estimates token count for each using `estimate_part_tokens()`
- Builds list of `(message_index, part_index, part, token_count)` tuples

### Phase 2: Protection Boundary (lines 209-221)

Determines which outputs to protect:
- Accumulates tokens from newest to oldest
- When accumulated tokens exceed `protect_tokens` threshold, marks pruning boundary
- All outputs within protection window remain untouched

### Phase 3: Threshold Check (lines 223-229)

Validates pruning is worthwhile:
- Calculates total tokens reclaimable from old outputs
- Only proceeds if savings exceed `minimum_threshold`
- Prevents unnecessary work for minimal gains

### Phase 4: Content Replacement (lines 231-236)

Performs in-place mutation:
- Replaces old tool output content with placeholder
- Uses `prune_part_content()` for safe mutation
- Returns total tokens reclaimed

## Key Functions

### prune_old_tool_outputs(messages, model)

Main entry point. Returns `(pruned_count, tokens_reclaimed)`.

### get_prune_thresholds()

Returns `(protect_tokens, minimum_threshold)` based on `is_local_mode()`.

### is_tool_return_part(part)

Returns `True` if part has `part_kind == "tool-return"`.

### count_user_turns(messages)

Counts user messages. Pruning requires `>= 2` user turns (`PRUNE_MIN_USER_TURNS`).

### estimate_part_tokens(part)

Estimates tokens in a message part using 4-char heuristic.

### prune_part_content(part)

Replaces part content with placeholder. Returns tokens reclaimed or 0 if immutable.

## Safety Guards

| Guard | Location | Purpose |
|-------|----------|---------|
| Min user turns | line 183-185 | Requires 2+ turns before pruning |
| Immutability handling | line 151-156 | Gracefully handles frozen parts |
| Already-pruned check | line 138-139 | Skips parts with placeholder |
| Empty messages | line 179-180 | Early return for empty list |

## Pruning Thresholds

Binary switch based on `is_local_mode()`:

| Mode | protect_tokens | minimum_threshold | Behavior |
|------|----------------|-------------------|----------|
| Standard (API) | 40,000 | 20,000 | Keep ~40k recent tokens |
| Local | 2,000 | 500 | Aggressive - keep only ~2k tokens |

Local mode prunes **20x more aggressively** to preserve limited context windows.

Thresholds are defined at lines 14-18 and are not user-configurable.

## Placeholder

Pruned content is replaced with:

```
[Old tool result content cleared]
```

Defined as `PRUNE_PLACEHOLDER` at line 21.

## What Gets Pruned

**Targets:**
- Tool return parts (`part_kind == "tool-return"`)
- Content older than protection window

**Never Pruned:**
- User messages
- Recent tool outputs (within protection window)
- System prompts
- Tool call requests (only returns are pruned)

## Integration Points

| Component | File | Integration |
|-----------|------|-------------|
| Mode detection | `core/limits.py` | `is_local_mode()` for threshold selection |
| Trigger point | `core/agents/main.py:369` | Called at request start |
| Token counting | `utils/messaging/token_counter.py` | `estimate_tokens()` |
| Message types | `types/pydantic_ai.py` | `ToolReturnPart`, `ModelRequest` |
| State | `core/state.py` | `session.conversation.messages` storage |

## Constants

```python
PRUNE_PROTECT_TOKENS = 40_000       # Standard mode
PRUNE_MINIMUM_THRESHOLD = 20_000    # Standard mode
LOCAL_PRUNE_PROTECT_TOKENS = 2_000  # Local mode
LOCAL_PRUNE_MINIMUM_THRESHOLD = 500 # Local mode
PRUNE_MIN_USER_TURNS = 2            # Safety guard
PRUNE_PLACEHOLDER = "[Old tool result content cleared]"
```

## Seams (M)

**Modification Points:**
- Adjust thresholds in constants (lines 14-18)
- Customize placeholder format (line 21)
- Add selective preservation rules in phase 2
- Implement content-aware pruning (e.g., preserve error messages)
