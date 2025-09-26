---
title: "AGENTS.md to AGENTS.md Migration – Plan"
phase: Plan
date: "2025-09-19_11-30-00"
owner: "context-engineer:plan"
parent_research: "memory-bank/research/2025-09-19_11-25-00_tunacode_md_to_agents_md_migration.md"
git_commit_at_plan: "1a81ce0"
tags: [plan, migration, refactoring]
---

## Goal
Execute a comprehensive migration from "AGENTS.md" to "AGENTS.md" as the primary configuration file throughout the codebase, ensuring all references, tests, documentation, and configurations are updated systematically with zero regressions. This is a singular focused migration that will standardize the agent configuration filename across the entire ecosystem.

## Scope & Assumptions

### In Scope
- All hardcoded "AGENTS.md" references in Python source code
- All test files referencing AGENTS.md (30+ references across 7 files)
- Configuration files, installation scripts, and package manifests
- User-facing documentation and examples
- Memory bank references and research documentation
- Logging messages and system prompts

### Out of Scope
- External tool integrations beyond this repository
- User projects that may have existing AGENTS.md files
- Backward compatibility with AGENTS.md (breaking change intended)

### Assumptions
- AGENTS.md already exists and contains comprehensive agent configuration
- This is an intentional breaking change to standardize on AGENTS.md
- All functionality should remain identical except for the filename change
- Characterization tests must be updated first to establish new baseline

## Deliverables (DoD)

1. **Updated Codebase** - All AGENTS.md references replaced with AGENTS.md
2. **Comprehensive Test Suite** - All tests passing with new filename
3. **Updated Documentation** - User guides and examples reflect AGENTS.md
4. **Configuration Updates** - All config files and installation scripts updated
5. **Memory Bank Consistency** - Research docs updated to reflect change
6. **Validation Report** - End-to-end functionality verification

## Readiness (DoR)

### Preconditions
- ✅ Current git state captured (commit 1a81ce0)
- ✅ Research document comprehensively analyzed
- ✅ All reference locations identified and categorized
- ✅ Risk assessment completed
- ✅ Migration strategy defined

### Data & Access
- ✅ Full codebase access available
- ✅ Test execution environment ready ("hatch run test")
- ✅ Git repository with proper permissions
- ✅ Documentation write access

## Milestones

### M1: Preparation & Baseline
- Create rollback commit point
- Establish baseline characterization test for current behavior
- Document exact current behavior with AGENTS.md

### M2: Core Infrastructure Changes
- Update GUIDE_FILE_NAME constant in constants.py
- Update core Python files to use new constant
- Validate core functionality works with AGENTS.md

### M3: Comprehensive Test Migration
- Systematically update all 7 test files
- Update hardcoded assertions and file references
- Validate logging message tests
- Test /init command behavior

### M4: Documentation & Configuration Updates
- Update user documentation and guides
- Update configuration examples and installation scripts
- Update package manifests
- Update memory bank references

### M5: Validation & Hardening
- Full end-to-end functionality testing
- Performance validation
- Documentation consistency check
- Final verification and cleanup

## Work Breakdown (Tasks)

### M1: Preparation & Baseline

**M1.1** - Create rollback commit point
- Owner: context-engineer
- Dependencies: None
- Acceptance Tests:
  - Git commit created with clear rollback message
  - All current changes committed safely

**M1.2** - Create baseline characterization test
- Owner: context-engineer
- Dependencies: M1.1
- Acceptance Tests:
  - Test captures exact current AGENTS.md behavior
  - Test validates file loading, context injection, logging
  - Test serves as regression prevention baseline

**M1.3** - Document current behavior
- Owner: context-engineer
- Dependencies: M1.2
- Acceptance Tests:
  - Comprehensive behavior documentation created
  - All edge cases documented
  - Test scenarios enumerated

### M2: Core Infrastructure Changes

**M2.1** - Update primary constant
- Owner: context-engineer
- Dependencies: M1.1
- Acceptance Tests:
  - GUIDE_FILE_NAME changed from "AGENTS.md" to "AGENTS.md"
  - No other constants need modification
  - Tests validate constant change

**M2.2** - Update core Python files
- Owner: context-engineer
- Dependencies: M2.1
- Acceptance Tests:
  - All core files use new constant
  - Context loading works with AGENTS.md
  - Agent configuration logic updated
  - No hardcoded references remain in core files

**M2.3** - Validate core functionality
- Owner: context-engineer
- Dependencies: M2.2
- Acceptance Tests:
  - Basic agent creation works
  - Context injection functions correctly
  - No regressions in core behavior

### M3: Comprehensive Test Migration

**M3.1** - Update context acceptance tests
- Owner: context-engineer
- Dependencies: M2.3
- Acceptance Tests:
  - All AGENTS.md references replaced in test_context_acceptance.py
  - Assertions validate AGENTS.md behavior
  - File creation tests use correct filename

**M3.2** - Update context integration tests
- Owner: context-engineer
- Dependencies: M3.1
- Acceptance Tests:
  - test_context_integration.py updated
  - Integration tests pass with AGENTS.md
  - Agent creation tests work correctly

**M3.3** - Update context loading tests
- Owner: context-engineer
- Dependencies: M3.2
- Acceptance Tests:
  - test_context_loading.py assertions updated
  - File loading behavior tests pass
  - Edge case handling preserved

**M3.4** - Update logging tests
- Owner: context-engineer
- Dependencies: M3.3
- Acceptance Tests:
  - test_tunacode_logging.py logging messages updated
  - All message format tests pass
  - Display behavior unchanged

**M3.5** - Update command tests
- Owner: context-engineer
- Dependencies: M3.4
- Acceptance Tests:
  - test_init_command.py creates AGENTS.md
  - Command behavior tests pass
  - File existence checks updated

**M3.6** - Update agent creation tests
- Owner: context-engineer
- Dependencies: M3.5
- Acceptance Tests:
  - test_agent_creation.py missing file tests updated
  - Agent creation works with AGENTS.md
  - Error handling preserved

**M3.7** - Update characterization main tests
- Owner: context-engineer
- Dependencies: M3.6
- Acceptance Tests:
  - test_characterization_main.py references updated
  - Main test suite passes
  - Integration preserved

### M4: Documentation & Configuration Updates

**M4.1** - Update user documentation
- Owner: context-engineer
- Dependencies: M3.7
- Acceptance Tests:
  - documentation/user/commands.md updated
  - documentation/user/getting-started.md updated
  - User guides consistently reference AGENTS.md

**M4.2** - Update developer documentation
- Owner: context-engineer
- Dependencies: M4.1
- Acceptance Tests:
  - documentation/development/performance-optimizations.md updated
  - Test README.md updated
  - Developer docs consistent

**M4.3** - Update configuration files
- Owner: context-engineer
- Dependencies: M4.2
- Acceptance Tests:
  - scripts/install_linux.sh updated
  - MANIFEST.in updated
  - Configuration examples updated

**M4.4** - Update memory bank references
- Owner: context-engineer
- Dependencies: M4.3
- Acceptance Tests:
  - Recent research documents updated
  - References to AGENTS.md in memory bank updated
  - Historical consistency maintained

### M5: Validation & Hardening

**M5.1** - Full test suite execution
- Owner: context-engineer
- Dependencies: M4.4
- Acceptance Tests:
  - All characterization tests pass
  - All unit tests pass
  - All integration tests pass

**M5.2** - End-to-end functionality testing
- Owner: context-engineer
- Dependencies: M5.1
- Acceptance Tests:
  - Agent creation works end-to-end
  - Context injection functions correctly
  - /init command creates AGENTS.md

**M5.3** - Documentation consistency check
- Owner: context-engineer
- Dependencies: M5.2
- Acceptance Tests:
  - All docs consistently reference AGENTS.md
  - No AGENTS.md references remain
  - Examples work correctly

## Risks & Mitigations

### High Risk
**Test Breakage** - High - Likely - Extensive hardcoded assertions
- Mitigation: Update tests systematically, use find-and-replace carefully
- Trigger: Any test failure after core changes

**User Confusion** - Medium - Medium - Documentation changes may confuse existing users
- Mitigation: Clear migration notes in commit messages
- Trigger: User feedback or confusion reports

### Medium Risk
**Configuration Regression** - Medium - Low - Default behavior changes
- Mitigation: Test all configuration scenarios thoroughly
- Trigger: Configuration loading failures

**Package Distribution** - Low - Low - MANIFEST.in changes affect packaging
- Mitigation: Verify package builds correctly
- Trigger: Build or installation failures

### Low Risk
**Constants Change** - Low - Unlikely - Single point of failure
- Mitigation: Test immediately after change
- Trigger: Core functionality failures

## Test Strategy

### Unit Tests
- Run: `hatch run test` for full test suite
- Coverage: 100% of changed files
- Mutation: Key functions should be mutation-tested

### Integration Tests
- Context injection with AGENTS.md
- Agent creation and configuration loading
- /init command end-to-end behavior

### E2E Tests
- Complete agent workflow with AGENTS.md
- File discovery and loading
- Logging and monitoring behavior

### Performance Tests
- File loading performance (should be identical)
- Memory usage (should be identical)
- Agent startup time (should be identical)

## Security & Compliance

### Secret Handling
- No secrets involved in filename change
- Configuration file parsing remains secure

### Authentication
- No auth changes required
- File access permissions remain the same

### Threat Model
- File path manipulation risks unchanged
- No new attack surfaces introduced

## Observability

### Metrics
- Agent creation success rate (should remain 100%)
- Configuration loading time (should remain consistent)
- Error rates (should remain unchanged)

### Logs
- Logging messages updated to reference AGENTS.md
- Error messages consistent with new filename
- Debug information preserved

### Traces
- Request tracing unchanged
- Performance characteristics identical
- Error handling flows preserved

## Rollout Plan

### Environment Order
1. Development environment (this execution)
2. CI/CD pipeline validation
3. Production deployment (via standard release process)

### Migration Steps
1. Create rollback point
2. Update core infrastructure
3. Update tests systematically
4. Update documentation and configuration
5. Validate end-to-end functionality

### Feature Flags
- No feature flags needed - this is a breaking change
- Change is atomic and immediately effective

### Rollback Triggers
- Any critical test failure
- Core functionality regression
- Performance degradation > 5%

## Validation Gates

### Gate A (Design Sign-off)
- ✅ Research document thoroughly analyzed
- ✅ All reference locations identified
- ✅ Risk assessment completed
- ✅ Migration strategy approved

### Gate B (Test Plan Sign-off)
- ✅ Baseline characterization test created
- ✅ All test files identified for updates
- ✅ Acceptance criteria defined for each task
- ✅ Test strategy documented

### Gate C (Pre-merge Quality Bar)
- All tests must pass (100% success rate)
- No performance regressions (> 5% change)
- Documentation consistently updated
- Code follows project standards (ruff check passes)

### Gate D (Pre-deploy Checks)
- Package builds successfully
- Installation scripts work correctly
- All documentation examples work
- No breaking changes to public APIs

## Success Metrics

### Quality Metrics
- 100% test pass rate
- Zero critical bugs post-migration
- No performance regressions
- Complete documentation consistency

### Adoption Metrics
- All functionality works with AGENTS.md
- No user-reported issues with filename change
- Smooth transition for existing users

### Technical Metrics
- All AGENTS.md references eliminated
- Code coverage maintained or improved
- Build and packaging success
- CI/CD pipeline stability

## References

### Research Document
- memory-bank/research/2025-09-19_11-25-00_tunacode_md_to_agents_md_migration.md

### Key Files
- src/tunacode/constants.py - Primary constant to change
- tests/characterization/context/ - Test files requiring updates
- documentation/user/ - User documentation to update
- scripts/install_linux.sh - Installation configuration

### GitHub Permalinks
- [AGENTS.md](https://github.com/alchemiststudiosDOTai/tunacode/blob/b3e228c3542923743cde34b892f4e74b8f515069/AGENTS.md)
- [constants.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/b3e228c3542923743cde34b892f4e74b8f515069/src/tunacode/constants.py)

## Agents

### Available Subagents
- **context-synthesis** - For analyzing complex code relationships
- **codebase-analyzer** - For detailed codebase analysis

### Subagent Deployment Strategy
- Deploy context-synthesis for complex code relationship analysis
- Deploy codebase-analyzer for detailed codebase analysis if needed

## Final Gate

**Plan Path**: `memory-bank/plan/2025-09-19_11-30-00_tunacode_md_to_agents_md_migration.md`

**Milestones**: 5 major milestones with 19 total tasks

**Validation Gates**: 4 quality gates to ensure success

**Next Command**: `/execute "memory-bank/plan/2025-09-19_11-30-00_tunacode_md_to_agents_md_migration.md"`
