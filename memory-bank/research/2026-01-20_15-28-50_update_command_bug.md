# Research - `/update` Command Bug

**Date:** 2026-01-20
**Owner:** Claude (context-engineer:research)
**Phase:** Research

## Goal

Investigate why the `/update` command is not working - user reports it "still just checks" instead of installing updates.

---

## Additional Search

```bash
grep -ri "push_screen_wait" .claude/
# No results - this is a new issue
```

---

## Findings

### Relevant Files & Why They Matter

| File | Why It Matters |
|------|----------------|
| `src/tunacode/ui/commands/__init__.py:420-493` | Contains `UpdateCommand` class with the bug |
| `src/tunacode/ui/screens/update_confirm.py:17-70` | `UpdateConfirmScreen` - modal screen for update confirmation (correctly implemented) |
| `src/tunacode/ui/app.py` | `TextualReplApp` class - missing the `push_screen_wait` method |
| `src/tunacode/utils/system/paths.py:161-190` | `check_for_updates()` function - works correctly |

---

## Root Cause: Missing `push_screen_wait` Method

**Location:** `src/tunacode/ui/commands/__init__.py:457`

```python
confirmed = await app.push_screen_wait(UpdateConfirmScreen(APP_VERSION, latest_version))
```

**The Bug:**
- `push_screen_wait` **does not exist** on `TextualReplApp`
- This method is never defined anywhere in the codebase
- Textual's standard API is `push_screen(screen, callback)`, not `push_screen_wait(screen)`
- The method name implies waiting for the screen result, but no such implementation exists

**Impact:**
- When user runs `/update` or `/update install` and an update is available
- Line 457 raises `AttributeError: 'TextualReplApp' object has no attribute 'push_screen_wait'`
- The confirmation screen never appears
- Update installation never proceeds
- User only sees the "Checking for updates..." notification, then the error (possibly hidden)

---

## Correct Pattern Used Elsewhere

All other screen pushes in the codebase use the callback pattern:

```python
# ModelCommand (line 208-211)
app.push_screen(
    ModelPickerScreen(provider_id, current_model),
    on_model_selected,  # callback receives result
)

# ThemeCommand (line 308-311)
app.push_screen(
    ThemePickerScreen(app.available_themes, app.theme),
    on_dismiss,  # callback receives result
)
```

The callback receives the screen's return value when dismissed.

---

## Control Flow Analysis

### When User Types `/update` (No Arguments)

1. `handle_command()` parses: `cmd_args = ""`
2. `UpdateCommand.execute()` receives `args = ""`
3. Line 432-433: Empty `parts` → `subcommand = "install"` (default)
4. Line 447: Enters `elif subcommand == "install"` block
5. Line 451: Checks for updates
6. Line 453-455: If no update, shows "Already on latest" → **WORKS**
7. Line 457: If update available → **CRASHES** - `push_screen_wait` doesn't exist

### When User Types `/update check`

1. `cmd_args = "check"`
2. `subcommand = "check"`
3. Line 435: Enters `if subcommand == "check"` block
4. Line 437: Checks for updates
5. Line 439-445: Displays version info → **WORKS**

---

## Expected vs Actual Behavior

| Command | Expected Behavior | Actual Behavior |
|---------|------------------|-----------------|
| `/update` (no update) | Shows "Already on latest" | Works correctly |
| `/update` (update available) | Shows confirmation screen, installs if confirmed | **CRASHES** at line 457 |
| `/update check` | Shows current and latest version | Works correctly |
| `/update install` | Same as `/update` | Same crash at line 457 |

---

## UpdateConfirmScreen Implementation (Correct)

The screen itself is correctly implemented:

- `Screen[bool]` - returns boolean result (line 17)
- `action_confirm()` - calls `self.dismiss(True)` (line 65-66)
- `action_cancel()` - calls `self.dismiss(False)` (line 68-69)
- Bindings: `y` to confirm, `n` or `escape` to cancel (lines 45-49)

The issue is purely in how it's being called.

---

## Code Path Diagram

**Check Path (Working):**
```
handle_command:519
  -> UpdateCommand.execute:425
    -> parse args at 432-433
    -> if subcommand == "check" at 435
      -> check_for_updates at 437
      -> display results at 439-445
```

**Install Path (Broken at line 457):**
```
handle_command:519
  -> UpdateCommand.execute:425
    -> parse args at 432-433
    -> elif subcommand == "install" at 447
      -> check_for_updates at 451
      -> if has_update at 453
        -> await app.push_screen_wait at 457 [CRASH - method doesn't exist]
        -> if confirmed at 459 [never reached]
        -> _get_package_manager_command at 463 [never reached]
        -> subprocess.run to install at 472-478 [never reached]
```

---

## Knowledge Gaps

1. **Should we implement `push_screen_wait` on `TextualReplApp`?**
   - Would require asyncio Future/Event coordination
   - Or refactor to use callback pattern like other commands

2. **Why wasn't this caught in testing?**
   - No dedicated tests for `/update` command found
   - Update flow likely not tested end-to-end

3. **Is there a similar pattern elsewhere in the codebase?**
   - Need to verify no other code expects `push_screen_wait`

---

## References

### Code Files
- `src/tunacode/ui/commands/__init__.py:420-493` - UpdateCommand class
- `src/tunacode/ui/commands/__init__.py:457` - Bug location
- `src/tunacode/ui/screens/update_confirm.py:17-70` - UpdateConfirmScreen
- `src/tunacode/utils/system/paths.py:161-190` - check_for_updates()

### Documentation
- `docs/codebase-map/modules/ui-overview.md:131` - Documents UpdateCommand
- `CHANGELOG.md:107` - `/update` command implementation (#182)
- `CHANGELOG.md:97` - Credits @ryumacodes for implementation

### GitHub Permalink (if on master)
- Not on master branch (current: 260)
