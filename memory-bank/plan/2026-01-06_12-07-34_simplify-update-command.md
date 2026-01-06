---
title: "Simplify /update Command – Plan"
phase: Plan
date: "2026-01-06T12:07:34"
owner: "Claude Code"
parent_research: "memory-bank/research/2026-01-06_update-command-analysis.md"
git_commit_at_plan: "bd14622"
tags: [plan, update, commands, ux]
---

## Goal

Simplify the `/update` command to a single-subcommand interaction: check for updates and immediately prompt to install if available.

**Non-goals:**
- Changing the underlying update mechanism (pip/uv)
- Modifying the confirmation screen UI
- Auto-updating without confirmation

## Scope & Assumptions

**In scope:**
- Modify `UpdateCommand.execute()` to combine check + confirm flow
- Remove explicit `check` and `install` subcommands
- Keep all error handling, timeout, and package manager detection logic

**Out of scope:**
- Changing `UpdateConfirmScreen`
- Modifying `check_for_updates()` in paths.py
- Changing version comparison logic

**Assumptions:**
- User wants `/update` (no args) to do the full flow
- Confirmation screen is reused as-is
- No changes to package manager detection (uv -> pip fallback)

## Deliverables

- Modified `UpdateCommand.execute()` method
- Updated `usage` string
- No new files or screens needed

## Readiness

**Preconditions:**
- Existing `UpdateCommand` at `src/tunacode/ui/commands/__init__.py:316-389`
- Existing `UpdateConfirmScreen` at `src/tunacode/ui/screens/update_confirm.py`
- Existing `check_for_updates()` at `src/tunacode/utils/system/paths.py:161-191`

**No new dependencies required.**

## Milestones

- **M1:** Simplify command flow to single entry point
- **M2:** Test the new `/update` behavior

## Work Breakdown (Tasks)

| Task | Summary | Owner | Est | Deps | Milestone | Acceptance Test | Files Touched |
|------|---------|-------|-----|------|-----------|-----------------|---------------|
| T1 | Simplify UpdateCommand.execute to single flow | Claude | 15m | - | M1 | Running `/update` checks and prompts if update available; shows "already latest" if not | `src/tunacode/ui/commands/__init__.py` |
| T2 | Update command usage string | Claude | 5m | T1 | M1 | `help` shows `/update` with no subcommands | `src/tunacode/ui/commands/__init__.py` |
| T3 | Manual test the new flow | Claude | 10m | T2 | M2 | Verify update/no-update paths work correctly | None |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Users may have scripts using `/update install` | Low | Consider keeping `install` as alias, or document breaking change |
| Version check fails silently | Low | Existing error handling in `check_for_updates()` already covers this |

## Test Strategy

- **T1:** Manual verification - run `/update` with and without updates available
- No new unit tests needed (reuses existing tested components)

## References

- Research: `memory-bank/research/2026-01-06_update-command-analysis.md`
- Target: `src/tunacode/ui/commands/__init__.py:316-389`

## Implementation Sketch

```python
class UpdateCommand(Command):
    name = "update"
    description = "Check for updates and install if available"
    usage = "/update"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        # Ignore args, always do the full flow
        app.notify("Checking for updates...")
        has_update, latest_version = await asyncio.to_thread(check_for_updates)

        if not has_update:
            app.notify(f"Already on latest version ({APP_VERSION})")
            return

        # Show confirmation immediately
        confirmed = await app.push_screen_wait(UpdateConfirmScreen(APP_VERSION, latest_version))
        if not confirmed:
            app.notify("Update cancelled")
            return

        # Install (reuse existing code)
        ...
```

## Final Gate

**Plan output:** `memory-bank/plan/2026-01-06_12-07-34_simplify-update-command.md`
**Milestones:** 2
**Tasks:** 3

**Ready to execute with:**
```bash
/context-engineer:execute "memory-bank/plan/2026-01-06_12-07-34_simplify-update-command.md"
```
