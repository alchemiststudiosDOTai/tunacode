# Research – Configuration System Boundary Mapping

**Date:** 2026-01-24
**Owner:** agent
**Phase:** Research

## Goal

Map the 4 config definition locations, identify dead code, and define clear boundaries for cleanup.

## Findings

### The 4 Config Locations (User's Observation)

| Location | Purpose | Status |
|----------|---------|--------|
| `src/tunacode/configuration/defaults.py` | `DEFAULT_USER_CONFIG` constant | **SOURCE OF TRUTH** |
| `src/tunacode/types/base.py:30` | `UserConfig = dict[str, Any]` type alias | Fine (just a type) |
| `src/tunacode/core/state.py:39` | `SessionState.user_config` field | Fine (runtime storage) |
| `src/tunacode/configuration/settings.py` | `ApplicationSettings` class | **MOSTLY DEAD** |

**Verdict:** Not as bad as it sounds. Only 1 is the source of truth, 1 is a type alias, 1 is runtime storage, and 1 has dead code to clean up.

---

## Dead Code Identified

### Priority 1: Delete These Fields

| Field | Location | Evidence |
|-------|----------|----------|
| `lsp.timeout` | `defaults.py:37` | Never read. LSP uses hardcoded `DEFAULT_TIMEOUT = 5.0` in `lsp/client.py:21` |
| `lsp.max_diagnostics` | `defaults.py:38` | Never read anywhere |
| `ripgrep.max_buffer_size` | `defaults.py:30` | Appears in defaults but never consumed |
| `ripgrep.debug` | `defaults.py:33` | Appears in defaults but never consumed |
| `ApplicationSettings.guide_file` | `settings.py:24` | Never read. Actual guide file comes from `config["settings"]["guide_file"]` |
| `ApplicationSettings.internal_tools` | `settings.py:26-36` | 9-item list never accessed |
| `ApplicationSettings.name` | `settings.py:23` | Only used to compute dead `guide_file` |

### Priority 2: Duplicate Definitions to Consolidate

**Ripgrep config duplication:**
- `defaults.py:28-34` defines ripgrep defaults
- `grep.py:50-56` defines IDENTICAL hardcoded defaults
- Both must be updated when changing values → DRY violation

**Guide file name in 4 places:**
1. `constants.py:23` → `GUIDE_FILE_NAME = "AGENTS.md"`
2. `defaults.py:26` → uses constant (good)
3. `settings.py:24` → hardcodes `f"{self.name.upper()}.md"` (dead)
4. `agent_config.py:238,240` → hardcodes `"AGENTS.md"` fallback

---

## Config Data Flow (Clean Path)

```
DEFAULT_USER_CONFIG (defaults.py)
    ↓
StateManager.__init__() (state.py:138)
    ↓
load_config_with_defaults() (user_configuration.py)
    ↓
merge_user_config(defaults, user_file)
    ├─ deepcopy(defaults)
    └─ merge user overrides
    ↓
session.user_config = merged
    ↓
Consumed via session.user_config.get("key", fallback)
```

---

## Boundary Definition

### Keep (Clean Separation)

```
src/tunacode/
├── configuration/
│   ├── defaults.py      ← DEFAULT_USER_CONFIG (schema + defaults)
│   ├── models.py        ← Model definitions
│   └── pricing.py       ← Cost calculations
├── types/
│   └── base.py          ← UserConfig type alias
├── core/
│   └── state.py         ← SessionState.user_config (runtime)
└── utils/config/
    └── user_configuration.py  ← load/save/merge functions
```

### Delete (Dead Code)

```
src/tunacode/configuration/settings.py:
  - Line 23: self.name = APP_NAME
  - Line 24: self.guide_file = f"{self.name.upper()}.md"
  - Lines 26-36: self.internal_tools = [...]

src/tunacode/configuration/defaults.py:
  - Line 30: "max_buffer_size": 1048576
  - Line 33: "debug": False
  - Line 37: "timeout": 5.0
  - Line 38: "max_diagnostics": 20

src/tunacode/tools/grep.py:
  - Line 52: "max_buffer_size": 1048576
  - Line 55: "debug": False
```

### Consolidate (Remove Duplication)

1. **Ripgrep defaults:** Keep only in `defaults.py`, remove from `grep.py`
2. **Guide file:** Use `GUIDE_FILE_NAME` constant in `agent_config.py` instead of hardcoded string

---

## Key Patterns / Solutions Found

- **Shallow copy bug (JOURNAL.md:513-542):** Fixed by using `deepcopy()` or reference replacement
- **Defensive access:** All config reads use `.get(key, fallback)` pattern
- **Implicit schema:** No TypedDict, schema documented by default values themselves
- **Reference replacement:** Setup replaces `session.user_config` reference, never mutates

---

## Recommended Cleanup Order

1. **Delete dead fields** from `defaults.py` (4 fields)
2. **Delete dead attributes** from `ApplicationSettings` (3 attributes)
3. **Remove duplicate ripgrep defaults** from `grep.py`
4. **Replace hardcoded guide file string** in `agent_config.py` with constant

**Estimated scope:** ~30 lines deleted across 4 files. No behavioral changes.

---

## External Storage Paths

| Path | Purpose | Code Reference | Notes |
|------|---------|----------------|-------|
| `~/.config/tunacode.json` | User config | `configuration/settings.py:16-17` | Hardcoded `~/.config/` |
| `~/.tunacode/device_id` | Anonymous telemetry UUID | `paths.py:85-100` | Uses `TUNACODE_HOME_DIR` |
| `~/.tunacode/sessions/{session_id}/` | **Temp runtime files** | `paths.py:30-42` | Cleaned up on exit |
| `~/.local/share/tunacode/sessions/` | **Persistent session JSON** | `paths.py:72-82` | XDG-compliant |
| `~/.local/share/tunacode/logs/` | Log files | `logging/handlers.py:70-76` | XDG-compliant |

**Not legacy:** Both session paths serve different purposes (temp vs persistent).

**Inconsistency:** Three location strategies - consider consolidating to XDG for everything.

---

## Config Merge Behavior

| Key | Merge Strategy | Risk |
|-----|----------------|------|
| `default_model` | User replaces default | Safe |
| `settings` | Recursively merged | Safe - preserves defaults |
| `env` | **NOT merged** - user replaces entirely | **Risk:** User deletes key → no fallback |

---

## References

- `src/tunacode/configuration/defaults.py` → Primary config definition
- `src/tunacode/configuration/settings.py` → ApplicationSettings (has dead code)
- `src/tunacode/core/state.py` → SessionState and StateManager
- `src/tunacode/utils/config/user_configuration.py` → Load/save/merge functions
- `src/tunacode/tools/grep.py` → Duplicate ripgrep config
- `.claude/JOURNAL.md:513-542` → Shallow copy bug history
