---
title: Utilities Layer
summary: Cross-cutting utilities for message conversion, token estimation, and repository file listing.
read_when: Modifying message format handling, changing token estimation heuristics, or adjusting file-listing behavior.
depends_on: [types, configuration]
feeds_into: [core, tools, ui]
when_to_read:
  - Modifying message format handling
  - Changing token estimation heuristics
  - Adjusting file-listing behavior
last_updated: "2026-07-11"
---

# Utilities Layer

**Package:** `src/tunacode/utils/`

## What

Stateless helper functions used across multiple layers. Two sub-packages: messaging (canonical message conversion and token counting) and system (repository file listing with shared ignore rules).

## Key Files

### Messaging (`messaging/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Re-exports all public functions from `adapter` and `token_counter`. Import from `tunacode.utils.messaging` directly. |
| `adapter.py` | Helpers over tinyagent message models and their JSON dict form. `to_canonical()` validates a message's role and returns the tinyagent-shaped dict. Extraction helpers: `get_content()`, `get_tool_call_ids()`, `get_tool_return_ids()`, `find_dangling_tool_calls()`. |
| `token_counter.py` | Lightweight heuristic token estimation (`CHARS_PER_TOKEN = 4`). `estimate_tokens(text)` for raw strings. `estimate_message_tokens(message)` for a single message (accepts both dict and tinyagent message models). `estimate_messages_tokens(messages)` sums over a list. Used by compaction threshold checks and the resource bar. |

### System (`system/`)

| File | Purpose |
|------|---------|
| `gitignore.py` | `list_cwd(max_depth)` -- walks the working directory using the same built-in ignore defaults and `.gitignore` rules as the rest of the file-filtering stack, including fallback-to-default behavior when `.gitignore` is unreadable or malformed. |

## How

### Message Conversion

tinyagent messages exist in two forms: typed pydantic models in memory, and
plain dicts (`model_dump(exclude_none=True)`) at persistence boundaries. There
is no separate canonical model — the adapter accepts either form, validates the
`role`, and extracts from the dict shape:

```
tinyagent model | dict  -->  to_canonical()   -->  validated tinyagent dict
tinyagent model | dict  -->  get_content()          -->  str
tinyagent model | dict  -->  get_tool_call_ids()    -->  list[str]
tinyagent model | dict  -->  get_tool_return_ids()  -->  list[str]
```

Supported tinyagent roles: `user`, `assistant`, `system`, `tool_result`, `tool`.

Content item types: `text`, `thinking`, `image`, `tool_call`.

### Token Estimation

The 4-chars-per-token heuristic is deliberately simple. It is used for:
- Compaction threshold decisions (`CompactionController.should_compact()`)
- Resource bar token display
- Retention boundary calculation in `ContextSummarizer`

It is NOT used for billing -- `UsageMetrics` carries the provider-reported token counts.

### File Listing

`list_cwd()` composes the shared default ignore set with any readable `.gitignore` lines, compiles that into a reusable `pathspec`, and short-circuits obvious generated directories such as `.git/` and `.venv/` before the expensive matcher runs.

If `.gitignore` cannot be read cleanly, the utility falls back to the built-in defaults instead of failing the listing call. That keeps the UI file picker and related helpers usable on cold or damaged checkouts.

## Why

Message adapter exists because tinyagent uses untyped dicts while internal code benefits from typed dataclasses. The adapter is the single translation point -- no other module manually parses message dicts.

Token estimation is intentionally rough. Accurate tokenization requires model-specific tokenizers (tiktoken, etc.) which add startup cost and dependency weight. The heuristic is good enough for "should we compact?" decisions.
