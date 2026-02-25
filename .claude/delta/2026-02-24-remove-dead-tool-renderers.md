---
title: Remove dead glob/grep/list_dir UI tool renderers
type: delta
link: remove-dead-tool-renderers
path: src/tunacode/ui/renderers/tools
depth: 1
seams: [M]
ontological_relations:
  - affects: [[ui]]
  - affects: [[tools]]
  - affects: [[tests]]
tags:
  - dead-code
  - renderers
  - tinyagent
created_at: 2026-02-24T01:22:50+00:00
updated_at: 2026-02-24T01:22:50+00:00
uuid: 6af25d41-9649-45e4-af1c-624f24eb6296
---

# Remove dead glob/grep/list_dir UI tool renderers

## Summary

Removed three renderer modules (`glob.py`, `grep.py`, `list_dir.py`) that no longer have matching runtime tools after the tinyagent migration.

Updated renderer exports to remove imports and `__all__` entries for these three render functions.

Updated unit tests to stop asserting renderer registration/inheritance for removed renderer classes.

Verified there were no TCSS selectors for `.tool-glob`, `.tool-grep`, or `.tool-list-dir`.

## Files changed

- `src/tunacode/ui/renderers/tools/__init__.py`
- `tests/unit/ui/test_base_renderer.py`
- `src/tunacode/ui/renderers/tools/glob.py` (deleted)
- `src/tunacode/ui/renderers/tools/grep.py` (deleted)
- `src/tunacode/ui/renderers/tools/list_dir.py` (deleted)

## Validation

- `uv run ruff check .` ✅
- `uv run pytest` ✅
