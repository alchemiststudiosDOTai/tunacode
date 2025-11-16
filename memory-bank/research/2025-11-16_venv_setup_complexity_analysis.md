# Research – Virtual Environment Setup Complexity Analysis

**Date:** 2025-11-16
**Owner:** context-engineer:research
**Phase:** Research
**Components:** scripts/setup_dev_env.sh, pyproject.toml, hatch configuration
**Tags:** build-system, environment-setup, dependency-management, hatch, uv

## Goal

Map out the current virtual environment setup logic to understand why 3 different virtual environments exist (venv/, .venv/, and hatch's cache environments), identify the root causes of complexity, and provide recommendations for a single, unified dev environment setup command.

## Findings

### Problem: 3 Different Virtual Environments

1. **`/Users/tuna/Desktop/tunacode/venv/`** - Python 3.12.12
   - Created by: `scripts/setup_dev_env.sh` (non-Hatch path)
   - When: Hatch is NOT available
   - How: `uv venv` or `python -m venv`

2. **`/Users/tuna/Desktop/tunacode/.venv/`** - Python 3.10.19
   - Created by: Hatch internally
   - When: `hatch run` commands are executed
   - How: Hatch's default environment creation in project directory (non-standard)

3. **`~/.local/share/hatch/env/virtual/tunacode-cli-{env}-{hash}/`**
   - Created by: Hatch (standard location)
   - Environments: default, test, lint, py310, py311, py312, py313
   - When: `hatch run` commands are executed
   - How: Hatch's platform-specific cache directory

### Root Cause Analysis

#### Strategy Conflict: Setup Script vs. Hatch

**Setup Script Philosophy** (`scripts/setup_dev_env.sh`):
- Single venv for all work
- Created at project root (`./venv/`)
- Activated once, used for everything
- Fallback-oriented (UV → pip → system Python)
- Prefers newest Python (3.13 → 3.12 → 3.11 → 3.10)

**Hatch Philosophy** (`pyproject.toml`):
- Multiple isolated environments for different purposes
- Created in system cache (`~/.local/share/hatch/env/virtual/`)
- Contextual activation via `hatch run {script}`
- Modern, declarative configuration
- Uses system default Python (must satisfy `>=3.10,<3.14`)

#### Bug in Setup Script

**Lines 299-313** of `setup_dev_env.sh`:
```bash
if [ "$HATCH_AVAILABLE" = true ]; then
    log "\n${BLUE}Using Hatch for environment management...${NC}"
    # Hatch manages its own environments - NO .venv created here
elif [ ! -d "$VENV_DIR" ]; then
    uv venv "$VENV_DIR"  # Only creates venv/ when Hatch NOT available
fi
```

But **lines 430, 448, 485**:
```bash
if [ "$HATCH_AVAILABLE" = true ]; then
    if ".venv/bin/tunacode" --version &>/dev/null; then  # BUG!
        # Assumes .venv exists, but Hatch doesn't create it here
```

The script assumes `.venv` exists when Hatch is available, but Hatch creates environments in `~/.local/share/hatch/env/virtual/`, NOT `.venv` by default.

### Environment Setup Decision Tree

```
START
│
├─ Tool Detection
│  ├─ UV available? (uv --version)
│  ├─ Hatch available? (hatch --version)
│  └─ Result: Set UV_AVAILABLE, HATCH_AVAILABLE, USE_UV flags
│
├─ Python Version Selection
│  ├─ IF UV available:
│  │  ├─ Try: uv python find 3.13/3.12/3.11/3.10
│  │  └─ Fallback: uv python install 3.12
│  └─ IF UV not available:
│     └─ Try: python3.13 → python3.12 → python3.11 → python3.10 → python3
│
├─ Virtual Environment Creation
│  ├─ IF HATCH_AVAILABLE:
│  │  ├─ DON'T create venv/ (Hatch manages it)
│  │  ├─ Run: hatch env create
│  │  └─ Hatch creates in: ~/.local/share/hatch/env/virtual/
│  └─ ELSE (no Hatch):
│     ├─ IF UV available:
│     │  └─ Run: uv venv ./venv
│     └─ ELSE:
│        └─ Run: python -m venv ./venv
│
├─ Dependency Installation
│  ├─ IF HATCH_AVAILABLE && USE_UV:
│  │  └─ Run: uv pip install -e ".[dev]" (via Hatch)
│  ├─ ELSE IF HATCH_AVAILABLE:
│  │  └─ Run: pip install -e ".[dev]" (via Hatch)
│  └─ ELSE (manual install):
│     ├─ Install: pydantic-ai==0.2.6 (critical)
│     ├─ Install: -e ".[dev]"
│     └─ Install: pytest-asyncio
│
└─ Verification
   ├─ Import checks for 8 critical packages
   ├─ CLI verification (tunacode --version)
   └─ Test run (pytest tests/test_security.py)
```

### Hatch Environment Architecture

**Defined Environments** (from `pyproject.toml`):

1. **default** (lines 156-227)
   - Installer: UV (fast)
   - Features: ["dev"]
   - Python: System default (unspecified)
   - Dependencies: All base + all dev packages
   - Scripts: test, lint, typecheck, security, clean, build, etc.

2. **test** (lines 231-241)
   - Dependencies: pytest, pytest-cov, pytest-asyncio (minimal)
   - Purpose: Lightweight testing environment

3. **lint** (lines 243-257)
   - Dependencies: ruff, mypy, bandit, vulture
   - Purpose: Code quality checks

4. **py310, py311, py312, py313** (lines 259-269)
   - Purpose: Matrix testing across Python versions
   - Each has explicit Python version pinned
   - Inherits dev features from default

**Environment Locations**:
- Default: `~/.local/share/hatch/env/virtual/tunacode-cli-default-{hash}/`
- Each environment is isolated with its own Python interpreter and site-packages

### Execution Path Comparison

**Current State - Option A (Setup Script + venv/)**:
```bash
bash scripts/setup_dev_env.sh
source venv/bin/activate
pytest tests/
```
- Creates: `./venv/` with Python 3.12
- Pros: Single environment, simple activation
- Cons: Doesn't use Hatch's features, manual management

**Current State - Option B (Hatch)**:
```bash
hatch run test
```
- Creates: `~/.local/share/hatch/env/virtual/tunacode-cli-default-{hash}/`
- Pros: Modern, declarative, multiple environments, UV integration
- Cons: Hidden location, import errors (see current issue), complexity

**Result**: Users run the setup script (creates venv/), then run `hatch run test` (creates .venv/ or cache env), ending up with 2-3 environments.

## Key Patterns / Solutions Found

### Pattern 1: Fallback Layers

The setup script implements sophisticated fallback logic:
```
UV + Hatch (best)
  ↓ (if no Hatch)
UV + manual venv
  ↓ (if no UV)
pip + manual venv
```

Each layer works, but creates different outcomes (different paths, different Python versions).

### Pattern 2: Dual Package Manager Strategy

- `pyproject.toml` declares `installer = "uv"` for Hatch's default environment
- Setup script uses UV directly when Hatch isn't available
- This creates confusion: Is UV the primary installer, or is Hatch?

### Pattern 3: Version Priority Mismatch

- Setup script prefers **newest** Python (3.13 → 3.12 → 3.11 → 3.10)
- MyPy config targets **minimum** Python (3.10 for compatibility)
- `requires-python = ">=3.10,<3.14"` allows **any** in range
- Result: Different environments use different Python versions

### Pattern 4: Environment Location Confusion

Files reference 3 different paths:
1. `VENV_DIR` variable → `./venv/` (line 29)
2. Hardcoded `.venv/` (lines 430, 448, 485)
3. Hatch's cache (not referenced in setup script)

## Knowledge Gaps

1. **Why does .venv/ exist at all?**
   - Setup script never creates it when Hatch is available
   - Yet it's referenced in verification steps
   - Likely created by Hatch during a previous `hatch run` invocation

2. **Which environment does `hatch run test` actually use?**
   - Default environment in cache?
   - .venv/ in project root?
   - Need to verify with `hatch env show`

3. **What is the intended workflow?**
   - Should developers use the setup script OR Hatch, not both?
   - Should the setup script be deprecated in favor of pure Hatch?

## References

### Configuration Files
- `/Users/tuna/Desktop/tunacode/pyproject.toml:1-273` - Project configuration, all Hatch settings
- `/Users/tuna/Desktop/tunacode/scripts/setup_dev_env.sh:1-525` - Setup script with all logic
- `/Users/tuna/Desktop/tunacode/tests/conftest.py:1-474` - Test stubs for when packages aren't installed

### Related Files
- `/Users/tuna/Desktop/tunacode/scripts/install_linux.sh` - User installation script (creates `~/.tunacode-venv`)
- `/Users/tuna/Desktop/tunacode/scripts/verify_dev_env.sh` - Environment verification
- `/Users/tuna/Desktop/tunacode/.github/workflows/publish-release.yml` - CI/CD uses Hatch
- `/Users/tuna/Desktop/tunacode/documentation/development/hatch-build-system.md` - Hatch documentation

### Search Terms
- `grep -ri "venv" scripts/`
- `grep -ri "HATCH" scripts/setup_dev_env.sh`
- `grep -ri "installer.*uv" pyproject.toml`

## Recommendations

### Option 1: Pure Hatch Workflow (Recommended)

**Eliminate** `scripts/setup_dev_env.sh` complexity and rely entirely on Hatch:

```bash
# New simplified setup
uv tool install hatch  # Or: pip install --user hatch
hatch env create       # Creates default environment with UV installer
hatch run test         # Run tests
hatch shell            # Enter shell with activated environment
```

**Benefits**:
- Single source of truth (pyproject.toml)
- Automatic environment management
- UV integration built-in
- Matrix testing for free (py310-py313)
- No bash script complexity

**Changes Required**:
1. Add `README.md` section: "Developer Setup"
2. Update `CLAUDE.md` workflow rules to use `hatch run` exclusively
3. Delete or archive `scripts/setup_dev_env.sh`
4. Remove venv/ and .venv/ from repository (add to .gitignore)

### Option 2: Simplified Setup Script

Keep a minimal setup script that **delegates to Hatch**:

```bash
#!/usr/bin/env bash
# scripts/setup_dev.sh - Simplified

set -euo pipefail

# Install UV if not available
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Install Hatch via UV
uv tool install hatch

# Let Hatch handle everything else
hatch env create

echo "✓ Setup complete! Run: hatch shell"
```

**Benefits**:
- Single command: `bash scripts/setup_dev.sh`
- Delegates complexity to Hatch
- Still provides UV auto-install convenience

### Option 3: Hybrid with Clear Separation

Keep both, but **never use both** in same workflow:

**For Users** (installing the CLI):
```bash
uv tool install tunacode-cli
```

**For Developers** (contributing to project):
```bash
hatch env create
hatch run test
```

**Changes Required**:
1. Rename `setup_dev_env.sh` → `setup_legacy.sh`
2. Add warning: "Use `hatch env create` instead for modern workflow"
3. Fix the `.venv/` bug in lines 430/448/485

## Conclusion

The current setup has **3 different virtual environment creation paths** due to:
1. Fallback strategy in setup script (UV → pip → system Python)
2. Hatch creating environments in cache + possibly .venv/
3. Bug in setup script assuming .venv/ exists when using Hatch

**Recommended solution**: Adopt **Option 1 (Pure Hatch Workflow)** to eliminate complexity, use modern tooling, and provide a single source of truth for environment management.

**Next Steps**:
1. Verify current environment state: `hatch env show`
2. Test pure Hatch workflow: `hatch env prune && hatch env create && hatch run test`
3. Confirm all 222 tests pass in Hatch's default environment
4. Update documentation to reflect new workflow
5. Archive old setup script for reference
