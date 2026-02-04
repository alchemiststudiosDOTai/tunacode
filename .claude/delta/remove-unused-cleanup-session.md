---
title: Remove unused cleanup_session helper
link: remove-unused-cleanup-session
type: delta
path: src/tunacode/configuration/paths.py
depth: 0
seams: [M]
ontological_relations:
  - relates_to: [[sessions]]
  - affects: [[system-utils]]
tags:
  - cleanup
  - sessions
  - maintenance
created_at: 2026-02-04T06:54:36.142471+00:00
updated_at: 2026-02-04T06:54:36.142471+00:00
uuid: 2da3eefa-7e65-4cfe-ab85-4d391cda5777
---

## Summary
Removed a dormant session cleanup helper that was no longer referenced, keeping the system utilities focused on active paths.

## Changes
- Deleted the unused `cleanup_session` helper from the configuration paths module.
- Dropped the `cleanup_session` re-export from system utilities.

## Behavioral Impact
No user-facing behavior changes; the helper was not invoked.

## Related Cards
- None.
