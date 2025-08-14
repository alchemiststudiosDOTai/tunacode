````markdown
---
allowed-tools: Edit, View, Bash(*)
description: Scans the codebase for common code smells, ranks them, and generates a remediation roadmap
---

# Find Common Smells

Detect and prioritize code smells for: $ARGUMENTS

## Context Gathering

I'll analyze the codebase structure and gather metrics.

### Check Directory Structure

- Identify main source directories
- Count Python files and total lines of code
- Find largest files by line count
- Identify most frequently modified files

### Analyze Code Complexity

- Calculate cyclomatic complexity for functions
- Find functions with high complexity (>10)
- Identify deeply nested code blocks
- Measure function lengths

### Detect Duplication

- Find repeated code blocks
- Identify similar function patterns
- Check for copy-pasted imports
- Measure overall duplication percentage

### Review Git History

- Files with highest churn rate
- Areas with many bug fix commits
- Recently modified hotspots

## Planning Phase

Create SMELLS_REPORT.md with:

1. Severity-ranked smell categories (critical to cosmetic)
2. Affected file paths with metrics
3. Root-cause hypothesis
4. Proposed fix strategy

## Implementation Steps

### Step 1: Static Analysis

Run complexity analysis:

- Find functions with cyclomatic complexity > 10
- Identify maintainability index < 65
- Count function parameters > 5
- Measure nesting depth > 3

Validation: Ensure analysis output contains valid metrics
Expected outcome: Consolidated findings with file locations

### Step 2: Triage and Ranking

```python
# Ranking algorithm
# Priority 1: Security issues (eval, exec, pickle without validation)
# Priority 2: Reliability (missing error handling, resource leaks)
# Priority 3: Performance (nested loops, repeated I/O)
# Priority 4: Maintainability (complexity, duplication)
# Priority 5: Style (naming, formatting)
```
````

Group findings by category and assign severity scores.
Progress check: Count findings per severity level

### Step 3: Integration

- Write findings to SMELLS_REPORT.md with direct file links
- Create smell inventory with code snippets
- Map smells to specific line numbers
- Generate fix effort estimates

Compatibility check: Verify report contains all sections

### Step 4: Testing

- Unit: Verify smell detection accuracy
- Integration: Ensure all Python files analyzed
- Edge cases: Empty files, generated code, vendored libraries
- Performance: Full scan completes in reasonable time

### Step 5: Documentation

- Create remediation playbook with specific fixes
- Document prevention strategies
- Include code examples of fixes
- Add smell patterns to avoid

## Validation and Finalization

Run quality checks:

- Verify all Python files were analyzed
- Check report completeness
- Validate severity assignments
- Ensure actionable recommendations

Manual checklist:

- [ ] SMELLS_REPORT.md generated
- [ ] All critical issues identified
- [ ] Fix strategies documented
- [ ] Prevention measures included

## Success Criteria

- Critical smells: Maximum 5 remaining
- Mean cyclomatic complexity < 10
- Duplication rate < 3%
- All functions < 50 lines
- All files < 500 lines
- No security anti-patterns detected

## Rollback Plan

- Backup location: .backups/code-quality/
- Revert command: Use git to restore previous state
- Verification: Check report presence and validity

## Report Structure

SMELLS_REPORT.md will contain:

| Phase           | Focus                    | Key Files | Fix Approach                 | Priority |
| --------------- | ------------------------ | --------- | ---------------------------- | -------- |
| Critical        | Security vulnerabilities | [files]   | Replace unsafe patterns      | P0       |
| High Complexity | CC > 15, MI < 65         | [files]   | Split into smaller functions | P1       |
| Duplication     | >30 line clones          | [files]   | Extract to shared utilities  | P2       |
| Maintainability | Long files, dead code    | [files]   | Refactor and remove          | P3       |
| Style           | Inconsistent patterns    | [files]   | Apply formatting rules       | P4       |

Logic Overview:

1. Scan - Collect raw metrics via analysis tools
2. Triage - Map findings to categories and severity
3. Report - Generate SMELLS_REPORT.md with actionable items
4. Gate - Define quality thresholds for CI/CD
5. Remediate - Fix issues in priority order

```

```
