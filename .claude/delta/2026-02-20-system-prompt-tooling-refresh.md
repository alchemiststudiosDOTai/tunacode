---
title: Refresh system prompt for current toolchain
link: system-prompt-tooling-refresh
type: delta
path: src/tunacode/prompts/system_prompt.md
depth: 0
seams: [M]
ontological_relations:
  - relates_to: [[system-prompt]]
  - affects: [[tool-selection]]
  - affects: [[discover-workflow]]
tags:
  - prompt
  - tools
  - discover
  - cleanup
created_at: 2026-02-20T16:13:43-06:00
updated_at: 2026-02-20T16:17:48-06:00
uuid: 4db7ad4e-4615-4ed8-b2a8-63c56ada9573
---

## Summary
Updated `system_prompt.md` to align with the current runtime toolset and discovery workflow.

## Context
The prompt needed a tooling refresh so instructions map directly to current behavior and available tools.

## Changes
- Updated tool inventory to the current set.
- Replaced multi-step search guidance with a discover-first workflow.
- Enforced discover-only routing for repository search, lookup, and exploration.
- Added explicit prohibition on using bash for repository searching.
- Added an end-of-prompt final reminder block that repeats discover-for-search and bash-not-for-search guidance.
- Updated examples to demonstrate discover-first behavior and follow-up file reads/edits.
- Updated penalties to enforce use of the declared tool list.
- Clarified path usage for file tools and reinforced parallel batching rules.

## Behavioral Impact
- The model receives unambiguous guidance aligned to current tool availability.
- Repository searching is now explicitly routed through `discover`.
- End-of-prompt repetition reinforces that `bash` is for execution tasks, not code search.
- Reduced risk of invalid tool calls from ambiguous search instructions.
