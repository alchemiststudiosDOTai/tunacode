# Code Smells Report - TunaCode

Generated on: 2025-07-26

## Executive Summary

Analysis of 219 Python files (32,163 lines of code) revealed several areas for improvement:

- **Critical Issues**: 0 security vulnerabilities found
- **High Complexity**: 2 functions with very high cyclomatic complexity
- **Large Files**: 1 file exceeds 1000 lines
- **High Churn**: 3 files with >40 commits in 6 months
- **Structural Issues**: 1 class with >20 methods, 3 functions with >5 parameters

## Detailed Findings

### Priority 1: High Complexity (Critical)

| File | Issue | Complexity | Location | Fix Approach |
|------|-------|------------|----------|--------------|
| src/tunacode/core/agents/main.py:223 | _process_node function | CC=94 | Lines 223-487 (265 lines) | Split into smaller specialized functions for each node type |
| src/tunacode/core/agents/main.py:761 | process_request function | CC=85 | Lines 761-1146 (386 lines) | Extract validation, processing, and response handling |

### Priority 2: File Size & Structure

| File | Issue | Metrics | Fix Approach |
|------|-------|---------|--------------|
| src/tunacode/core/agents/main.py | Extremely large file | 1146 lines | Split into modules: tool_execution.py, message_processing.py, agent_factory.py |
| src/tunacode/tools/grep.py | Large file | 693 lines | Consider separating fast-glob logic into utilities |
| src/tunacode/core/recursive/hierarchy.py:42 | Large class (TaskHierarchy) | 23 methods | Apply Single Responsibility Principle, extract related methods |

### Priority 3: High Change Frequency (Maintenance Hotspots)

| File | Changes | Bug Fixes | Risk | Recommendation |
|------|---------|-----------|------|----------------|
| src/tunacode/constants.py | 45 commits | N/A | Version bumps | Normal - version management |
| src/tunacode/core/agents/main.py | 42 commits | 15 fixes | High churn + complexity | Refactor and add comprehensive tests |
| src/tunacode/cli/repl.py | 28 commits | Multiple | UI changes | Add integration tests |

### Priority 4: Function Design Issues

| File:Line | Function | Parameters | Issue | Fix |
|-----------|----------|------------|-------|-----|
| src/tunacode/tools/bash.py:147 | _format_output | 6 params | Too many parameters | Use configuration object |
| src/tunacode/core/recursive/aggregator.py:313 | update_context | 6 params | Too many parameters | Group related params |
| src/tunacode/cli/main.py:25 | main | 6 params | Too many parameters | Use argument parser object |

### Priority 5: Long Functions

| File | Function | Length | Recommendation |
|------|----------|--------|----------------|
| src/tunacode/core/agents/main.py | get_or_create_agent | 84 lines | Split creation logic from caching |
| src/tunacode/tools/grep.py | run_ripgrep_filtered | 79 lines | Extract filtering and processing steps |
| src/tunacode/tools/grep.py | search_file_sync | 68 lines | Separate search from result formatting |

## Common Patterns Observed

### Import Duplication
- StateManager imported in 16 files - consider dependency injection
- UI console imported in 8 files - evaluate if all files need direct UI access
- ToolExecutionError used in 8 files - good error standardization

### Error Handling
- 105 simple try-except blocks - review for proper error specificity
- Consistent error handling patterns suggest good standardization

## Remediation Roadmap

### Phase 1: Critical Complexity (Week 1)
1. Refactor `_process_node` in main.py:
   - Extract node type handlers into separate methods
   - Create NodeProcessor class with strategy pattern
   - Target: CC < 15 per function

2. Refactor `process_request` in main.py:
   - Split into: validate_request, execute_request, format_response
   - Extract tool batching logic
   - Target: CC < 20 per function

### Phase 2: Structural Improvements (Week 2)
1. Break down main.py into modules:
   - agent_factory.py: Agent creation and caching
   - tool_executor.py: Tool execution logic
   - message_processor.py: Message handling
   - Keep main.py as coordination layer only

2. Refactor TaskHierarchy class:
   - Extract traversal methods to TaskTraverser
   - Extract modification methods to TaskModifier
   - Keep core hierarchy logic in base class

### Phase 3: Maintenance & Testing (Week 3)
1. Add comprehensive tests for high-churn files
2. Implement integration tests for REPL
3. Add performance benchmarks for grep operations

### Phase 4: Code Quality (Week 4)
1. Reduce function parameters using configuration objects
2. Split long functions into cohesive units
3. Apply consistent error handling patterns

## Prevention Strategies

1. **Complexity Gates**: Set radon CC threshold of 10 in CI/CD
2. **File Size Limits**: Alert on files > 500 lines
3. **Function Length**: Enforce 50-line function limit
4. **Parameter Count**: Maximum 4 parameters per function
5. **Code Review**: Focus on high-churn files

## Success Metrics

- All functions with CC < 15
- No files > 500 lines
- All functions < 50 lines  
- Maximum 4 parameters per function
- Test coverage > 80% for high-churn files

## Conclusion

The codebase shows good overall structure with consistent patterns. Main areas of concern are concentrated in the agent system (main.py) which handles complex orchestration logic. By breaking down these complex areas and adding appropriate tests, the codebase can achieve better maintainability while preserving its functionality.