---
description: Smart deploy command that commits and pushes code, automatically fixing any commit hook issues
allowed-tools: Bash(git:*), Edit(*), Read(*)
---

# Deploy Command - Smart Commit and Push

Intelligently commits and pushes your code changes. If commit hooks fail, automatically fixes the issues and retries.

## Current Repository Status
- Status: !`git status --porcelain`
- Branch: !`git branch --show-current`
- Remote: !`git remote -v | head -n1`

## Process

1. **Check for changes**
   - Verify there are changes to commit
   - Show current uncommitted changes

2. **Stage and commit changes**
   - Stage all changes
   - Create commit with message: $ARGUMENTS
   - If no message provided, analyze changes and generate appropriate commit message

3. **Handle commit hooks**
   - If commit succeeds → proceed to push
   - If commit fails due to hooks:
     - Identify the specific issue (linting, formatting, tests)
     - Automatically fix the issues:
       - Run linters/formatters if available (prettier, black, ruff, eslint, etc.)
       - Fix simple syntax errors
       - Update imports if needed
     - Retry the commit

4. **Push to remote**
   - Push to current branch's upstream
   - If no upstream, set it and push
   - Handle any push conflicts if they arise

5. **Verify deployment**
   - Confirm push was successful
   - Show the commit hash and branch

## Error Handling

- If linting fails: Run appropriate linters and fix issues
- If tests fail: Identify failing tests and provide fixes
- If formatting fails: Run formatters and stage changes
- If push fails: Check for conflicts and resolve
- If a unique issue prevents you from pushing STOP and ask user for next steps after providing a summary

## Your task
Commit message (optional): $ARGUMENTS
