---
title: Core Compaction
path: src/tunacode/core/compaction.py
type: file
depth: 1
description: Context window management and tool output pruning
exports: [prune_old_tool_outputs, compact_messages]
seams: [M]
---

# Core Compaction

## Purpose
Manages context window limits by pruning old tool outputs from conversation history while preserving critical information.

## Key Functions

### prune_old_tool_outputs()
Removes old tool outputs from message history:
- Targets tool-result messages with large outputs
- Replaces with placeholder: `[Old tool result content cleared]`
- Preserves recent messages for context continuity
- Frees tokens for new interactions

### compact_messages()
General message compaction:
- Summarizes old conversation turns
- Removes redundant content
- Maintains conversation flow

## Compaction Strategy

**When to Compact:**
- Context window approaching limit (e.g., 80% full)
- Total tokens exceed configured threshold

**What to Prune:**
1. Large tool outputs (> N tokens)
2. Old file reads (already superseded)
3. Intermediate bash outputs
4. Redundant search results

**What to Preserve:**
1. Recent messages (last K turns)
2. User messages and critical responses
3. Final tool results
4. Task completion markers

## Placeholders

Pruned content replaced with:
```
[Old tool result content cleared - tool_name: args...]
```

## Pruning Thresholds

Binary switch based on `local_mode`:

| Mode | protect_tokens | minimum_threshold |
|------|----------------|-------------------|
| Standard | 40,000 | 20,000 |
| Local | 2,000 | 500 |

Thresholds are not user-configurable (internal optimization).

## Integration Points

- **core/limits.py** - Uses `is_local_mode()` for threshold selection
- **core/state.py** - Token tracking and message history
- **core/agents/main.py** - Called during iteration loop
- **types/** - MessageHistory type definitions

## Seams (M)

**Modification Points:**
- Adjust compaction thresholds
- Customize placeholder format
- Add selective preservation rules
- Implement smarter pruning strategies (e.g., keep recent writes)
