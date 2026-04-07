# Git Practices

## Purpose
This document defines safe Git operating practices for humans and code agents working in this repository.

Primary goal: preserve developer work while keeping commits clean and reviewable.

## Non-destructive Default (Hard Rule)
- Treat all untracked files/directories as potentially intentional work.
- Do **not** delete untracked files/directories by default.
- Do **not** run destructive cleanup commands (`git clean -fd`, `rm -rf`, bulk restores) unless the user explicitly asks.

## Required Process When New Files or Directories Appear
1. Detect and report: run `git status --short` and list what is new.
2. Classify with the user:
   - intentional project artifact
   - temporary/generated output
   - unknown
3. Ask for explicit confirmation before deletion or cleanup.
4. If confirmation is not provided, leave files in place.

## Pre-commit / Tooling Side Effects
Some hooks/tools may modify tracked files or create temporary outputs.

When this happens:
1. Report exactly what changed.
2. Revert only the files that were auto-modified **if requested**.
3. Do not remove untracked files/directories without confirmation.
4. Re-run checks after any requested revert.

## Commit-Time Failure Handling (Agent Rule)
When a commit attempt triggers failing checks (pre-commit, lint, type checks, tests):
1. Do **not** make architectural or refactor decisions on your own to "get green".
2. Do **not** expand scope beyond the requested task.
3. Only apply trivial, mechanical lint fixes if they are clearly local and non-architectural (e.g., formatting, import order, whitespace).
4. If the failure is not a trivial lint blocker, stop and report the exact blocker to the user.
5. Wait for explicit user instruction before making broader code changes.

## Issue, PR, And Change Labels
When describing work in issue titles, PR titles, task summaries, commit drafts, or handoff notes, use an explicit leading label so the intent is obvious at a glance.

Required format:
- `<label>: <short description>`

Examples:
- `bug: fix session crash when stdin closes`
- `refactor: split command registry into smaller modules`
- `bug: prevent duplicate tool execution in PR retry flow`
- `refactor: simplify PR status rendering in the UI`
- `docs: clarify non-destructive git cleanup policy`
- `test: add regression coverage for tool-loop retries`
- `chore: refresh pre-commit hook versions`

Rules:
- Do not leave issue or task types implied; label them explicitly.
- Prefer specific labels such as `bug:`, `refactor:`, `docs:`, `test:`, `chore:`, or another short category that matches the work.
- Use one primary label per item based on the dominant intent.
- If the work is bug-driven, label it `bug:` even if the fix also includes refactoring.
- Keep the description after the label concrete and reviewable.

## Safe Cleanup Policy
Cleanup is allowed only when one of the following is true:
- the user explicitly requested cleanup, or
- the repository has a documented generated-path policy and the path matches that policy.

If cleanup is authorized, state the exact command before running it.

## Commit Hygiene Checklist
Before commit/push:
- `git status --short` is reviewed.
- Commit scope matches the requested task.
- No unrelated local changes are included.
- Any untracked files are either intentionally kept or explicitly handled per user instruction.

## Related Docs
- `AGENTS.md`
- `HARNESS.md`
