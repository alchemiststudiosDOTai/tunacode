# Feature Work

Use this workflow when adding or extending product behavior.

## Start

Create a dedicated feature worktree from the repo root:

```sh
git wt "feature:name"
```

This is the default entry point for feature development. Feature work should
happen in the generated worktree, not in the main checkout.

Use a clear branch name that describes the behavior being added. The branch
should read like scoped delivery work, not like a scratchpad.

## If `git wt` Is Missing

If `git wt` is not installed, install `git-wt` first from:

`https://github.com/k1LoW/git-wt`

After `git-wt` is available, create the feature worktree and then run:

```sh
make install
```

Run `make install` inside the new feature worktree so dependencies and the
local environment are ready before implementation starts.

## Intent

Feature branches should be clearly named and isolated. The point of this
workflow is to support parallel feature development, clean branch boundaries,
and multi-agent execution without collisions between unrelated changes.

## Working Rules

- Do feature work in the dedicated worktree, not in the main checkout.
- Keep the scope narrow to one deliverable behavior or one tightly related set
  of changes.
- Avoid mixing feature work with unrelated cleanup, refactors, or drive-by
  fixes.
- Keep the branch clearly labeled as feature delivery so other agents and
  reviewers can understand its purpose immediately.

## Verification

Each feature must prove it works.

Do not claim parity based only on compilation success, lint success, or a
high-level summary of the change. Those signals are useful, but they are not
enough to establish that the feature behaves correctly.

Verification should use real artifacts and real execution paths whenever
possible. Preferred evidence includes:

- deterministic automated tests
- capture-based verification
- replay-based verification
- direct execution of the real user-facing path

The goal is to leave behind evidence that the feature works in practice, not
just evidence that the code is syntactically valid.

## Done Criteria

Feature work is ready for review when all of the following are true:

- the feature was developed in a dedicated `git wt` worktree
- dependencies were installed in that worktree with `make install`
- the branch name clearly identifies the feature
- the implementation stays within the intended feature scope
- verification demonst
rates the feature works through real behavior
