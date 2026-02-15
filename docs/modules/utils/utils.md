---
title: Utilities Layer
summary: Cross-cutting utilities for message conversion, token estimation, and gitignore-aware file listing.
read_when: Modifying message format handling, changing token estimation heuristics, or adjusting file-listing behavior.
depends_on: [types, configuration]
feeds_into: [core, tools, ui]
---

# Utilities Layer

**Package:** `src/tunacode/utils/`

## What

Stateless helper functions used across multiple layers. Two sub-packages: messaging (canonical message conversion and token counting) and system (gitignore-aware file listing).

## Key Files

### Messaging (`messaging/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Re-exports all public functions from `adapter` and `token_counter`. Import from `tunacode.utils.messaging` directly. |
| `adapter.py` | Bidirectional conversion between tinyagent dict messages and `CanonicalMessage`. `to_canonical()` / `from_canonical()` for single messages, `*_list()` variants for batches. Extraction helpers: `get_content()`, `get_tool_call_ids()`, `get_tool_return_ids()`, `find_dangling_tool_calls()`. |
| `token_counter.py` | Lightweight heuristic token estimation (`CHARS_PER_TOKEN = 4`). `estimate_tokens(text)` for raw strings. `estimate_message_tokens(message)` for a single message (accepts both dict and `CanonicalMessage`). `estimate_messages_tokens(messages)` sums over a list. Used by compaction threshold checks and the resource bar. |

### System (`system/`)

| File | Purpose |
|------|---------|
| `gitignore.py` | `list_cwd(max_depth)` -- walks the working directory respecting `.gitignore` patterns (falls back to built-in defaults). Used during system prompt context generation. |

## How

### Message Conversion

tinyagent stores messages as plain dicts with `role`, `content` (list of typed items), and optional metadata. The adapter normalizes these into `CanonicalMessage` / `CanonicalPart` dataclasses for type-safe processing:

```
tinyagent dict  -->  to_canonical()  -->  CanonicalMessage
                                              |
                                         .get_text_content()
                                         .get_tool_call_ids()
                                         .get_tool_return_ids()
                                              |
CanonicalMessage  -->  from_canonical()  -->  tinyagent dict
```

Supported tinyagent roles: `user`, `assistant`, `system`, `tool_result`, `tool`.

Content item types: `text`, `thinking`, `image`, `tool_call`.

### Token Estimation

The 4-chars-per-token heuristic is deliberately simple. It is used for:
- Compaction threshold decisions (`CompactionController.should_compact()`)
- Resource bar token display
- Retention boundary calculation in `ContextSummarizer`

It is NOT used for billing -- `UsageMetrics` carries the provider-reported token counts.

## Why

Message adapter exists because tinyagent uses untyped dicts while internal code benefits from typed dataclasses. The adapter is the single translation point -- no other module manually parses message dicts.

Token estimation is intentionally rough. Accurate tokenization requires model-specific tokenizers (tiktoken, etc.) which add startup cost and dependency weight. The heuristic is good enough for "should we compact?" decisions.
