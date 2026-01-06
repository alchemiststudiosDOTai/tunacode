# Research - Update Command Implementation Analysis

**Date:** 2026-01-06
**Owner:** Claude Code
**Phase:** Research
**last_updated:** 2026-01-06
**last_updated_by:** Claude Code
**git_commit:** bd14622f982b5d6e934f334783c154ab9af1705e
**git_branch:** master
**tags:** ["update", "commands", "version", "pypi"]

## Goal

Map out existing update mechanism and version management in tunacode codebase before implementing `/update` command.

## Additional Search

- `grep -ri "update" .claude/` - No existing research on update commands in kb-claude

## Findings

### TL;DR: The `/update` command already exists and is fully implemented

The `/update` command is **already implemented** in the codebase with full functionality. It supports:
- `/update check` - Check if a newer version is available on PyPI
- `/update install` - Install the latest version with user confirmation

### Relevant files & why they matter

| File | Purpose | Key Details |
|------|---------|-------------|
| `src/tunacode/ui/commands/__init__.py:316-389` | Main command implementation | `UpdateCommand` class with check/install subcommands |
| `src/tunacode/utils/system/paths.py:161-191` | PyPI version checking | `check_for_updates()` uses `pip index versions` |
| `src/tunacode/ui/screens/update_confirm.py` | Update confirmation modal | User must confirm before installing |
| `src/tunacode/constants.py:12` | Current version | `APP_VERSION = "0.1.10"` |
| `src/tunacode/ui/commands/__init__.py:13-15` | Package name constants | `PACKAGE_NAME = "tunacode-cli"`, `UPDATE_INSTALL_TIMEOUT_SECONDS = 120` |

### Command System Architecture

**Base Pattern:**
- Commands inherit from `Command` ABC at `src/tunacode/ui/commands/__init__.py:37-47`
- Each command has `name`, `description`, `usage` attributes
- Commands implement `async def execute(self, app: TextualReplApp, args: str) -> None`
- Commands registered in `COMMANDS` dict at `src/tunacode/ui/commands/__init__.py:391-401`

**Existing Commands:**
- `/help` - Show available commands
- `/clear` - Clear conversation history
- `/yolo` - Toggle auto-confirm
- `/model` - Model picker/switch
- `/branch` - Create git branch
- `/plan` - Toggle planning mode (not yet implemented)
- `/theme` - Theme picker/switch
- `/resume` - Resume previous session
- `/update` - Check/install updates

### Update Command Implementation Details

**Version Check (`check_for_updates` at `src/tunacode/utils/system/paths.py:161-191`):**
```python
def check_for_updates():
    # Uses subprocess to run: pip index versions tunacode-cli
    # Parses "Available versions:" output
    # Compares latest version against current_version from ApplicationSettings
    # Returns (has_update: bool, latest_version: str)
```

**Update Flow:**
1. User runs `/update check` or `/update install`
2. Calls `check_for_updates()` via `asyncio.to_thread`
3. For `install`:
   - If no update: notifies "Already on latest version"
   - If update available: Shows `UpdateConfirmScreen` modal
   - User confirms with 'y' or cancels with 'n'/'Esc'
   - Runs package manager (prefers `uv`, falls back to `pip`)
   - Command: `uv pip install --upgrade tunacode-cli` or `pip install --upgrade tunacode-cli`
   - Timeout: 120 seconds

**Package Manager Detection (`_get_package_manager_command` at `src/tunacode/ui/commands/__init__.py:18-34`):**
- Searches for `uv` first via `shutil.which("uv")`
- Falls back to `pip` if `uv` not found
- Returns `(command_list, manager_name)` tuple

### Version Management

**Current Version Source:**
- `APP_VERSION = "0.1.10"` in `src/tunacode/constants.py:12`
- Also available via `ApplicationSettings().version` (reads from constants)

**Version Comparison:**
- Uses simple string comparison: `if latest_version > current_version`
- Relies on PyPI's version ordering

## Key Patterns / Solutions Found

| Pattern | Description |
|---------|-------------|
| **Command ABC pattern** | All TUI commands inherit from `Command` base class |
| **Async command execution** | Commands use `async def execute()` for non-blocking operations |
| **Screen modals for confirmation** | User-confirmable actions use `Screen[bool]` with `push_screen_wait()` |
| **Package manager abstraction** | Uses `shutil.which()` to detect available tools (uv > pip) |
| **Subprocess for version checking** | Uses `pip index versions` rather than HTTP requests to PyPI |
| **NeXTSTEP UI patterns** | Modal follows constants-based layout (MODAL_WIDTH, PADDING, etc.) |

## Knowledge Gaps

None - the `/update` command is fully implemented and functional.

## Implementation is Complete

Since the `/update` command already exists, no new implementation is needed. The command provides:
- Version checking against PyPI
- User confirmation before install
- Automatic package manager detection (uv/pip)
- Proper timeout handling
- Rich UI feedback

If there are specific enhancements needed (e.g., different behavior, additional features), those would be modifications to the existing implementation rather than new code.

## References

- **Command System:** `src/tunacode/ui/commands/__init__.py:37-430`
- **Update Command:** `src/tunacode/ui/commands/__init__.py:316-389`
- **Update Checker:** `src/tunacode/utils/system/paths.py:161-191`
- **Confirmation Screen:** `src/tunacode/ui/screens/update_confirm.py`
- **Version Constant:** `src/tunacode/constants.py:12`

## GitHub Permalinks

- [Update Command Implementation](https://github.com/alchemiststudiosDOTai/tunacode/blob/bd14622f982b5d6e934f334783c154ab9af1705e/src/tunacode/ui/commands/__init__.py#L316-L389)
- [Version Check Function](https://github.com/alchemiststudiosDOTai/tunacode/blob/bd14622f982b5d6e934f334783c154ab9af1705e/src/tunacode/utils/system/paths.py#L161-L191)
- [Update Confirmation Screen](https://github.com/alchemiststudiosDOTai/tunacode/blob/bd14622f982b5d6e934f334783c154ab9af1705e/src/tunacode/ui/screens/update_confirm.py)
- [Command System Base](https://github.com/alchemiststudiosDOTai/tunacode/blob/bd14622f982b5d6e934f334783c154ab9af1705e/src/tunacode/ui/commands/__init__.py#L37-L47)
