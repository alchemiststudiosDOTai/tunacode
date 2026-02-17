# Small Wins Audit Plan

## Goals
- Identify surgical, low-risk improvements (XS/S effort) across the tunacode codebase
- Document findings without making any modifications
- Produce a single actionable report at `reports/SMALL_WINS_AUDIT.md`

## Constraints
- **Read-only**: No edits, no refactors, no PRs
- **Detection + documentation only**
- Tools used: ruff, mypy, radon, vulture, grep, glob, subagent research

## Categories Scanned
1. **Structure & Naming** -- directory oddities, dead folders, naming violations
2. **Dead Code & Orphans** -- unused symbols, TODO debt, unreferenced files
3. **Lint & Config Drifts** -- ruff, mypy, radon complexity, vulture dead code
4. **Micro-Performance/Clarity** -- hot paths by complexity, long functions

## Data Sources
- 3 parallel subagents: codebase-locator, codebase-analyzer, context-synthesis
- 4 parallel linters: ruff, mypy, radon (C+ complexity), vulture
- Manual file counts and test coverage gap analysis
