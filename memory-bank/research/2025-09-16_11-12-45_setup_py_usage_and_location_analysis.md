---
date: 2025-09-16
time: 11:12:45
owner: context-engineer
phase: research
topic: setup.py Usage and Location Analysis
last_updated: 2025-09-16
last_updated_by: context-engineer
last_updated_note: Initial research on setup.py usage and location analysis
tags: [setup.py, pyproject.toml, build-system, packaging, migration]
---

# Research – setup.py Usage and Location Analysis
**Date:** 2025-09-16
**Owner:** context-engineer
**Phase:** Research

## Goal
Investigate where setup.py is used and for what purpose, and evaluate if its current location is appropriate.

## Additional Search
- `grep -ri "setup\.py" .claude/` → Found references in development notes and research documents
- `grep -ri "pyproject\.toml" .claude/` → Found migration documentation and configuration details

## Findings

### setup.py Files Found
1. **Root setup.py** (`/home/fabian/tunacode/setup.py`) - Minimal setuptools configuration
2. **Application setup.py** (`/home/fabian/tunacode/src/tunacode/setup.py`) - Runtime setup API (not packaging)

### Current Usage Patterns

#### Root setup.py (Packaging Configuration)
**Purpose**: Minimal setuptools compatibility shim
**Content**:
```python
from setuptools import find_namespace_packages, setup

setup(
    package_dir={"": "src"},
    packages=find_namespace_packages(where="src"),
    include_package_data=True,
    package_data={
        "tunacode": ["prompts/*.txt", "prompts/*.md"],
    },
)
```

**Why it's still needed**:
1. **Package Data Inclusion**: Handles including prompt files (`prompts/*.txt`, `prompts/*.md`)
2. **Backward Compatibility**: Some tools may still expect setup.py
3. **Namespace Package Discovery**: Uses `find_namespace_packages()` for package discovery

#### Application setup.py (Runtime Setup)
**Purpose**: Provides application initialization API
**Location**: `/home/fabian/tunacode/src/tunacode/setup.py`
**Key Functions**:
- `setup()` - Main application initialization
- `setup_agent()` - Agent-specific setup
- Imports from `tunacode.core.setup` modules

### Modern Build System: pyproject.toml
The project has fully migrated to **pyproject.toml** as the primary build configuration:

**Build System Configuration**:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Key Features**:
- Complete project metadata and dependencies
- Hatch environment management
- Build scripts and tool configurations
- Package discovery: `packages = ["src/tunacode"]`

### Migration History
- **August 2025**: Complete Hatch migration (commit a2aa197)
- Successfully published v0.0.62 using Hatch + UV
- All tests passing (298 tests)
- Replaced Makefile with Hatch scripts

### Location Analysis

#### Root setup.py Location
**Should it be moved?** NO
- Standard location expected by setuptools and pip
- Moving would break Python packaging conventions
- Serves as compatibility shim for build tools

#### Application setup.py Location
**Current location**: `src/tunacode/setup.py`
**Appropriateness**: CORRECT
- Part of the application codebase
- Provides runtime setup functionality
- Properly namespaced under the package

## Key Patterns / Solutions Found

### 1. Dual Configuration Pattern
The project uses a hybrid approach:
- `pyproject.toml` for modern build configuration (PEP 517/518)
- `setup.py` for setuptools-specific needs (package data, namespace packages)

### 2. Clear Separation of Concerns
- **Build-time packaging**: Root setup.py + pyproject.toml
- **Runtime setup**: src/tunacode/setup.py + core/setup/ modules

### 3. Successful Migration
The migration to pyproject.toml is complete and functional:
- All builds use `hatch build`
- Package distribution works correctly
- No active issues with current configuration

## Knowledge Gaps

### Missing Context
1. **No explicit roadmap** for removing setup.py entirely
2. **Undocumented requirements** for maintaining setup.py
3. **No analysis** of whether package data can be moved to pyproject.toml
4. **Unknown dependencies** on setup.py by external tools or systems

### Technical Questions
1. Can `package_data` configuration be moved to pyproject.toml?
2. Are there specific tools in the ecosystem that require setup.py?
3. What would break if setup.py were removed?

## References

### Files
- `/home/fabian/tunacode/setup.py` - Root setuptools configuration
- `/home/fabian/tunacode/pyproject.toml` - Primary build configuration
- `/home/fabian/tunacode/src/tunacode/setup.py` - Application setup API
- `/home/fabian/tunacode/src/tunacode/core/setup/` - Setup implementation modules

### Documentation
- `.claude/development/model-updates-2025.md` - Migration context
- `.github/workflows/publish-release.yml` - CI/CD build pipeline
- `memory-bank/research/` - Historical research documents

### Git Commits
- `a2aa197` - "feat: complete Hatch migration - remove Makefile and update all references"
- `3c0b18a` - "refactor: migrate to uv for dependency management"
- `5f954f8` - "feat: complete UV+Hatch integration with dependency fixes"
