# Research – Dev Install Script tiny-agent-os PyPI Package Setup

**Date:** 2026-02-09
**Owner:** claude
**Phase:** Research
**last_updated:** 2026-02-09
**last_updated_by:** claude
**git_commit:** 3f8dea1a
**git_branch:** master
**tags:** [installation, tiny-agent-os, dependencies, pyproject]

## Goal

Verify that the development install scripts are properly configured to use the PyPI-packaged version of `tiny-agent-os` v1.1.0 (Rust bindings) instead of any local build configuration.

## Findings

### Core Dependency Configuration
- **File:** `pyproject.toml:31`
- **Status:** ✅ Correctly configured
- **Dependency:** `"tiny-agent-os==1.1.0"`
- **Note:** Lines 89-90 explicitly state no repo-local override is used

```
# NOTE: tinyagent is now provided by the PyPI distribution `tiny-agent-os`.
# We intentionally do not use a repo-local override.
```

### Developer Setup Script
- **File:** `scripts/dev-setup.sh`
- **Command:** `uv sync --extra dev`
- **Status:** ✅ Ready to use PyPI package
- **Verification:** Script validates package import after install

### End-User Installer
- **File:** `scripts/install_linux.sh`
- **Commands:**
  - Line 452: `uv pip install --python "$VENV_DIR/bin/python" tunacode-cli`
  - Line 455: `"$VENV_DIR/bin/pip" install tunacode-cli`
- **Status:** ✅ Will pull `tiny-agent-os` as transitive dependency

### Installed Package Verification
- **Location:** `.venv/lib/python3.13/site-packages/tinyagent/`
- **Rust binary:** `_alchemy.abi3.so` (9.4 MB ELF 64-bit shared object)
- **Import path:** `import tinyagent` (module name differs from package name)
- **Version:** 1.1.0 confirmed via `get_tinyagent_version()`

## Key Patterns / Solutions Found

### Package Name vs Module Name
- **PyPI package:** `tiny-agent-os`
- **Python import:** `import tinyagent`
- This is correctly reflected in `src/tunacode/core/tinyagent/__init__.py` which imports `tinyagent` directly

### No Local Override Required
The codebase has no local tinyagent build configuration. The dependency flows:
```
pip install tunacode-cli → installs tiny-agent-os v1.1.0 → provides tinyagent module
```

### Developer vs End-User Installation
| User Type | Command | Dependency Source |
|-----------|---------|-------------------|
| Developer | `make dev-setup` or `uv sync --extra dev` | PyPI via uv.lock |
| End-user | `scripts/install_linux.sh` | PyPI via pip/uv |

## Knowledge Gaps

- None identified for installation flow

## References

- `pyproject.toml` - Dependency declaration
- `scripts/dev-setup.sh` - Developer environment setup
- `scripts/install_linux.sh` - End-user production installer
- `src/tunacode/core/tinyagent/__init__.py` - tinyagent integration scaffolding
