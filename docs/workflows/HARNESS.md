---
title: Harness Workflow
summary: Workflow guidance for harness-related verification and enforcement work.
when_to_read:
  - When working on harness checks
  - When auditing pre-commit or pre-push enforcement
last_updated: "2026-04-04"
---

# Harness Work

Use this workflow when changing, auditing, or debugging the repository harness.

Harness work here is mostly code-level enforcement: lint rules, type checks,
test gates, validation scripts, git hooks, and CI wiring that turns those
checks into repository policy.

## Intent

The goal of harness work is to improve enforcement clarity without creating
mystery behavior. Every rule should have an obvious owner, a concrete
execution path, and a clear reason for existing.

## Working Rules

- Treat any mismatch between documented and actual enforcement as a real defect.
- Prefer explicit failure messages over silent or confusing behavior.
- Keep local hooks and CI expectations aligned.
- Prefer enforcement that runs from repository code and config, not fragile
  machine-local state.
- Do not weaken enforcement just to get a green run unless the repository has
  explicitly decided to change the rule.
- Audit the real commands manually when a wrapper or aggregate command fails.

## Scope

Harness work includes:

- lint and formatting enforcement
- type checking and structural tests
- `pre-commit` and `pre-push` hooks
- validation scripts under `scripts/`
- architecture and repository policy gates
- CI workflows under `.github/workflows/`
- operator-facing harness documentation such as `HARNESS.md`

## Verification

Harness changes need proof at the level where they execute.

Preferred verification includes:

- running the exact lint or validation command that the rule wraps
- running the affected hook directly
- running the underlying script directly
- confirming the same rule is enforced in CI when that is part of the contract
- confirming failure behavior with a real bad case when practical
- confirming documentation matches the actual enforcement path

When auditing harness behavior, do not rely only on umbrella commands if the
point is to understand which exact gate failed.

## Done Criteria

Harness work is ready when all of the following are true:

- the enforcement behavior is clear and reproducible
- the documented workflow matches the actual checks
- local and CI expectations are aligned or the difference is documented
- the code-level enforcement path is easier to understand after the change
- failure messages are specific enough to act on
- the change does not create hidden or path-dependent behavior
