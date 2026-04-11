---
title: Changelog Update Procedure
summary: Manual policy and workflow for refreshing CHANGELOG.md from merged pull requests.
when_to_read:
  - When asked to update CHANGELOG.md from recent PRs
  - When deciding whether a merged PR needs a changelog edit
last_updated: "2026-04-11"
---

# Changelog Updates

## Policy

- Updating `CHANGELOG.md` from merged PRs is a manual maintenance task.
- A PR merging to `master` does **not** automatically require its own changelog edit before merge.
- Do **not** treat changelog updates as a default merge blocker for normal PR flow.
- Refresh the `## [Unreleased]` section only when the user explicitly asks for it or when changelog coverage is explicitly part of the task being reviewed.

## Scope

Use this workflow when the goal is to summarize recently merged pull requests into `CHANGELOG.md`.

Do not use it to:
- add entries for open or unmerged PRs
- invent release notes without checking the merged PR content
- force every feature or fix PR to include a changelog change in the same branch

## Workflow

1. Identify the recent merged PRs on `master`.

   Example:

   ```bash
   gh pr list --state merged --base master --limit 5 \
     --json number,title,mergedAt,author,url
   ```

2. Inspect each relevant PR before summarizing it.

   Example:

   ```bash
   gh pr view 460 --json title,body,files,commits,url
   ```

3. Update `CHANGELOG.md` under `## [Unreleased]` using the existing Keep a Changelog headings already present in the file.

   Preferred headings:
   - `### Added`
   - `### Changed`
   - `### Fixed`
   - `### Removed` when needed

4. Write concise user-facing summaries.

   Rules:
   - summarize the merged outcome, not the implementation play-by-play
   - group related PRs into a small number of bullets when they land on the same theme
   - prefer behavior and operator impact over internal refactor detail
   - avoid duplicating every commit message verbatim

5. Update the document metadata in `CHANGELOG.md` when you edit it.

6. If the user asked for a commit, commit only the changelog/documentation files that are part of the requested update.

## Notes

- This workflow is intentionally not automated.
- The source of truth is the merged PR set plus the actual PR content, not branch names alone.
- If the task is ambiguous, clarify whether the user wants:
  - the last N merged PRs summarized into `Unreleased`, or
  - a release-specific changelog entry for a versioned cut
