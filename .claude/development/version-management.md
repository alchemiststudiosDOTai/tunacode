# Version Management & Release Process

## Overview
This system ensures consistent, automated releases with proper version control and quality checks.

## Version Files

**Files that MUST match:**
- `pyproject.toml` - Build system version
- `src/tunacode/constants.py` - Runtime version

## Release Components

### 1. Git Tags
- Format: `v0.0.77`
- Technical snapshots of code at specific moments
- Serve as official release identifiers

### 2. GitHub Releases
- User-facing pages with download links and notes
- Trigger the automated publishing workflow
- Work with git tags but serve different purposes

### 3. GitHub Actions Workflow
**File:** `.github/workflows/publish-release.yml`

> tech-docs-maintainer (short): File renamed to force GitHub Actions to pick up Ruff-based release steps.

**Triggers:**
- Automatic: When creating a GitHub release
- Manual: "Run workflow" in Actions tab

**Process:**
1. Version validation - Ensures git tag matches both version files
2. Package building - Creates installable Python package
3. PyPI publishing - Pushes to Python Package Index

## Release Process Flow

1. **Update versions** in both `pyproject.toml` and `src/tunacode/constants.py`
2. **Commit changes** to git
3. **Create git tag** (e.g., `git tag v0.0.77`)
4. **Push tag** to GitHub (`git push origin v0.0.77`)
5. **Create GitHub release** (this triggers the workflow)
6. **Automated publishing** to PyPI

## Why This System Matters

- **User Access**: PyPI users can `pip install tunacode` to get the latest version
- **Version Consistency**: Prevents bugs where different code components think they're different versions
- **Quality Assurance**: Every release passes the same test suite
- **Automation**: Eliminates manual packaging errors and ensures consistent process

## Key Commands

```bash
# After updating version files
git add pyproject.toml src/tunacode/constants.py
git commit -m "bump version to v0.0.77"

# Create and push tag
git tag v0.0.77
git push origin v0.0.77

# Then create GitHub release through web interface
```

## Important Notes

- Never skip version validation - it prevents deployment of inconsistent versions
- Always create git tag before GitHub release
- Run tests locally before tagging to avoid shipping regressions (CI no longer enforces this)
- Version numbers must follow semantic versioning (major.minor.patch.build)
