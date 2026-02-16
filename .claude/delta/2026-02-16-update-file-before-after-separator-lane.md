---
title: Update file side-by-side diff now has explicit before/after separation lane
type: delta
link: update-file-before-after-separator-lane
path: src/tunacode/ui/renderers/tools/update_file.py
depth: 0
seams: [A, M]
ontological_relations:
  - affects: [[ui]]
  - affects: [[tool-renderers]]
  - improves: [[update-file-diff-clarity]]
tags:
  - ui
  - diff
  - update_file
  - rendering
created_at: 2026-02-16T14:05:49-06:00
updated_at: 2026-02-16T14:05:49-06:00
uuid: 0291d339-2bd4-481b-bdda-c879e54447a4
---

# Update file side-by-side diff now has explicit before/after separation lane

## Summary

Improved readability of `update_file` side-by-side diffs by adding a visible change lane (`-│`, `+│`, ` │`) and explicit `Before`/`After` captions.

## Changes

- `src/tunacode/ui/renderers/tools/update_file.py`
  - Added symbolic constants for side-by-side layout widths and divider glyphs.
  - Changed middle diff column to a 2-character lane that combines change direction with a vertical separator.
  - Styled lane markers by direction (`delete` red, `insert` green, context dim).
  - Updated caption to: `Before: a/<file> │ After: b/<file>`.

- `tests/unit/ui/test_update_file_renderer.py`
  - Added assertion that rendered output includes:
    - `Before: a/file.py`
    - `After: b/file.py`
    - `-│` and `+│` markers

## Behavioral Impact

No tool contract changes. The renderer still parses unified diffs and retains unified-diff fallback when side-by-side parsing fails.
