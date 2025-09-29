---
title: "Git Safety Branch Logic Removal – Plan"
phase: Plan
date: "2025-09-29_11-45-00"
owner: "context-engineer:plan"
parent_research: "memory-bank/research/2025-09-29_11-41-39_git_safety_branch_removal_analysis.md"
git_commit_at_plan: "9eee227"
tags: [plan, git-safety-removal]
---

## Goal
Remove git safety branch functionality completely from TunaCode CLI tool. This feature creates automatic "-tunacode" suffix branches to protect users from unintended file modifications, but is unnecessary for an advanced CLI tool. The goal is clean removal with no impact on core functionality.

**Non-goals:** Remove the /branch command (keep for branch management), remove git context gathering functionality.

## Scope & Assumptions

### In Scope:
- Remove GitSafetySetup class and all related code
- Remove skip_git_safety configuration option
- Update setup orchestration to remove git safety step
- Clean up documentation references
- Remove git safety test coverage
- Ensure setup flow continues working

### Out of Scope:
- Remove /branch command (separate functionality)
- Remove git status context gathering
- Remove git utilities used by other features

### Assumptions:
- Git safety is isolated and doesn't affect core functionality
- Setup orchestration will continue with 3 steps instead of 4
- User configuration will gracefully handle missing skip_git_safety option

## Deliverables (DoD)

1. **Clean Codebase**: All git safety code removed without breaking existing functionality
2. **Updated Setup Flow**: SetupCoordinator runs with Config, Environment, Template steps only
3. **Configuration Cleanup**: skip_git_safety option removed from config schema
4. **Documentation Updated**: All git safety references removed from user docs
5. **Test Coverage**: Git safety tests removed, other tests continue passing
6. **Validation**: CLI setup and commands work correctly after removal

## Readiness (DoR)

- ✅ Research document completed and analyzed
- ✅ Current git state captured (9eee227)
- ✅ No drift detected since research commit
- ✅ Test environment available (hatch run test)
- ✅ Backup/rollback capability via git

## Milestones

### M1: Architecture & Skeleton (Day 1)
- **M1.1**: Verify current setup flow and git safety integration points
- **M1.2**: Create backup of current state
- **M1.3**: Set up test baseline for setup functionality

### M2: Core Feature Removal (Day 1-2)
- **M2.1**: Remove GitSafetySetup class file
- **M2.2**: Update setup orchestration imports and registration
- **M2.3**: Remove git safety test coverage
- **M2.4**: Update configuration schema and utilities

### M3: Cleanup & Validation (Day 2-3)
- **M3.1**: Clean up documentation references
- **M3.2**: Verify setup flow works correctly
- **M3.3**: Test CLI commands still function
- **M3.4**: Run full test suite and fix any issues

### M4: Final Validation (Day 3)
- **M4.1**: Performance and behavior validation
- **M4.2**: Documentation final review
- **M4.3**: Commit final changes

## Work Breakdown (Tasks)

### M1.1: Verify Current Setup Flow
- **Task ID**: M1.1
- **Summary**: Analyze current setup orchestration and git safety integration
- **Owner**: context-engineer
- **Estimate**: 30 min
- **Dependencies**: None
- **Target Milestone**: M1
- **Acceptance Tests**:
  - SetupCoordinator imports verified
  - Git safety integration points documented
  - Current flow behavior understood
- **Files/Interfaces**: `src/tunacode/setup.py`, `src/tunacode/core/setup/__init__.py`

### M1.2: Create Backup
- **Task ID**: M1.2
- **Summary**: Create git backup before starting removal
- **Owner**: context-engineer
- **Estimate**: 5 min
- **Dependencies**: M1.1
- **Target Milestone**: M1
- **Acceptance Tests**:
  - Git commit created with "Backup before git safety removal"
  - Commit contains all current state
- **Files/Interfaces**: Git repository

### M1.3: Setup Test Baseline
- **Task ID**: M1.3
- **Summary**: Create test to verify setup functionality before changes
- **Owner**: context-engineer
- **Estimate**: 45 min
- **Dependencies**: M1.2
- **Target Milestone**: M1
- **Acceptance Tests**:
  - Test passes before removal
  - Test covers setup coordinator flow
  - Test validates all setup steps execute
- **Files/Interfaces**: `tests/characterization/test_setup_flow.py`

### M2.1: Remove GitSafetySetup Class
- **Task ID**: M2.1
- **Summary**: Delete git_safety_setup.py file completely
- **Owner**: context-engineer
- **Estimate**: 5 min
- **Dependencies**: M1.3
- **Target Milestone**: M2
- **Acceptance Tests**:
  - File successfully deleted
  - No import errors in related modules
- **Files/Interfaces**: `src/tunacode/core/setup/git_safety_setup.py`

### M2.2: Update Setup Orchestration
- **Task ID**: M2.2
- **Summary**: Remove GitSafetySetup from setup flow and imports
- **Owner**: context-engineer
- **Estimate**: 30 min
- **Dependencies**: M2.1
- **Target Milestone**: M2
- **Acceptance Tests**:
  - GitSafetySetup removed from __init__.py exports
  - GitSafetySetup removed from setup.py registration
  - SetupCoordinator initializes with 3 steps only
- **Files/Interfaces**: `src/tunacode/core/setup/__init__.py`, `src/tunacode/setup.py`

### M2.3: Remove Git Safety Tests
- **Task ID**: M2.3
- **Summary**: Delete git safety test files and update related tests
- **Owner**: context-engineer
- **Estimate**: 20 min
- **Dependencies**: M2.2
- **Target Milestone**: M2
- **Acceptance Tests**:
  - test_git_commands.py deleted
  - Characterization tests updated to remove git safety references
  - Test suite runs without git safety tests
- **Files/Interfaces**: `tests/characterization/utils/test_git_commands.py`, `tests/characterization/test_characterization_commands.py`

### M2.4: Update Configuration Schema
- **Task ID**: M2.4
- **Summary**: Remove skip_git_safety from configuration system
- **Owner**: context-engineer
- **Estimate**: 30 min
- **Dependencies**: M2.3
- **Target Milestone**: M2
- **Acceptance Tests**:
  - skip_git_safety removed from key_descriptions.py
  - Configuration validation works without git safety option
  - User config migration handled gracefully
- **Files/Interfaces**: `src/tunacode/configuration/key_descriptions.py`, `src/tunacode/utils/user_configuration.py`

### M3.1: Clean Documentation
- **Task ID**: M3.1
- **Summary**: Remove git safety references from user documentation
- **Owner**: context-engineer
- **Estimate**: 30 min
- **Dependencies**: M2.4
- **Target Milestone**: M3
- **Acceptance Tests**:
  - Getting started guide updated
  - Configuration examples updated
  - No broken documentation links
- **Files/Interfaces**: `documentation/user/getting-started.md`, `documentation/configuration/config-file-example.md`

### M3.2: Verify Setup Flow
- **Task ID**: M3.2
- **Summary**: Test setup coordinator works with 3 steps
- **Owner**: context-engineer
- **Estimate**: 30 min
- **Dependencies**: M3.1
- **Target Milestone**: M3
- **Acceptance Tests**:
  - Setup coordinator initializes correctly
  - All 3 setup steps execute successfully
  - No errors in setup flow
- **Files/Interfaces**: `src/tunacode/setup.py`, baseline test from M1.3

### M3.3: Test CLI Commands
- **Task ID**: M3.3
- **Summary**: Verify CLI commands still work after removal
- **Owner**: context-engineer
- **Estimate**: 45 min
- **Dependencies**: M3.2
- **Target Milestone**: M3
- **Acceptance Tests**:
  - Main CLI entry point works
  - Core commands execute without errors
  - /branch command still functions (if kept)
- **Files/Interfaces**: `src/tunacode/cli/main.py`, command implementations

### M3.4: Run Full Test Suite
- **Task ID**: M3.4
- **Summary**: Execute complete test suite and fix any issues
- **Owner**: context-engineer
- **Estimate**: 60 min
- **Dependencies**: M3.3
- **Target Milestone**: M3
- **Acceptance Tests**:
  - All tests pass (except removed git safety tests)
  - No regressions in existing functionality
  - Code quality checks pass (ruff)
- **Files/Interfaces**: Test suite, `hatch run test`

### M4.1: Performance Validation
- **Task ID**: M4.1
- **Summary**: Verify performance and behavior after removal
- **Owner**: context-engineer
- **Estimate**: 30 min
- **Dependencies**: M3.4
- **Target Milestone**: M4
- **Acceptance Tests**:
  - CLI startup time acceptable
  - Memory usage normal
  - No unexpected side effects
- **Files/Interfaces**: Performance benchmarks, CLI behavior

### M4.2: Documentation Final Review
- **Task ID**: M4.2
- **Summary**: Final review of all documentation updates
- **Owner**: context-engineer
- **Estimate**: 20 min
- **Dependencies**: M4.1
- **Target Milestone**: M4
- **Acceptance Tests**:
  - All documentation accurate and complete
  - No references to git safety remain
  - User guide reflects current behavior
- **Files/Interfaces**: All documentation files

### M4.3: Final Commit
- **Task ID**: M4.3
- **Summary**: Commit all changes with proper message
- **Owner**: context-engineer
- **Estimate**: 10 min
- **Dependencies**: M4.2
- **Target Milestone**: M4
- **Acceptance Tests**:
  - Clean commit with focused changes
  - Commit message describes removal clearly
  - All tests passing in final state
- **Files/Interfaces**: Git repository

## Risks & Mitigations

### Risk: Setup Flow Breakage
- **Impact**: High - Could prevent CLI from working
- **Likelihood**: Medium - Setup orchestration changes
- **Mitigation**: Create baseline test before changes, verify each step
- **Trigger**: Setup coordinator fails to initialize

### Risk: Configuration Migration Issues
- **Impact**: Medium - Could affect user experience
- **Likelihood**: Low - Configuration system is robust
- **Mitigation**: Test configuration loading without git safety option
- **Trigger**: Configuration validation errors

### Risk: Test Suite Failures
- **Impact**: Medium - Could block deployment
- **Likelihood**: High - Removing code affects dependent tests
- **Mitigation**: Update tests incrementally, run suite frequently
- **Trigger**: Test failures after removal

### Risk: Documentation Inconsistencies
- **Impact**: Low - User confusion
- **Likelihood**: Medium - Multiple documentation files
- **Mitigation**: Comprehensive review of all documentation
- **Trigger**: User reports outdated information

## Test Strategy

- **Single Golden Test**: Create one comprehensive test that validates the entire setup flow works correctly after git safety removal
- **Test Location**: `tests/characterization/test_setup_flow.py`
- **Test Coverage**: Setup coordinator initialization, step execution, CLI functionality
- **Validation**: All setup steps complete successfully, no errors, CLI remains functional

## References

### Research Document Sections:
- Core Git Safety Files Found (lines 12-31)
- Complete File Mapping for Removal (lines 52-74)
- Usage Patterns Found (lines 75-92)
- Next Steps for Removal (lines 100-105)

### Key Files:
- `/root/tunacode/src/tunacode/core/setup/git_safety_setup.py`
- `/root/tunacode/src/tunacode/setup.py`
- `/root/tunacode/src/tunacode/configuration/key_descriptions.py`
- `/root/tunacode/tests/characterization/utils/test_git_commands.py`

### Git Commits:
- Research commit: 85fab76
- Current commit: 9eee227

## Agents

### context-synthesis subagent
- **Purpose**: Analyze code changes and validate removal completeness
- **Trigger**: After M2.2 (setup orchestration changes)
- **Focus**: Verify no references to GitSafetySetup remain

### codebase-analyzer subagent
- **Purpose**: Validate test coverage and identify missed references
- **Trigger**: After M3.4 (test suite execution)
- **Focus**: Search for any remaining git safety references

## Final Gate

**Plan Path**: `memory-bank/plan/2025-09-29_11-45-00_git_safety_branch_removal_plan.md`

**Milestones**: 4 (Architecture, Core Removal, Cleanup, Final Validation)

**Gates**:
- M1 Gate: Baseline test passes and backup created
- M2 Gate: All git safety code removed, setup flow works with 3 steps
- M3 Gate: Full test suite passes, CLI functionality verified
- M4 Gate: Documentation complete, performance validated

**Next Command**: `/execute "memory-bank/plan/2025-09-29_11-45-00_git_safety_branch_removal_plan.md"`
