---
title: Exclude Markdown from Tech Debt Scans
link: tech-debt-scanner-markdown-exclusion
type: delta
path: scripts/todo_scanner.py
depth: 0
seams: [M, D]
ontological_relations:
  - relates_to: [[tech-debt-tracking]]
  - affects: [[ci-tech-debt-workflow]]
  - fixes: [[docs-triggered-debt-scan]]
tags:
  - tech-debt
  - scanner
  - ci
  - markdown
created_at: 2026-02-05T03:49:20Z
updated_at: 2026-02-05T03:49:20Z
uuid: 1520a635-625d-4465-bce8-c130cf40e966
---

# Exclude Markdown from Tech Debt Scans

## Summary

Markdown documentation contained example TODO/FIXME/HACK markers, which the scanner counted as new debt and caused baseline checks to fail. We now exclude `.md` files from scanning and update the scheduled workflow to flag any debt and report the correct timestamp.

## Context

- File: `scripts/todo_scanner.py`
- Symptoms: PR scans failed with debt coming from documentation examples; weekly reports never opened issues because the scan did not fail.

## Root Cause

The scanner did not exclude documentation files, and the scheduled workflow checked the baseline without any failure mode, so debt presence never produced a failing exit status.

## Changes

- Excluded Markdown files from `EXCLUDE_PATTERNS`.
- Documented Markdown exclusion in `docs/agent-docs/tech-debt-tracking.md`.
- Updated the scheduled workflow to use `--fail-on-new`, renamed steps, and fixed the report timestamp field.

## Behavioral Impact

- Markdown files are no longer scanned for debt markers.
- Weekly reports now open/update issues when any debt exists.
- PR baseline checks remain unchanged for code files.

## Related Cards

- [[tech-debt-tracking]]
