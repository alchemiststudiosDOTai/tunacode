# Research – Issue #313: Core → Utils Layer Violation

**Date:** 2026-01-27
**Owner:** Claude (research agent)
**Phase:** Research
**Issue:** [#313 Layer violation: core → utils (18 imports, skips Layer 2)](https://github.com/alchemiststudiosDOTai/tunacode/issues/313)

## Goal

Document all `core → utils` imports, categorize by fix strategy, and provide a migration plan to eliminate the layer violation where core (Layer 1) imports directly from utils (Layer 3), skipping Layer 2 (tools/indexing/lsp).

## Architecture Reference

```
ui (Layer 0)
  ↓ only
core (Layer 1)
  ↓ only
tools | indexing | lsp (Layer 2)
  ↓ only
utils (Layer 3)

Foundation (exempt): types, configuration, constants
```

## Findings

### Current Import Analysis

**Total:** 24 imports across 13 files

| Core File | Utils Module | Imports | Count |
|-----------|-------------|---------|-------|
| `core/system_paths.py:5-11` | `utils.system.paths` | `check_for_updates`, `delete_session_file`, `get_project_id` | 3 |
| `core/agents/resume/sanitize_debug.py:11` | `utils.messaging` | `_get_attr`, `_get_parts`, `get_tool_call_ids`, `get_tool_return_ids` | 4 |
| `core/agents/resume/summary.py:19` | `utils.messaging` | `estimate_tokens` | 1 |
| `core/agents/resume/prune.py:11` | `utils.messaging` | `estimate_tokens` | 1 |
| `core/agents/resume/sanitize.py:20` | `utils.messaging` | `_get_attr`, `_get_parts`, `find_dangling_tool_calls`, `to_canonical_list` | 4 |
| `core/agents/agent_components/agent_config.py:24-25` | `utils.config`, `utils.limits` | `load_config`, `get_max_tokens` | 2 |
| `core/agents/agent_components/orchestrator/tool_dispatcher.py:108,149` | `utils.parsing` | `parse_args`, `parse_tool_calls_from_text`, `has_potential_tool_call` | 3 |
| `core/agents/main.py:31` | `utils.ui` | `DotDict` | 1 |
| `core/file_filter.py:5` | `utils.ui.file_filter` | `FileFilter` | 1 |
| `core/formatting.py:5,8` | `utils.formatting` | `truncate_diagnostic_message`, `MAX_DIAGNOSTIC_MESSAGE_LENGTH` | 2 |
| `core/user_configuration.py:6-10` | `utils.config` | `load_config_with_defaults`, `save_config`, `UserConfigStateManager` | 3 |
| `core/state.py:19,98,185,291,337` | `utils.messaging`, `utils.config`, `utils.system.paths` | `estimate_tokens`, `get_content`, `load_config_with_defaults`, `get_session_storage_dir` | 4 |
| `core/messaging.py:7` | `utils.messaging` | `get_content` | 1 |

### Utils Modules Dependency Analysis

| Utils Module | Dependencies | Layer Assessment |
|-------------|-------------|------------------|
| `utils/system/paths.py` | `configuration.settings`, `constants` | Foundation-eligible |
| `utils/messaging/` | `types.canonical` only | Foundation-eligible (type adapters) |
| `utils/config/` | `configuration.settings`, `exceptions`, `types` | Foundation-eligible |
| `utils/limits.py` | `constants`, `utils.config` | Foundation-eligible (after config moves) |
| `utils/parsing/` | `constants`, `exceptions`, `types` | Tool-specific (Layer 2) |
| `utils/ui/helpers.py` | None | Inline candidate |
| `utils/ui/file_filter.py` | `constants`, `utils.system.ignore_patterns` | Infrastructure |
| `utils/formatting.py` | None | Inline candidate |

### Existing Facade Pattern

Core already has facade files that re-export from utils:

- `core/messaging.py` → re-exports `get_content`
- `core/formatting.py` → re-exports `truncate_diagnostic_message`
- `core/user_configuration.py` → re-exports config functions
- `core/system_paths.py` → re-exports path utilities
- `core/file_filter.py` → re-exports `FileFilter`

Pattern uses underscore-prefixed imports:
```python
from tunacode.utils.messaging import get_content as _get_content
```

## Key Patterns / Solutions Found

### Fix Strategy Categories

**1. Move to Foundation (`configuration/`)** - 4 modules
- `utils/system/paths.py` → `configuration/paths.py`
- `utils/config/user_configuration.py` → `configuration/user_config.py`
- `utils/limits.py` → `configuration/limits.py`
- `utils/system/ignore_patterns.py` → `configuration/ignore_patterns.py`

**2. Move to Foundation (`types/adapters/`)** - 1 module
- `utils/messaging/` → `types/adapters/` (message format conversion)

**3. Re-export through Layer 2 (`tools/`)** - 1 module
- `utils/parsing/` → `tools/parsing/` (tool-specific parsing logic)

**4. Inline into Core** - 2 modules
- `utils/ui/helpers.py` (DotDict, 14 lines) → inline into `core/agents/main.py`
- `utils/formatting.py` (6-line function) → inline into `core/formatting.py`

**5. Move to Infrastructure** - 1 module
- `utils/ui/file_filter.py` → new `infrastructure/` package

### Migration Order

To avoid circular dependencies, migrate in this order:

1. **Phase 1 - Inline tiny modules (no dependencies)**
   - Inline `utils/formatting.py` into `core/formatting.py`
   - Inline `DotDict` from `utils/ui/helpers.py` into `core/agents/main.py`

2. **Phase 2 - Foundation layer (configuration/)**
   - Move `utils/system/ignore_patterns.py` → `configuration/ignore_patterns.py`
   - Move `utils/config/user_configuration.py` → `configuration/user_config.py`
   - Move `utils/limits.py` → `configuration/limits.py`
   - Move `utils/system/paths.py` → `configuration/paths.py`

3. **Phase 3 - Foundation layer (types/adapters/)**
   - Move `utils/messaging/` → `types/adapters/`

4. **Phase 4 - Infrastructure**
   - Create `infrastructure/` package
   - Move `utils/ui/file_filter.py` → `infrastructure/file_filter.py`

5. **Phase 5 - Tool layer re-export**
   - Move `utils/parsing/` → `tools/parsing/`
   - Update `core/agents/.../tool_dispatcher.py` to import from `tools.parsing`

6. **Phase 6 - Cleanup**
   - Delete empty `utils/` directories
   - Update all imports across codebase
   - Verify with grimp/import-linter

## Knowledge Gaps

- **Cross-layer import counts**: Need to verify tools/ also imports from some utils modules (limits, ignore_patterns)
- **Test coverage**: Need to verify tests don't have direct utils imports
- **UI layer**: Need to verify UI doesn't import directly from utils (should go through core facades)

## Acceptance Criteria (from issue)

- [ ] Zero direct imports from `tunacode.utils` in `tunacode.core`
- [ ] Utils accessed through `tools`/`indexing`/`lsp` layer OR moved to foundation
- [ ] `import-linter` passes with layer config
- [ ] No new functionality added (pure refactor)
- [ ] Tests pass

## Impact Assessment

| Impact Area | Scope | Risk |
|-------------|-------|------|
| Messaging (estimate_tokens, get_content) | 6 files | Medium - hot path for token counting |
| Config (load_config, limits) | 4 files | Low - straightforward move |
| Paths (session storage) | 2 files | Low - infrastructure |
| Parsing (tool dispatch) | 1 file | Medium - complex multi-strategy parser |
| UI helpers (DotDict, FileFilter) | 2 files | Low - simple utilities |
| Formatting | 1 file | Low - 6-line inline |

## References

- Issue: https://github.com/alchemiststudiosDOTai/tunacode/issues/313
- Architecture: `docs/architecture/layers_html.html`
- Dependency map: `docs/architecture/DEPENDENCY_MAP.md`
- Related issues: #311 (core→types), #312 (core→configuration), #314 (Layer 2 lateral), #315 (lsp→configuration)

## File Inventory

### Files to Modify (core/ - update imports)

1. `src/tunacode/core/system_paths.py`
2. `src/tunacode/core/agents/resume/sanitize_debug.py`
3. `src/tunacode/core/agents/resume/summary.py`
4. `src/tunacode/core/agents/resume/prune.py`
5. `src/tunacode/core/agents/resume/sanitize.py`
6. `src/tunacode/core/agents/agent_components/agent_config.py`
7. `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`
8. `src/tunacode/core/agents/main.py`
9. `src/tunacode/core/file_filter.py`
10. `src/tunacode/core/formatting.py`
11. `src/tunacode/core/user_configuration.py`
12. `src/tunacode/core/state.py`
13. `src/tunacode/core/messaging.py`

### Files to Move/Create

| Source | Destination |
|--------|-------------|
| `src/tunacode/utils/system/paths.py` | `src/tunacode/configuration/paths.py` |
| `src/tunacode/utils/config/user_configuration.py` | `src/tunacode/configuration/user_config.py` |
| `src/tunacode/utils/limits.py` | `src/tunacode/configuration/limits.py` |
| `src/tunacode/utils/system/ignore_patterns.py` | `src/tunacode/configuration/ignore_patterns.py` |
| `src/tunacode/utils/messaging/` | `src/tunacode/types/adapters/` |
| `src/tunacode/utils/parsing/` | `src/tunacode/tools/parsing/` |
| `src/tunacode/utils/ui/file_filter.py` | `src/tunacode/infrastructure/file_filter.py` |
| (inline) `utils/formatting.py` | → `core/formatting.py` |
| (inline) `utils/ui/helpers.py` DotDict | → `core/agents/main.py` |

### Files to Delete (after migration)

- `src/tunacode/utils/formatting.py`
- `src/tunacode/utils/ui/helpers.py` (if only contains DotDict)
- Empty `utils/` subdirectories
