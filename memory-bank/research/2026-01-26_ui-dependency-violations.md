# Research – UI Layer Dependency Violations

**Date:** 2026-01-26
**Owner:** Claude (context-engineer:research)
**Phase:** Research
**Branch:** `ui-dependency-direction`

## Goal

Map all dependency direction violations in the `ui/` layer for the next developer to fix. The correct flow per Gate 2 is:

```
ui → core → tools → utils/types
```

## Reference

See `layers.dot` for the full dependency graph. Current violations:
- `ui -> tools [3]` - **VIOLATION**
- `ui -> configuration [8]` - **EVALUATE**
- `ui -> lsp [2]` - **VIOLATION**

---

## Findings

### 1. ui → tools (VIOLATION - 3 imports, 2 files)

These MUST be refactored to go through core.

| File | Line | Import | Usage |
|------|------|--------|-------|
| `ui/main.py` | 15 | `ToolHandler` | Creates instance at L75, L197 |
| `ui/repl_support.py` | 32 | `ToolHandler` | Creates fallback instance at L151 |
| `ui/renderers/tools/list_dir.py` | 17 | `IGNORE_PATTERNS_COUNT` | Calculates total ignore count at L79 |

**Fix Strategy:**
1. `ToolHandler` - Core should expose this via `StateManager` or similar. UI should not instantiate tools directly.
2. `IGNORE_PATTERNS_COUNT` - Pass this value in the tool result dict, or move constant to utils.

---

### 2. ui → lsp (VIOLATION - 1 import)

| File | Line | Import | Usage |
|------|------|--------|-------|
| `ui/renderers/tools/diagnostics.py` | 12 | `truncate_diagnostic_message` | Text formatting at L163 |

**Fix Strategy:**
- Move `truncate_diagnostic_message()` to `utils/text.py` or `utils/formatting.py`
- Both LSP and UI can then import from utils (valid direction)

---

### 3. ui → configuration (8 imports, 4 files - NEEDS DECISION)

The `configuration/` module is ambiguous - is it core or utils-level?

| File | Line | Import |
|------|------|--------|
| `ui/main.py` | 10 | `ApplicationSettings` |
| `ui/commands/__init__.py` | 11 | `ApplicationSettings` |
| `ui/commands/__init__.py` | 161 | `validate_provider_api_key` |
| `ui/commands/__init__.py` | 186-190 | `DEFAULT_USER_CONFIG`, `get_model_context_window`, `load_models_registry` |
| `ui/screens/setup.py` | 13-18 | `DEFAULT_USER_CONFIG`, `get_models_for_provider`, `get_provider_env_var`, `get_providers` |
| `ui/screens/model_picker.py` | 12 | `get_models_for_provider`, `get_providers` |
| `ui/screens/model_picker.py` | 236 | `format_pricing_display`, `get_model_pricing` |

**Decision Required:**
- **Option A:** Treat `configuration/` as utils-level (like types/) → imports are VALID
- **Option B:** Treat `configuration/` as core-level → route through core layer

**Recommendation:** Option A - configuration holds static data (model registries, defaults, pricing). It's read-only infrastructure, not business logic.

---

## Priority Order for Fixes

1. **P0 - ToolHandler** (ui/main.py, ui/repl_support.py)
   - Biggest violation - UI directly manages tool authorization
   - Fix: Expose via StateManager or AgentRunner

2. **P1 - IGNORE_PATTERNS_COUNT** (ui/renderers/tools/list_dir.py)
   - Minor but clear violation
   - Fix: Include in tool result or move to utils

3. **P2 - truncate_diagnostic_message** (ui/renderers/tools/diagnostics.py)
   - Text utility in wrong place
   - Fix: Move to utils/formatting.py

4. **P3 - Configuration** (decide on architecture)
   - Document the decision either way

---

## Current Dependency Graph (from layers.dot)

```
ui ──────┬──→ core (9) ✓
         ├──→ types (6) ✓
         ├──→ utils (10) ✓
         ├──→ configuration (8) ?
         ├──→ tools (3) ✗ VIOLATION
         └──→ lsp (2) ✗ VIOLATION
```

---

## Files to Modify

```
src/tunacode/ui/main.py                          # Remove ToolHandler import
src/tunacode/ui/repl_support.py                  # Remove ToolHandler import
src/tunacode/ui/renderers/tools/list_dir.py      # Remove IGNORE_PATTERNS_COUNT import
src/tunacode/ui/renderers/tools/diagnostics.py   # Import from utils instead
src/tunacode/core/state.py                       # Expose ToolHandler (or similar)
src/tunacode/utils/formatting.py                 # New file for truncate_diagnostic_message
```

---

## References

- `layers.dot` - Dependency graph with edge counts
- `.claude/CLAUDE.md` - Gate 2: Dependency Direction rules
- Branch: `ui-dependency-direction`
