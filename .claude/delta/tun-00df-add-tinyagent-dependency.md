---
title: "Phase 1: Add tinyagent dependency via repo-local path"
link: "tun-00df-add-tinyagent-dependency"
type: "delta"
path:
  - "pyproject.toml"
  - "uv.lock"
  - "src/tunacode/core/tinyagent/__init__.py"
depth: 0
seams: [A, M]
ontological_relations:
  - relates_to: "[[tun-1658-tinyagent-migration]]"
  - affects: "[[dependencies]]"
  - affects: "[[tunacode-core]]"
tags:
  - migration
  - tinyagent
  - dependencies
created_at: 2026-02-07T15:15:39-06:00
updated_at: 2026-02-07T15:15:39-06:00
uuid: 8d77dabd-d9be-40b2-ad4f-ecdbbd71acb8
---

## Summary

Added `tinyagent` as a project dependency, sourced from the repo-local `./tinyAgent` directory, to begin the pydantic-ai → tinyagent migration without changing runtime behavior yet.

## Changes

- Updated `pyproject.toml` to include `tinyagent` and configured `uv` to install it from `./tinyAgent` as an editable path source.
- Regenerated `uv.lock` to include the new dependency.
- Added a small `tunacode.core.tinyagent` scaffolding module with helper functions to fail fast if `tinyagent` is missing.

## Behavioral Impact

- No user-facing or agent-loop behavior changes in Phase 1.
- `uv sync` now installs `tinyagent` into the project environment and tests continue to pass.

## Related Cards

- [[tun-1658-tinyagent-migration]]
