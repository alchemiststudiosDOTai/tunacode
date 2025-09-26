---
title: "Research – AGENTS.md to AGENTS.md Migration"
date: "2025-09-19"
time: "11:25:00"
owner: "context-engineer:research"
phase: "Research"
last_updated: "2025-09-19"
last_updated_by: "context-engineer:research"
last_updated_note: "Initial comprehensive research on AGENTS.md to AGENTS.md migration"
tags: ["migration", "refactoring", "documentation", "configuration", "testing"]
git_commit: "b3e228c3542923743cde34b892f4e74b8f515069"
---

# Research – AGENTS.md to AGENTS.md Migration
**Date:** 2025-09-19
**Owner:** context-engineer:research
**Phase:** Research

## Goal
Summarize all existing knowledge about changing references from "AGENTS.md" to "AGENTS.md" throughout the codebase before implementing the migration.

## Research Scope
- Comprehensive search for all "AGENTS.md" references
- Analysis of AGENTS.md current state and contents
- Impact assessment on tests, configuration, and documentation
- Identification of required changes and potential risks

## Additional Search
- `grep -ri "AGENTS.md" .claude/` - No references found in .claude directory
- `grep -ri "AGENTS.md" .claude/` - No references found in .claude directory

## Findings

### Current State of AGENTS.md
**File Location**: `/root/tunacode/AGENTS.md` - [View on GitHub](https://github.com/alchemiststudiosDOTai/tunacode/blob/b3e228c3542923743cde34b892f4e74b8f515069/AGENTS.md)

**File Status**: ✅ Exists (119 lines)

**Contents Summary**: AGENTS.md contains comprehensive documentation about:
- Claude-specific repository optimization requirements
- Directory structure specifications (claude/ with metadata/, semantic_index/, etc.)
- Workflow instructions and coding standards
- Available subagents list (bug-context-analyzer, code-synthesis-analyzer, documentation-synthesis-qa)
- Testing requirements (TDD, "hatch run test")

**Key Finding**: AGENTS.md serves as the primary context file for AI agents working with this repository.

### AGENTS.md References - Complete Inventory

#### Core Python Files (4 files)
- `src/tunacode/constants.py:17` → `GUIDE_FILE_NAME = "AGENTS.md"` - **PRIMARY CONSTANT**
- `src/tunacode/configuration/defaults.py:23` → Uses `GUIDE_FILE_NAME` constant
- `src/tunacode/core/agents/agent_components/agent_config.py:91-168` → Context loading logic with hardcoded references
- `src/tunacode/context.py:53-71` → Directory tree walking for AGENTS.md files

#### Test Files (7 files, 30+ references)
- `tests/characterization/context/test_context_acceptance.py:1,21-24,37-40,50,62-66,98` → Acceptance tests for context injection
- `tests/characterization/context/test_context_integration.py:1,20-24,65-69,99-101` → Integration tests for agent creation
- `tests/characterization/context/test_context_loading.py:1,20-23,30-32,54-57,77-78,108-113,130-134` → Unit tests for file loading behavior
- `tests/characterization/context/test_tunacode_logging.py:1,12-17,55,62-64,87-88` → Logging message tests
- `tests/characterization/commands/test_init_command.py:2,18-19,40-41,60-61,92,110,114` → `/init` command tests
- `tests/characterization/agent/test_agent_creation.py:45,101,126` → Agent creation with missing AGENTS.md
- `tests/characterization/test_characterization_main.py:281` → Main characterization test

#### Configuration Files (4 files)
- `scripts/install_linux.sh:498` → Default config example
- `MANIFEST.in:10` → Package inclusion
- `documentation/configuration/tunacode.json.example:19` → Config example
- `documentation/configuration/config-file-example.md:20,44` → Documentation examples

#### Documentation Files (4 files)
- `documentation/user/commands.md:35` → User guide
- `documentation/user/getting-started.md:222` → Getting started guide
- `documentation/development/performance-optimizations.md:37` → Developer docs
- `tests/characterization/context/README.md:3,14-22` → Test documentation

#### Memory Bank Files (2 files)
- `memory-bank/research/2025-09-19_11-09-23_system_md_discoverability_analysis.md:36,40` → Recent research
- `memory-bank/research/2025-09-15_12-19-00_configuration_system_and_dashboard.md:49` → Previous research

## Key Patterns / Solutions Found

### Primary Change Point
**`src/tunacode/constants.py:17`** - The `GUIDE_FILE_NAME` constant is the single source of truth used throughout the codebase.

### Hardcoded References Pattern
Most references are hardcoded strings that need direct replacement:
- File paths: `"AGENTS.md"` → `"AGENTS.md"`
- Logging messages: `"📄 AGENTS.md located"` → `"📄 AGENTS.md located"`
- Test assertions: Project context strings and file existence checks

### Test Impact Categories
1. **Agent Creation Tests** - Mock file existence, system prompt validation
2. **Context Injection Tests** - File content loading and parsing
3. **Logging Tests** - Message display and formatting
4. **Command Tests** - `/init` command creates AGENTS.md instead of AGENTS.md
5. **Integration Tests** - End-to-end behavior validation

### Configuration Changes
- Default configuration files need filename updates
- Installation scripts need reference updates
- Package manifest needs inclusion update

## Knowledge Gaps

### Migration Strategy Questions
1. **Should existing AGENTS.md files be renamed to AGENTS.md?**
2. **What about user projects that already have AGENTS.md files?**
3. **Are there any external tools or integrations that expect AGENTS.md?**
4. **Should we maintain backward compatibility?**

### Testing Concerns
1. **Characterization tests** need to be updated first (TDD requirement)
2. **Integration tests** may need significant rework
3. **Acceptance tests** will need new expected values
4. **Performance implications** of filename change

## Change Complexity Assessment

### Low Complexity (2 changes)
- Constants update (`constants.py`)
- Configuration defaults (`defaults.py`)

### Medium Complexity (10-15 changes)
- Agent configuration logic
- Context loading functions
- Installation scripts
- Package manifests

### High Complexity (30+ changes)
- **Test files** - Extensive hardcoded references and assertions
- **Documentation** - User-facing content updates
- **Memory bank** - Historical research references

## Risk Assessment

### High Risk
- **Test breakage** - Many hardcoded assertions will fail
- **User confusion** - Documentation changes may confuse existing users
- **Tool incompatibility** - External integrations may expect AGENTS.md

### Medium Risk
- **Logging changes** - Monitoring and debugging may be affected
- **Configuration changes** - Default behavior modifications
- **Package distribution** - MANIFEST.in changes affect packaging

### Low Risk
- **Constants change** - Single point of failure, easily tested
- **Agent functionality** - Core behavior remains the same

## Recommended Migration Strategy

### Phase 1: Preparation
1. Create comprehensive characterization test for current AGENTS.md behavior
2. Backup existing configuration and documentation
3. Communicate change to stakeholders

### Phase 2: Core Changes
1. Update `GUIDE_FILE_NAME` constant in `constants.py`
2. Update all core Python files to use the new constant
3. Run core functionality tests

### Phase 3: Test Updates
1. Update all test files systematically
2. Ensure all assertions use new filename
3. Update logging message tests
4. Validate `/init` command behavior

### Phase 4: Documentation & Configuration
1. Update user documentation
2. Update configuration examples
3. Update installation scripts
4. Update package manifests

### Phase 5: Cleanup
1. Update memory bank references
2. Remove any remaining AGENTS.md references
3. Verify end-to-end functionality

## References

### GitHub Permalinks
- [AGENTS.md](https://github.com/alchemiststudiosDOTai/tunacode/blob/b3e228c3542923743cde34b892f4e74b8f515069/AGENTS.md)
- [constants.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/b3e228c3542923743cde34b892f4e74b8f515069/src/tunacode/constants.py)
- [agent_config.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/b3e228c3542923743cde34b892f4e74b8f515069/src/tunacode/core/agents/agent_components/agent_config.py)

### Key Files for Full Review
- `src/tunacode/constants.py` - Primary constant to change
- `tests/characterization/context/test_context_acceptance.py` - Acceptance test example
- `src/tunacode/core/agents/agent_components/agent_config.py` - Core context loading logic
- `documentation/user/commands.md` - User-facing documentation
- `scripts/install_linux.sh` - Installation configuration

### Test Files Requiring Updates (7 files)
All files in `tests/characterization/` directory that reference AGENTS.md need systematic updates to assertions, file creation, and logging message validation.

### Configuration Files (4 files)
Default configurations, examples, and installation scripts need filename reference updates.

## Next Steps

1. **Create baseline characterization test** before any changes
2. **Update constants.py** as the primary change point
3. **Systematically update test files** using find-and-replace
4. **Validate all functionality** works with AGENTS.md
5. **Update documentation** to reflect the new default filename
6. **Run full test suite** to ensure no regressions
