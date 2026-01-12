---
title: Missing cached_tokens in RequestUsage crashes usage tracking
link: missing-cached-tokens-request-usage
type: delta
path: src/tunacode/core/agents/agent_components/orchestrator/usage_tracker.py
depth: 0
seams: [D] data
ontological_relations:
  - relates_to: [[agent-orchestrator]]
  - affects: [[usage-tracking]]
  - fixes: [[requestusage-missing-cached-tokens]]
tags:
  - usage
  - crash
  - tracking
created_at: 2026-01-12T22:19:08Z
updated_at: 2026-01-12T22:19:08Z
uuid: 00080ff4-9b7e-418b-b7dc-ca671160aee7
---

## Summary

The new usage tracker accessed `cached_tokens` directly on provider usage objects, which caused an AttributeError for providers that omit that field. We now normalize usage objects at the boundary and default missing fields to 0, matching the old behavior.

## Context

This surfaced after the node processor refactor when the usage tracking logic moved into `usage_tracker.py` and lost the defensive `getattr` fallback. We missed it because the refactor did not include a regression test for usage objects without cached token data.

## Root Cause

Provider usage payloads are not uniform: some only include request/response tokens. The new code assumed the presence of `cached_tokens`, violating the implicit contract that missing fields should be treated as zero. Prevention: normalize usage objects at the type boundary and add a test for missing cached tokens.

## Changes

- Added a normalization helper for usage objects with defaults for missing fields.
- Updated usage tracking to use the normalized shape.
- Added a regression test covering missing `cached_tokens`.

## Behavioral Impact

Usage tracking no longer crashes when a provider omits cached token data; costs and totals still accumulate correctly with cached tokens treated as zero.

## Related Cards

None
