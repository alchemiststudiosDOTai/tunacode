# Small Wins Audit Plan

## Goals
1. Identify quick, surgical improvements that can be batched into small PRs
2. Document dead code, unused exports, and configuration drift
3. Find low-effort, high-impact cleanup opportunities
4. Catalog technical debt without making changes

## Constraints
- **READ-ONLY**: This audit documents only; no modifications performed
- **Scope**: Focus on `src/tunacode/` and `tests/` directories
- **Time Target**: Findings should be implementable in <=1 hour batches
- **PR Size**: Recommendations target <=10 files per PR

## Categories Scanned

### A. Structure & Naming
- Directory organization anomalies
- Naming convention violations
- Duplicate/orphan modules

### B. Dead Code & Orphans
- Unused functions/classes
- Orphan files not imported
- Technical debt markers (TODO/FIXME)
- Unused constants and exports

### C. Lint & Config Drifts
- Ruff check results
- Mypy type errors
- Configuration inconsistencies

### D. Micro-Performance/Clarity
- Long functions (>100 lines)
- High cyclomatic complexity
- Large files needing split

## Methodology
- Deployed 3 parallel subagents (codebase-locator, codebase-analyzer, context-synthesis)
- Ran ruff and mypy for automated detection
- Vulture for dead code detection
- Manual grep for technical debt markers

## Output
- `reports/SMALL_WINS_AUDIT.md` - Full findings report
