---
title: No Cargo Cult Fixes - Question Every Change
link: no-cargo-cult-fixes
type: qa
path: qa/
depth: 1
seams: [M]
ontological_relations:
  - relates_to: [[code-review]]
  - affects: [[all-modules]]
  - fixes: [[scope-creep]]
tags:
  - discipline
  - shims
  - code-review
created_at: 2026-01-09T22:15:00Z
updated_at: 2026-01-09T22:15:00Z
uuid: 4fa0c1e7-d7d0-415a-91e4-d69b28210ff0
---

## Problem

When extracting changes from a messy PR, I blindly copied a fix to `retry.py` without questioning whether it was needed.

The signature preservation fix was for pydantic-ai tool schema generation. `retry_on_json_error` is a JSON parsing utility - it never gets passed to pydantic-ai's `Tool()`. The fix there was a shim.

## Root Cause

Cargo culting. "The original PR had it, so I included it."

## Lesson

Before applying any fix, ask: **"Does this code path actually hit the problem?"**

For the signature preservation bug specifically:
- pydantic-ai uses `inspect.signature()` to generate JSON schemas for tools
- Only wrappers that produce functions passed to `Tool()` need the fix
- `retry_on_json_error` wraps JSON parsers, not pydantic-ai tools

## Rule

If you encounter a shim, fix it. Don't care who made it. Don't propagate it.

## Files That Actually Needed The Fix

1. `research_agent.py` - `ProgressTracker.wrap_tool()` wraps tools for pydantic-ai
2. `decorators.py` - `base_tool()` and `file_tool()` wrap tools for pydantic-ai
3. `present_plan.py` - `create_present_plan_tool()` creates a pydantic-ai tool

## Files That Did NOT Need The Fix

- `retry.py` - wraps JSON parsers, not pydantic-ai tools
