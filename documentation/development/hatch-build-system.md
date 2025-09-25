# Hatch Build System

## Overview

TunaCode uses [Hatch](https://hatch.pypa.io/) as its build system and development environment manager. Hatch provides cross-platform compatibility, standardized Python tooling, and simplified dependency management.

## Installation

```bash
uv install hatch
```

## Common Commands

### Development

```bash
# Create virtual environment with UV
uv venv

# Install development dependencies
source .venv/bin/activate && uv pip install -e ".[dev]"

# Run the application
source .venv/bin/activate && tunacode

# Start development mode
source .venv/bin/activate && tunacode
```

### Testing

```bash
# Run test suite
source .venv/bin/activate && pytest

# Run tests with coverage
source .venv/bin/activate && pytest --cov=src/tunacode

# Test specific Python version
source .venv/bin/activate && python3.10 -m pytest
source .venv/bin/activate && python3.11 -m pytest
source .venv/bin/activate && python3.12 -m pytest
```

### Code Quality

```bash
# Lint and format code
source .venv/bin/activate && ruff check . && ruff format .

# Check without modifying
source .venv/bin/activate && ruff check . && ruff format --check .

# Type checking
source .venv/bin/activate && mypy src/

# Security analysis
source .venv/bin/activate && bandit -r src/ -ll

# Dead code analysis
source .venv/bin/activate && python -m vulture --config pyproject.toml
source .venv/bin/activate && python -c "print('Running comprehensive dead code analysis...')"
```

### Building & Publishing

```bash
# Build distribution packages
source .venv/bin/activate && python -m build

# Clean build artifacts
source .venv/bin/activate && python -c "import shutil, pathlib; dirs=['build', 'dist']; [shutil.rmtree(d, ignore_errors=True) for d in dirs]; print('Cleaned build artifacts')"

# Publish to PyPI
source .venv/bin/activate && twine upload dist/*
```

## Environment Management

Hatch manages isolated environments for different purposes:

- **default**: Main development environment
- **test**: Testing with pytest and coverage tools
- **lint**: Linting and formatting tools
- **py310/py311/py312**: Python version-specific environments

### Using Environments

```bash
# Run command in specific environment
hatch run test:pytest tests/

# Enter environment shell
hatch shell test
```

## Configuration

All Hatch configuration is in `pyproject.toml`:

```toml
[tool.hatch.envs.default.scripts]
# Script definitions

[tool.hatch.envs.test]
# Test environment configuration

[tool.hatch.build.targets.wheel]
# Build configuration
```

## Migration from Makefile

| Old Command | New Command |
|------------|-------------|
| `make install` | `source .venv/bin/activate && uv pip install -e ".[dev]"` |
| `make test` | `source .venv/bin/activate && pytest` |
| `make lint` | `source .venv/bin/activate && ruff check . && ruff format .` |
| `make build` | `source .venv/bin/activate && python -m build` |
| `make clean` | `source .venv/bin/activate && python -c "import shutil; dirs=['build', 'dist']; [shutil.rmtree(d, ignore_errors=True) for d in dirs]"` |
| `make coverage` | `source .venv/bin/activate && pytest --cov=src/tunacode` |
| `make vulture` | `source .venv/bin/activate && python -m vulture --config pyproject.toml` |

## Troubleshooting

### UV not found

Install UV for faster package management:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Virtual environment issues

Recreate virtual environment:
```bash
rm -rf .venv
uv venv
source .venv/bin/activate && uv pip install -e ".[dev]"
```

### Build errors

Clean and rebuild:
```bash
source .venv/bin/activate && python -c "import shutil; dirs=['build', 'dist']; [shutil.rmtree(d, ignore_errors=True) for d in dirs]"
source .venv/bin/activate && python -m build
```

## Advanced Usage

### Matrix Testing

Test across multiple Python versions:
```bash
hatch run test:all
```

### Custom Scripts

Add custom scripts to `pyproject.toml`:
```toml
[tool.hatch.envs.default.scripts]
my-command = "python scripts/my_script.py"
```

### Environment Variables

Set environment variables:
```toml
[tool.hatch.envs.default.env-vars]
MY_VAR = "value"
```

## Benefits

1. **Cross-platform**: Works on Windows, macOS, and Linux
2. **No external dependencies**: No need for make or other build tools
3. **Python-native**: Integrates seamlessly with Python ecosystem
4. **Environment isolation**: Separate environments for different tasks
5. **Standardized**: Follows Python packaging standards (PEP 517/518)
