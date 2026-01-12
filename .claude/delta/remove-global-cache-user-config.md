---
title: Remove global cache state from user_configuration
link: delta/remove-global-cache-user-config
type: delta
path: src/tunacode/utils/config/user_configuration.py
depth: 3
seams: [M] module
ontological_relations:
  - relates_to: [[utils]]
  - affects: [[user_configuration.py]]
tags:
  - utils
  - config
  - state-management
  - cleanup
created_at: 2026-01-12T00:00:00Z
updated_at: 2026-01-12T00:00:00Z
uuid: 3383a720-0203-4a5b-9c1c-7b2f8c4d5e6f
---

## Summary

Removed global mutable cache state from the user configuration module. The previous implementation used module-level `_config_fingerprint` and `_config_cache` variables for a fast-path optimization that was likely premature for configuration file handling.

## Context

The original `load_config()` function stored parsed config and its SHA-1 fingerprint in module globals to avoid re-parsing unchanged files. This added complexity and hidden state that could cause cache staleness issues.

## Root Cause

The fast-path optimization was unnecessary overhead for configuration files that:
- Are small (typically < 1KB)
- Are read infrequently (once per session or on demand)
- May change externally between calls

The cost of hashing and comparing fingerprints likely exceeded the cost of simply parsing the JSON.

## Changes

- Removed `_config_fingerprint` and `_config_cache` module-level globals
- Simplified `load_config()` to read and parse file directly
- Changed `save_config()` return type from `bool` to `None` (always returned `True`)
- Changed `set_default_model()` return type from `bool` to `None`
- Removed dead `except ConfigurationError: raise` code in `set_default_model()`

## Behavioral Impact

- Config loading is now simpler and more predictable
- No functional change in behavior - callers already handled `None` returns and exceptions
- Slightly more straightforward debugging with no hidden cache state

## Related Cards

- [[utils]] - Parent system
