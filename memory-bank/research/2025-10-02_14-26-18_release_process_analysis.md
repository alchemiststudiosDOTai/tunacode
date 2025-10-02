# Research – Release Process Analysis

**Date:** 2025-10-02
**Owner:** context-engineer
**Phase:** Research

## Goal
Summarize all existing knowledge about the current release process to identify pain points and opportunities for automation improvements.

- Additional Search:
  - `grep -ri "release" .claude/`

## Findings

### Current Release Architecture

The project has a **semi-automated release process** with both automated and manual components:

**Automated Components:**
- GitHub Actions workflow for PyPI publishing (`.github/workflows/publish-release-v2.yml:6-73`)
- Version consistency validation in CI
- Automated build and package creation
- PyPI publishing via API token

**Manual Components:**
- Version synchronization across 3 files
- Git tag creation and pushing
- GitHub release creation
- Changelog updates

### Relevant Files & Architecture

**Core Release Files:**
- `.github/workflows/publish-release-v2.yml` → GitHub Actions workflow that triggers on release events, validates versions, builds, and publishes to PyPI
- `pyproject.toml:8,173` → Primary version locations (project version and hatch script version)
- `src/tunacode/constants.py:12` → APP_VERSION constant that must stay synchronized
- `documentation/development/publishing-workflow.md` → Comprehensive release guide with step-by-step instructions

**Build System Configuration:**
- `pyproject.toml:156-273` → Hatch build system with release automation scripts
- `pyproject.toml:176-181` → Release workflow: test → lint → build → manual publish prompt

**Documentation & Guides:**
- `.claude/development/version-management.md` → Concise version management overview
- `documentation/development/hatch-build-system.md` → Complete Hatch build system guide

## Current Release Workflow

### Prerequisites (Manual)
1. **Version Consistency** - Three files must match:
   - `pyproject.toml:8` (project version)
   - `pyproject.toml:173` (hatch script version)
   - `src/tunacode/constants.py:12` (APP_VERSION)

2. **PyPI API Token** - Must be configured as `PYPI_API_TOKEN` GitHub secret

### Manual Release Steps
```bash
# 1. Update version files (manual)
sed -i 's/version = "0.0.77"/version = "0.0.78"/g' pyproject.toml
sed -i 's/APP_VERSION = "0.0.77"/APP_VERSION = "0.0.78"/' src/tunacode/constants.py

# 2. Commit changes
git add pyproject.toml src/tunacode/constants.py
git commit -m "chore: bump version to 0.0.78"

# 3. Create and push tag
git tag v0.0.78
git push origin master
git push origin v0.0.78

# 4. Create GitHub release
gh release create v0.0.78 --generate-notes
```

### Automated Steps (GitHub Actions)
1. **Version Validation** - Validates tag matches code versions (`.github/workflows/publish-release-v2.yml:43-63`)
2. **Build** - Creates distribution packages with `hatch build` (line 66)
3. **Publish** - Uploads to PyPI via API token (lines 69-73)

## Key Pain Points Identified

### 1. **Manual Version Synchronization**
- **Problem**: Three separate files must be updated manually
- **Risk**: Human error can cause version mismatches, breaking the release
- **Files**: `pyproject.toml:8`, `pyproject.toml:173`, `src/tunacode/constants.py:12`

### 2. **Manual Git Operations**
- **Problem**: Requires manual tag creation, pushing, and GitHub release creation
- **Steps**: `git tag`, `git push`, `gh release create`
- **Risk**: Commands must be executed in correct order

### 3. **No Automated Changelog**
- **Problem**: Changelog must be updated manually
- **Risk**: Missing changelog entries or inconsistent formatting

### 4. **Local Testing Requirement**
- **Problem**: No automated pre-release testing in CI
- **Risk**: Issues discovered only after release creation

## Existing Strengths

### 1. **Robust Version Validation**
- GitHub Actions automatically validates version consistency
- Fails fast if versions don't match
- Clear error messages for troubleshooting

### 2. **Comprehensive Documentation**
- Well-documented release procedures
- Troubleshooting guides for common issues
- Example commands provided

### 3. **Modern Tooling**
- Uses Hatch build system and UV installer
- Proper Python packaging standards
- Semantic versioning

## Automation Opportunities

### High Impact
1. **Version Bumping Script** - Single command to update all version files
2. **Release Command** - Combine version bump, commit, tag, and release creation
3. **Automated Changelog** - Generate from git commits

### Medium Impact
1. **Pre-release Testing** - Automated testing before release creation
2. **Release Validation** - More comprehensive pre-flight checks

## Knowledge Gaps

- Current developer workflow and preferred release frequency
- Whether there are any existing release scripts not found in the repository
- Integration requirements with other tools or services
- Developer preferences for automation vs. manual control

## References

- **GitHub Actions Workflow**: `.github/workflows/publish-release-v2.yml:6-73`
- **Publishing Guide**: `documentation/development/publishing-workflow.md:1-120`
- **Build Configuration**: `pyproject.toml:156-273`
- **Version Management**: `.claude/development/version-management.md`
- **Hatch Documentation**: `documentation/development/hatch-build-system.md`

## Git Context

- **Current Branch**: master
- **Recent Commits**:
  - 0e5c473 Fix UI lazy Rich typing and dead-imports hook
  - 950b8a6 lazy-ui-imports
  - 2fce96d rollback point: before lazy loading Rich UI components
- **Current Version**: 0.0.77.1
