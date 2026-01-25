# Research – First-Run Experience Broken: No Config Created, Setup Fails

**Date:** 2026-01-24
**Owner:** Claude Agent
**Phase:** Research

## Goal

Investigate why first-time user experience is broken: no config file created on first-run, `--setup` fails with empty config, and config corruption occurs during setup with Chutes provider.

## Findings

### Problem 1: No Config File Created on First-Run - CONFIRMED

**Root Cause:** The configuration system is designed for lazy creation - config is only written when explicitly saved.

**Relevant files:**

| File | Role |
|------|------|
| `src/tunacode/utils/config/user_configuration.py:20-36` | `load_config()` returns `None` when file doesn't exist |
| `src/tunacode/core/state.py:143-172` | `_load_user_configuration()` uses defaults but never writes |
| `src/tunacode/configuration/defaults.py:11-41` | `DEFAULT_USER_CONFIG` provides in-memory defaults |

**Flow for first-time user:**

```
1. User runs `tunacode`
2. StateManager.__init__() → _load_user_configuration()
3. load_config() returns None (FileNotFoundError caught, returns None)
4. StateManager sets self._session.user_config = DEFAULT_USER_CONFIG.copy()
5. App runs with in-memory defaults
6. NO config file is created on disk
```

**Evidence from code:**

```python
# src/tunacode/utils/config/user_configuration.py:28-31
def load_config() -> UserConfig | None:
    try:
        with open(app_settings.paths.config_file) as f:
            return json.load(f)
    except FileNotFoundError:
        return None  # ← Silent return, no file created
```

```python
# src/tunacode/core/state.py:164-165
else:
    # No user config file found, use defaults
    self._session.user_config = DEFAULT_USER_CONFIG.copy()
    # ← Never calls save_config()
```

**Config file is only created when:**
- Setup wizard "Save & Start" clicked → `setup.py:214`
- `/model` command changes model → `commands/__init__.py:209`
- `/theme` command changes theme → `commands/__init__.py:329`

### Problem 2: --setup Doesn't Work on Empty/Missing Config - CONFIRMED

**Reproduction confirmed (2026-01-24):**

```
tuna@homeStation:~$ tunacode --setup
Traceback (most recent call last):
  File ".../user_configuration.py", line 29, in load_config
    return json.load(f)
  ...
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

The above exception was the direct cause of the following exception:
  ...
tunacode.exceptions.ConfigurationError: Invalid JSON in config file at /home/tuna/.config/tunacode.json
```

**Root Cause:** Empty config file exists at `~/.config/tunacode.json`

The `load_config()` function handles `FileNotFoundError` (missing file) but does NOT handle empty file gracefully:

```python
# src/tunacode/utils/config/user_configuration.py:28-34
def load_config() -> UserConfig | None:
    try:
        with open(app_settings.paths.config_file) as f:
            return json.load(f)  # ← CRASHES on empty file (char 0)
    except FileNotFoundError:
        return None  # ← Only handles missing file
    except JSONDecodeError as err:
        raise ConfigurationError(msg) from err  # ← Empty file raises this!
```

**Bug:** Empty file (`""`) causes `JSONDecodeError` at char 0, which raises `ConfigurationError` instead of falling back to defaults.

**Why empty file exists:** Previous failed run or manual creation left an empty file.

**Fix needed:** Treat empty file same as missing file:

```python
except JSONDecodeError as err:
    # Check if file is empty - treat same as missing
    if err.pos == 0:
        return None
    raise ConfigurationError(msg) from err
```

---

**Original analysis (before reproduction):**

**Expected behavior:** The setup wizard should work even without a config file because:
1. `StateManager` populates `user_config` with `DEFAULT_USER_CONFIG` on init
2. Setup wizard gets reference: `user_config = self.state_manager.session.user_config`
3. Mutates dict in-place, then calls `save_config()`

**Relevant files:**

| File | Role |
|------|------|
| `src/tunacode/ui/main.py:104` | `--setup` CLI flag definition |
| `src/tunacode/ui/app.py:157-160` | Pushes `SetupScreen` if `show_setup=True` |
| `src/tunacode/ui/screens/setup.py:170-218` | Setup wizard save logic |

**Other possible failure modes:**
1. **Missing nested dict:** If `DEFAULT_USER_CONFIG` changes and `"env"` or `"settings"` keys are missing, setup would fail at line 202-208
2. **Provider not in registry:** If user selects a provider not in `models_registry.json`, `get_provider_env_var()` falls back to `{PROVIDER}_API_KEY` but `get_provider_base_url()` returns `None`
3. **Permissions error:** `save_config()` creates `~/.config/` with `0o700` - could fail if parent dir has issues

**Current flow appears correct (when config loads):**

```python
# src/tunacode/ui/screens/setup.py:199-214
user_config = self.state_manager.session.user_config  # Gets defaults
user_config["default_model"] = full_model
if "env" not in user_config:
    user_config["env"] = {}  # Creates if missing
user_config["env"][env_var] = api_key
if base_url:
    if "settings" not in user_config:
        user_config["settings"] = {}  # Creates if missing
    user_config["settings"][SETTINGS_BASE_URL] = base_url
save_config(self.state_manager)  # Writes to disk
```

### Problem 3: Config "Corruption" - USER INPUT ISSUE (Not a bug)

**Reported "corruption":**
```json
"CHUTES_API_KEY": "\"CHUTES_API_KEY\": \"\\\"base_url\\\": \\\"https://llm.chutes.ai/v1\\\"\""
```

**Root cause:** User pasted malformed/garbage text into the API key input field. The setup wizard correctly stored exactly what was pasted.

**Chutes provider IS registered:**
```json
{
  "id": "chutes",
  "env": ["CHUTES_API_KEY"],
  "api": "https://llm.chutes.ai/v1",
  "name": "Chutes"
}
```

**This reveals a UX issue:** No validation on API key input.

Current validation (`setup.py:191-193`):
```python
if not api_key:
    error_label.update("API key is required")
    return
```

This only checks if the field is empty - it accepts ANY non-empty string.

**Recommended fix:** Add basic API key format validation:
- Check for reasonable length (most keys are 32-128 chars)
- Check for expected prefix patterns (e.g., `sk-`, `key-`, alphanumeric)
- Warn if input contains JSON-like characters (`{`, `}`, `":`)

## Key Patterns / Solutions Found

### Pattern: Lazy Config Creation
- **Description:** Config file only created on explicit save action
- **Impact:** First-time users run with in-memory defaults until they change a setting
- **Fix:** Add `save_config()` call after `_load_user_configuration()` when config is None

### Pattern: Provider Fallback
- **Description:** Unknown providers get generated env var name `{PROVIDER}_API_KEY`
- **Impact:** Users can use unlisted providers but without base_url support
- **Fix:** Consider adding a way to specify custom providers with base_url in setup

### Pattern: Error Handling
- **Description:** `load_config()` silently returns None on FileNotFoundError
- **Impact:** App starts fine without config, but users don't know config was never created
- **Fix:** Log a message when using defaults, or create config on first run

## Systematic Error Handling Audit (2026-01-24)

### Why the initial analysis missed the bug

1. Read code and saw `except FileNotFoundError: return None`
2. Assumed "handles missing file = handles first-run"
3. Didn't consider that **empty file existing ≠ no file**
4. Kept saying "needs reproduction" instead of trusting the user
5. Focused on "happy path" instead of tracing all exception paths

### The Contract Violation

`load_config()` docstring says:
```
Returns None when the config file does not exist.
Raises ConfigurationError for invalid JSON or other failures.
```

But **ALL 4 callers assume it only returns `UserConfig | None`** - none catch exceptions:

| Caller | Location | Code | Catches Exception? |
|--------|----------|------|-------------------|
| StateManager init | `state.py:150` | `user_config = load_config()` | NO |
| Agent config | `agent_config.py:250` | `config = load_config()` | NO |
| Limits (cached) | `limits.py:31` | `config = load_config()` | NO |
| Tool decorators | `decorators.py:52` | `user_config = load_config() or {}` | NO (`or {}` only handles None) |

### All Unhandled Failure Modes

| Scenario | What Happens | User Impact |
|----------|--------------|-------------|
| Empty file (`""`) | `JSONDecodeError` at pos 0 → `ConfigurationError` | **CRASH on startup** |
| Malformed JSON (`{foo}`) | `JSONDecodeError` → `ConfigurationError` | **CRASH on startup** |
| JSON array (`[]`) | Returns `[]`, later `TypeError` on `.get()` | **CRASH later** |
| JSON null (`null`) | Returns `None`, treated as "no config" | Silent fallback (OK?) |
| JSON string (`"hello"`) | Returns `"hello"`, later `TypeError` on `.get()` | **CRASH later** |
| Valid JSON, wrong structure | May work or crash depending on access pattern | **Unpredictable** |
| Permission denied read | `Exception` → `ConfigurationError` | **CRASH on startup** |

### Root Cause

The function contract says "I raise exceptions" but callers don't honor it. Two ways to fix:

**Option A: Change callers** - Wrap all 4 call sites in try/except

**Option B: Change function** - Make `load_config()` NEVER raise, always return `None` on ANY error

Option B is simpler and matches what callers expect.

### Cascade Effect

Because `limits.py:_load_settings()` is `@lru_cache` decorated:
- First call with corrupt config → CRASH
- Exception gets cached? (need to verify lru_cache behavior with exceptions)

Because `state.py` loads at module import time (`main.py:25`):
```python
# main.py:25 - MODULE LEVEL, runs at import!
state_manager = StateManager()
```
- `from tunacode.ui.main import app` triggers `StateManager()`
- `StateManager.__init__()` calls `_load_user_configuration()`
- `_load_user_configuration()` calls `load_config()`
- Any config error crashes before CLI even parses `--setup` flag

**This is a design flaw:** Module-level initialization that can fail prevents ANY error recovery.

### CLI Failure Policy Violation

**The CLI entry point is allowed to fail without any constraints. This is unacceptable.**

A command-line tool MUST:
1. Always attempt to run, even with invalid config
2. Provide error messages that guide users to recovery
3. Never fail silently or crash before giving actionable feedback
4. Support recovery modes (like `--setup`) even when normal operation is blocked

**Current behavior violates all of these:**
- Module-level `StateManager()` crashes on config errors before CLI args are parsed
- `--setup` cannot be used to fix config because the crash happens first
- `--help` and `--version` likely also crash (unconfirmed but same risk)
- User has NO path to recovery short of manually editing/deleting config files

**This is a CLI design anti-pattern.** The entry point should be the most failure-resistant part of the application, not the most fragile.

### Additional Design Issues Found

1. **Module-level StateManager** (`main.py:25`) - Should be lazy-initialized
2. **No graceful degradation** - Invalid config = total crash, not "use defaults"
3. **--setup is useless** - Can't run setup to fix config because config crash happens first
4. **Circular dependency on config** - Even `--help` or `--version` might crash (need to verify)

## Knowledge Gaps

1. **Config file path discrepancy** - Code says `~/.config/tunacode.json` but constants.py has `TUNACODE_HOME_DIR = ".tunacode"` - need to verify actual path used
2. **lru_cache exception behavior** - VERIFIED: `@lru_cache` does NOT cache exceptions. Function re-executes on each call until success. So `limits.py` will crash repeatedly, not cache the crash.

## Recommended Fixes

### Fix 1: Handle empty config file gracefully
**Location:** `src/tunacode/utils/config/user_configuration.py:32-34`

**Priority: HIGH** - This is the immediate crash blocker.

```python
except JSONDecodeError as err:
    # Treat empty file same as missing file
    if err.pos == 0:
        return None
    msg = f"Invalid JSON in config file at {app_settings.paths.config_file}"
    raise ConfigurationError(msg) from err
```

### Fix 2: Create config on first-run
**Location:** `src/tunacode/core/state.py:164-165`

```python
else:
    # No user config file found, use defaults and create file
    self._session.user_config = DEFAULT_USER_CONFIG.copy()
    from tunacode.utils.config import save_config
    save_config(self)  # ← Add this line
```

### Fix 3: Add API key validation
**Location:** `src/tunacode/ui/screens/setup.py:191-193`

Add basic sanity checks before saving:
```python
# Check for suspicious input patterns
if any(c in api_key for c in ['{', '}', '":"']):
    error_label.update("API key appears malformed - check you copied only the key")
    return

# Check reasonable length
if len(api_key) < 10 or len(api_key) > 256:
    error_label.update("API key length seems wrong - check your key")
    return
```

### Fix 4: Add config path consistency check
**Location:** `src/tunacode/configuration/settings.py`

Verify config path matches documented behavior:
```python
# Current: ~/.config/tunacode.json
# Expected per constants.py: ~/.tunacode/tunacode.json
```

## Summary of All Issues Found

### Critical (Crashes app)

| Issue | Location | Impact |
|-------|----------|--------|
| Empty config file crashes app | `user_configuration.py:32-34` | Can't run `--setup` to fix |
| Malformed JSON crashes app | `user_configuration.py:32-34` | Same |
| No callers catch `ConfigurationError` | 4 call sites | Any config error = crash |
| Module-level `StateManager()` | `main.py:25` | Crash happens at import time |
| **CLI allowed to fail without constraints** | `main.py` entry point | **User cannot recover from ANY error** |

### Design Issues

| Issue | Location | Impact |
|-------|----------|--------|
| Config scattered across 3 dirs | `settings.py`, `paths.py` | Confusing, inconsistent |
| `TUNACODE_HOME_DIR` defined but unused for config | `constants.py:110` | Dead/misleading constant |
| No graceful degradation | `state.py` | Invalid config = crash, not "use defaults" |
| `--setup` can't fix broken config | N/A | Catch-22 for users |

### UX Issues

| Issue | Location | Impact |
|-------|----------|--------|
| No API key validation | `setup.py:191-193` | Garbage in = garbage out |
| No config created on first run | `state.py:163-172` | Actually fixed! But error handling masks it |

## References

- `src/tunacode/utils/config/user_configuration.py` - load_config/save_config
- `src/tunacode/core/state.py` - StateManager config loading
- `src/tunacode/ui/screens/setup.py` - Setup wizard
- `src/tunacode/configuration/defaults.py` - DEFAULT_USER_CONFIG
- `src/tunacode/configuration/models.py` - Provider registry functions
- `src/tunacode/constants.py` - CONFIG_FILE_NAME, TUNACODE_HOME_DIR

## Config Path Investigation

**THREE different locations for tunacode data - INCONSISTENT:**

| What | Path | Source |
|------|------|--------|
| User config | `~/.config/tunacode.json` | `settings.py:16-17` |
| Home dir (sessions, device_id) | `~/.tunacode/` | `paths.py:25` via `TUNACODE_HOME_DIR` |
| XDG session storage | `~/.local/share/tunacode/sessions/` | `paths.py:79-80` |

**The mess:**

1. `constants.py:110` defines `TUNACODE_HOME_DIR = ".tunacode"`
2. `settings.py:16` IGNORES this and hardcodes `Path.home() / ".config"`
3. `paths.py:25` USES `TUNACODE_HOME_DIR` for `~/.tunacode/`
4. `paths.py:79` ALSO uses XDG for sessions: `~/.local/share/tunacode/sessions/`

**Result:** User data is scattered across 3 locations:
- Config in `~/.config/`
- Device ID in `~/.tunacode/`
- Sessions in BOTH `~/.tunacode/sessions/` AND `~/.local/share/tunacode/sessions/`

**Questions:**
1. Why does `settings.py` not use `TUNACODE_HOME_DIR`?
2. Why are there TWO session directories?
3. What happens if user has data in one location but app looks in another?

**Recommendation:** Consolidate all tunacode data under ONE location (either `~/.tunacode/` or XDG-compliant paths, not both)
