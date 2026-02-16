---
title: Context rail inspector styling and core agents cleanup
type: delta
link: context-rail-inspector-styling
path: src/tunacode/ui/styles/layout.tcss
depth: 0
seams: [M]
ontological_relations:
  - affects: [[ui]]
  - affects: [[context-rail]]
tags:
  - ui
  - styling
  - context-rail
created_at: 2026-02-16T15:45:35-06:00
updated_at: 2026-02-16T15:45:35-06:00
uuid: b2d4f901-8a3c-4e7d-a1c5-6f9e3b5d2a08
---

# Context rail inspector styling and core agents cleanup

## Summary

Polished the context rail inspector with theme-colored border title and reduced the core agents main module to 600 lines.

## Changes

- `src/tunacode/ui/styles/layout.tcss`
  - Replaced `outline: solid $border` with `border-title-align: center`, `border-title-color: $accent`, `border-title-style: bold`
  - Updated DoomEd inspector comment for clarity
- `src/tunacode/ui/app.py`
  - Set `rail.border_title = "Session Inspector"` in compose
- `src/tunacode/core/agents/main.py`
  - Removed blank lines to bring module under 600 lines
