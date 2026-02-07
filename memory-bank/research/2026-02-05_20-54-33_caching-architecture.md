# Research - Caching Architecture and Boundaries

**Date:** 2026-02-05
**Owner:** agent
**Phase:** Research
**git_commit:** 9b6bf0d8

## Goal

Map all existing caching mechanisms in tunacode, document their boundaries, and identify invalidation strategies.

## Findings

### Cache Inventory

| Cache Name | Location | Scope | Invalidation Strategy |
|------------|----------|-------|----------------------|
| Agent Instance Cache | `agent_config.py:56-57` | Module + Session | Version hash + manual on abort |
| System Prompt Cache | `agent_config.py:53` | Module | Mtime-based |
| Canonical Message Cache | `sanitize.py:520` | Per-iteration | Explicit (set to None after mutation) |
| Settings/Limits Cache | `limits.py:18` | Module (LRU) | Manual `clear_cache()` |
| Models Registry Cache | `models.py:13` | Module | None (requires restart) |
| Gitignore Manager Cache | `ignore.py:36` | Module | Mtime-based |
| XML Prompt Cache | `xml_helper.py:10` | Module (LRU) | Never (maxsize=32) |
| Editor Wrap Cache | `editor.py:50-51` | Instance | Explicit invalidation |
| Ripgrep Utilities Cache | `ripgrep.py:25,52` | Module (LRU) | Never (maxsize=1) |

### Relevant Files

- `src/tunacode/core/agents/agent_components/agent_config.py` - Agent and prompt caching (lines 52-57, 149-192)
- `src/tunacode/core/agents/resume/sanitize.py` - Canonical message cache (lines 70-99, 519-546)
- `src/tunacode/configuration/limits.py` - Settings LRU cache (lines 18-32)
- `src/tunacode/configuration/models.py` - Models registry cache (lines 13-52)
- `src/tunacode/tools/ignore.py` - Gitignore manager cache (lines 28-36, 158-171)
- `src/tunacode/tools/xml_helper.py` - XML prompt LRU cache (line 10)
- `src/tunacode/ui/widgets/editor.py` - UI wrap state cache (lines 50-51, 188)
- `src/tunacode/tools/utils/ripgrep.py` - Ripgrep utilities cache (lines 25, 52)

---

## Cache Architecture Detail

### 1. Agent Instance Cache (Two-Level)

**Purpose:** Persist PydanticAI agent instances with HTTP clients to reuse connections

**Cache Stores:**
```python
_AGENT_CACHE: dict[ModelName, PydanticAgent] = {}      # Module level
_AGENT_CACHE_VERSION: dict[ModelName, int] = {}        # Config version hash
session.agents: dict[ModelName, PydanticAgent] = {}    # Session level
```

**Lookup Flow:**
1. Check session cache first (`session.agents[model]`)
2. Validate version matches current config
3. If miss/stale, check module cache
4. If version mismatch, invalidate and recreate
5. Store in both caches on creation

**Version Invalidation Triggers:**
- Config changes: `max_retries`, `tool_strict_validation`, `request_delay`, `global_request_timeout`
- User abort (ESC key) - prevents broken HTTP client reuse

**Boundary:** HTTP client is reused across API calls, but responses are NOT cached

---

### 2. System Prompt Cache (AGENTS.md)

**Purpose:** Cache system prompt file contents to avoid repeated disk I/O

**Cache Structure:**
```python
_TUNACODE_CACHE: dict[str, tuple[str, float]] = {}
# Key: absolute file path
# Value: (content string, mtime)
```

**Invalidation:** Automatic via file mtime comparison on every access

**Boundary:** Re-read if file modified; no cross-session persistence

---

### 3. Canonical Message Cache (Per-Iteration)

**Purpose:** Optimize sanitize cleanup loop by caching canonical conversions

**Cache Lifecycle:**
1. Created once at start of each cleanup iteration
2. Passed to `find_dangling_tool_call_ids()`, `remove_empty_responses()`, `remove_consecutive_requests()`
3. Invalidated (set to None) after any mutation
4. Recomputed via `_resolve_canonical_cache()` before next use

**Performance Gain:** From 4N to 1N conversions per iteration (75% reduction)

**Boundary:** Strictly per-iteration; does NOT persist across cleanup iterations

**Invariant:** `len(canonical_cache) == len(messages)` - ValueError if violated

---

### 4. Settings/Limits Cache

**Purpose:** Cache user config settings to avoid repeated file I/O

```python
@lru_cache(maxsize=1)
def _load_settings() -> dict:
    config = load_config()
    return config.get("settings", {})
```

**Boundary:** Must call `clear_cache()` manually when config changes

---

### 5. Models Registry Cache

**Purpose:** Cache parsed `models_registry.json` (provider configs, pricing, limits)

```python
_models_registry_cache: dict | None = None  # Singleton
```

**Boundary:** Never invalidated during runtime; requires process restart

**Rationale:** Registry is static bundled data that doesn't change during execution

---

### 6. Gitignore Manager Cache

**Purpose:** Cache compiled PathSpec patterns for gitignore matching

```python
@dataclass(frozen=True)
class IgnoreCacheEntry:
    gitignore_mtime: float
    manager: IgnoreManager

IGNORE_MANAGER_CACHE: dict[Path, IgnoreCacheEntry] = {}
```

**Invalidation:** Automatic via `.gitignore` mtime comparison

**Boundary:** One entry per directory root; recomputes if `.gitignore` modified

---

## Cache Boundaries Summary

### What Crosses Cache Boundaries

| Source | Target | Crosses? | Notes |
|--------|--------|----------|-------|
| Agent Cache | HTTP Requests | Partial | Client reused, responses fresh |
| Session Cache | Module Cache | Yes | Bidirectional sync maintained |
| Canonical Cache | Cleanup Operations | Yes | Passed as parameter |
| Settings Cache | Runtime Config | Yes | Exposed via getter functions |

### What Does NOT Cross Cache Boundaries

| Item | Why Not Cached |
|------|----------------|
| API Responses | Each request is fresh; no response caching |
| Tool Results | Each execution is fresh; tools always run |
| File Contents | Tools always read from disk |
| Token Counts | Extracted per-request, not persisted per-message |

---

## Key Patterns / Solutions Found

### 1. Two-Level Cache with Version Tracking (Agent Cache)
- Module cache persists across session resets
- Session cache maintains backward compatibility with tests
- Version hash detects config changes requiring agent recreation

### 2. Mtime-Based TTL (Prompt Cache, Gitignore Cache)
- Check file modification time on every access
- Automatic invalidation without explicit API
- Zero maintenance overhead

### 3. Scope-Limited Cache (Canonical Messages)
- Cache valid only within single iteration
- Explicit invalidation after mutations
- Prevents stale data from persisting

### 4. Immutable Cache Entries (Gitignore)
- `@dataclass(frozen=True)` prevents accidental mutation
- Forces creation of new entry on invalidation

### 5. LRU Eviction for Static Data (XML Prompts)
- Finite cache size prevents unbounded growth
- Process-lifetime persistence for static content

---

## Cache Invalidation Matrix

| Cache | Auto-Invalidate | Manual Invalidate | Version-Based | Never |
|-------|-----------------|-------------------|---------------|-------|
| Agent Instance | | `invalidate_agent_cache()` | Yes | |
| System Prompt | Mtime check | | | |
| Canonical Message | After mutation | | | |
| Settings/Limits | | `clear_cache()` | | |
| Models Registry | | | | Restart required |
| Gitignore Manager | Mtime check | | | |
| XML Prompt | | | | LRU only |
| Editor Wrap | | `_invalidate_wrap_cache()` | | |

---

## Knowledge Gaps

1. **No token count caching per message** - Each request re-estimates tokens
2. **Pruning has redundant calculations** - `PRUNE_PLACEHOLDER` token count not memoized
3. **Models registry staleness** - No way to detect if registry file changed
4. **Settings cache manual invalidation** - Easy to forget `clear_cache()` call
5. **No test coverage** for canonical cache validation logic (`_validate_canonical_cache`)

---

## Anti-Patterns Removed (Historical)

### Global Cache with SHA-1 Fingerprinting
**Removed from:** `configuration/user_config.py`
**Why removed:** Overhead of SHA-1 hashing exceeded cost of parsing small JSON (<1KB)
**Reference:** `.claude/delta/remove-global-cache-user-config.md`

### MessageTokenCache
**Removed from:** Token counting module
**Why removed:** Premature optimization; simpler to use API-reported usage
**Reference:** `memory-bank/research/2026-02-01-token-counting-logic.md`

---

## Test Coverage

**Covered:**
- `tests/unit/core/test_agent_cache_abort.py` - Agent cache invalidation on abort
- `tests/tools/test_ignore.py` - Gitignore cache mtime invalidation

**Gaps:**
- No test for canonical cache length mismatch ValueError
- No test for settings cache invalidation
- No test for models registry cache staleness

---

## References

### Implementation Files
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9b6bf0d8/src/tunacode/core/agents/agent_components/agent_config.py
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9b6bf0d8/src/tunacode/core/agents/resume/sanitize.py
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9b6bf0d8/src/tunacode/configuration/limits.py
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9b6bf0d8/src/tunacode/configuration/models.py
- https://github.com/alchemiststudiosDOTai/tunacode/blob/9b6bf0d8/src/tunacode/tools/ignore.py

### Documentation
- `.claude/delta/2026-02-02-sanitize-canonical-cache.md`
- `.claude/delta/remove-global-cache-user-config.md`
- `.claude/debug_history/2026-01-12_missing-cached-tokens.md`
- `.claude/debug_history/2026-01-21_abort-hang-investigation.md`

### Test Files
- `tests/unit/core/test_agent_cache_abort.py`
- `tests/tools/test_ignore.py`
