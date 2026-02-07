## Description
<!-- Provide a brief description of the changes in this PR -->

## Pre-PR Checklist
<!-- These must be done BEFORE opening the PR -->
- [ ] **Rebased onto master** (`git fetch origin && git rebase origin/master`)
- [ ] **All pre-commit hooks pass** (`uv run pre-commit run --all-files`)
- [ ] Tech debt baseline updated (if adding TODO/FIXME markers: `uv run python scripts/todo_scanner.py --output scripts/todo_baseline.json`)

## Type of Change
<!-- Mark the relevant option with an "x" -->
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Test improvement
- [ ] Refactoring (code improvement without changing functionality)
- [ ] Tool/Agent enhancement (improvements to LLM tools or agents)

## Testing
<!-- Describe the tests you ran to verify your changes -->
- [ ] All existing tests pass (`uv run pytest`)
- [ ] New tests have been added to cover the changes
- [ ] Tests have been run locally
- [ ] Golden/character tests established for new features

### Test Coverage
<!-- If applicable, mention the test coverage for new code -->
- Current coverage: ___%
- Coverage after changes: ___%

## Pre-commit Checks
- [ ] All pre-commit hooks pass
- [ ] Code formatted with `ruff format`
- [ ] Code passes `ruff check` without warnings
- [ ] No Python file exceeds **600 lines**

## Checklist
- [ ] My code follows the Python coding standards (type hints, f-strings, pathlib, etc.)
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code where necessary, particularly in hard-to-understand areas
- [ ] I have updated documentation in `@documentation/` and `.claude/` directories
- [ ] My changes generate no new warnings
- [ ] Dependencies are properly managed in `pyproject.toml`
- [ ] Any dependent changes have been merged and published
- [ ] Created rollback point with clear commit message before changes

## Documentation Updates
<!-- Mark which documentation has been updated -->
- [ ] Updated relevant files in `@documentation/`
- [ ] Updated developer notes in `.claude/`
- [ ] README.md updated (if needed)

## Additional Notes
<!-- Add any additional notes, screenshots, or context about the PR here -->

> PRs will fail CI if formatting/linting or file length rules are violated.
> **Rebase required:** This project changes frequently. Rebase onto master before opening your PR.
> **All pre-commit hooks must pass.** You can open a draft PR anytime, but **when marked ready for review, all checks must pass or the PR will be closed.** If dev setup isn't working, open an issue first.
