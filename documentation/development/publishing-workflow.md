# Publishing Workflow

This document describes the automated publishing workflow for TunaCode CLI to PyPI.

> tech-docs-maintainer (short): Workflow renamed to `publish-release.yml` so GitHub Actions reruns the Ruff lint/test pipeline when releases fire.

## Overview

The project uses GitHub Actions to automatically publish releases to PyPI when a new release tag is created. The workflow is triggered by GitHub releases and handles version consistency, building, testing, and publishing.

## Release Process

### Prerequisites

1. **Version Consistency**: All version files must match before releasing:
   - `pyproject.toml` `[project]` version
   - `pyproject.toml` `[tool.hatch.envs.default.scripts]` version
   - `src/tunacode/constants.py` `APP_VERSION`

2. **PyPI API Token**: A valid PyPI API token must be configured as a GitHub repository secret named `PYPI_API_TOKEN`.

### Creating a Release

1. **Update Version Files**: Ensure all version files are synchronized to the desired version number
2. **Commit Changes**: Commit the version updates to the master branch
3. **Create Tag**: Create and push a version tag:
   ```bash
   git tag v0.0.77.2
   git push origin v0.0.77.2
   ```
4. **Create Release**: Create a GitHub release:
   ```bash
   gh release create v0.0.77.2 --generate-notes
   ```

### Workflow Steps

The publishing workflow (`.github/workflows/publish-release.yml`) performs these steps:

1. **Checkout Code**: Checks out the repository at the release tag
2. **Setup Python**: Configures Python 3.12 (3.13 currently breaks Hatch's filter parsing)
3. **Install Dependencies**: Installs build tools (hatch, twine, uv)
4. **Version Check**: Validates that tag version matches code versions
5. **Build**: Creates distribution packages using hatch
6. **Publish**: Uploads to PyPI using API token authentication

## Version Management

### Version Files

The project maintains version consistency across multiple files:

- `pyproject.toml` lines 8 and 173: Package version and hatch script version
- `src/tunacode/constants.py` line 12: Application constant

### Version Bumping Process

1. Update all version files simultaneously
2. Commit with clear message: `chore: bump version to X.Y.Z`
3. Ensure changes are on master branch
4. Create and push version tag

## Troubleshooting

### Version Mismatch Errors

If the workflow fails with "version mismatch" errors:

1. Check that all version files have the same version number
2. Ensure the release tag matches the version in the files
3. Verify the tag points to the correct commit with the version updates

### PyPI Authentication Issues

If publishing fails with authentication errors:

1. Verify `PYPI_API_TOKEN` secret exists in repository settings
2. Ensure the token has publishing permissions for the package
3. Check that the token hasn't expired

### Workflow Configuration

The workflow is configured in `.github/workflows/publish-release.yml` and:
- Triggers on GitHub release events
- Uses API token authentication (preferred method)
- Validates version consistency before building
- Runs full test suite before publishing

## Best Practices

1. **Always test locally** before creating a release
2. **Verify version consistency** across all files
3. **Use semantic versioning** (MAJOR.MINOR.PATCH)
4. **Include meaningful release notes** when creating releases
5. **Monitor workflow runs** to ensure successful publishing

## Example Release Commands

```bash
# Update version to 0.0.77.2
sed -i 's/version = "0.0.77.1"/version = "0.0.77.2"/g' pyproject.toml
sed -i 's/APP_VERSION = "0.0.77.1"/APP_VERSION = "0.0.77.2"/' src/tunacode/constants.py

# Commit and tag
git add pyproject.toml src/tunacode/constants.py
git commit -m "chore: bump version to 0.0.77.2"
git tag v0.0.77.2
git push origin master
git push origin v0.0.77.2

# Create release
gh release create v0.0.77.2 --generate-notes
```

## Related Documentation

- [Hatch Build System](../development/hatch-build-system.md) - Build system details
- [Codebase Hygiene](../development/codebase-hygiene.md) - Development practices
- [Configuration](../configuration/) - Configuration file documentation
