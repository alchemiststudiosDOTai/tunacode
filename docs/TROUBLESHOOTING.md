# Troubleshooting Guide

This guide helps resolve common issues during TunaCode setup and usage.

## Table of Contents

- [Installation Issues](#installation-issues)
  - [Missing pydantic-ai Dependency](#missing-pydantic-ai-dependency)
  - [Python Version Issues](#python-version-issues)
  - [Virtual Environment Problems](#virtual-environment-problems)
  - [Permission Errors](#permission-errors)
- [Runtime Issues](#runtime-issues)
  - [Import Errors](#import-errors)
  - [API Key Problems](#api-key-problems)
  - [Model Connection Issues](#model-connection-issues)
- [Development Issues](#development-issues)
  - [Test Failures](#test-failures)
  - [Linting Errors](#linting-errors)
- [Platform-Specific Issues](#platform-specific-issues)
  - [Windows](#windows)
  - [macOS](#macos)
  - [Linux](#linux)

## Installation Issues

### Missing pydantic-ai Dependency

**Problem**: Error messages like `ModuleNotFoundError: No module named 'pydantic_ai'`

**Solution**:
```bash
# Ensure you're in the virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install pydantic-ai explicitly
pip install "pydantic-ai[logfire]==0.2.6"

# Verify installation
python -c "import pydantic_ai; print('Success!')"
```

If this fails, try:
```bash
# Clear pip cache and reinstall
pip cache purge
pip install --no-cache-dir "pydantic-ai[logfire]==0.2.6"
```

### Python Version Issues

**Problem**: `Error: Python 3.10 or higher required`

**Solution**:
1. Check your Python version:
   ```bash
   python --version
   # or
   python3 --version
   ```

2. Install Python 3.10+ if needed:
   - **Ubuntu/Debian**: `sudo apt update && sudo apt install python3.10`
   - **macOS**: `brew install python@3.10`
   - **Windows**: Download from [python.org](https://python.org)

3. Create venv with specific Python version:
   ```bash
   python3.10 -m venv venv
   ```

### Virtual Environment Problems

**Problem**: Virtual environment not activating or commands not found

**Solution**:

1. Ensure virtual environment exists:
   ```bash
   ls venv/  # Should show bin/, lib/, etc.
   ```

2. Recreate if corrupted:
   ```bash
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   ```

3. Verify activation:
   ```bash
   which python  # Should show /path/to/project/venv/bin/python
   echo $VIRTUAL_ENV  # Should show your venv path
   ```

### Permission Errors

**Problem**: `Permission denied` during installation

**Solution**:

1. Never use `sudo` with pip in a virtual environment
2. Ensure you own the project directory:
   ```bash
   sudo chown -R $USER:$USER .
   ```
3. Check file permissions:
   ```bash
   chmod -R u+rw .
   ```

## Runtime Issues

### Import Errors

**Problem**: `ImportError` when running TunaCode

**Solution**:

1. Ensure you installed in editable mode:
   ```bash
   pip install -e ".[dev]"  # Note the -e flag!
   ```

2. Check installation:
   ```bash
   pip show tunacode-cli
   ```

3. Verify all dependencies:
   ```bash
   pip check  # Should show "No broken requirements found."
   ```

4. Reinstall if needed:
   ```bash
   pip uninstall tunacode-cli -y
   pip install -e ".[dev]"
   ```

### API Key Problems

**Problem**: `API key not found` or authentication errors

**Solution**:

1. Check configuration:
   ```bash
   cat ~/.config/tunacode.json
   ```

2. Set API key correctly:
   ```bash
   # For Anthropic
   tunacode --model "anthropic:claude-3.5-sonnet" --key "sk-ant-..."
   
   # For OpenAI
   tunacode --model "openai:gpt-4" --key "sk-..."
   ```

3. Verify environment variables (if using):
   ```bash
   echo $ANTHROPIC_API_KEY
   echo $OPENAI_API_KEY
   ```

### Model Connection Issues

**Problem**: Cannot connect to AI model

**Solution**:

1. Test with a simple prompt:
   ```bash
   tunacode --model "your-model" --prompt "Say hello"
   ```

2. Check network connectivity:
   ```bash
   curl -I https://api.anthropic.com  # For Anthropic
   curl -I https://api.openai.com    # For OpenAI
   ```

3. Try a different model provider:
   ```bash
   tunacode --model "openrouter:openai/gpt-3.5-turbo" --key "sk-or-..."
   ```

## Development Issues

### Test Failures

**Problem**: Tests fail with import errors

**Solution**:

1. Ensure development dependencies are installed:
   ```bash
   pip install -e ".[dev]"
   pip install pytest-asyncio  # Sometimes needs explicit install
   ```

2. Run from project root:
   ```bash
   cd /path/to/tunacode
   pytest tests/
   ```

3. Check Python path:
   ```bash
   python -c "import sys; print('\n'.join(sys.path))"
   ```

### Linting Errors

**Problem**: Linting fails with format errors

**Solution**:

1. Auto-fix with ruff:
   ```bash
   ruff format src/ tests/
   ruff check src/ tests/ --fix
   ```

2. Check configuration:
   ```bash
   cat pyproject.toml | grep -A10 "\[tool.ruff\]"
   ```

## Platform-Specific Issues

### Windows

**Problem**: Script execution disabled

**Solution**:
```powershell
# Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Problem**: Path separators in file operations

**Solution**: TunaCode handles this automatically, but ensure you use forward slashes in paths when prompted.

### macOS

**Problem**: SSL certificate errors

**Solution**:
```bash
# Install certificates
pip install --upgrade certifi
```

**Problem**: `xcrun: error: invalid active developer path`

**Solution**:
```bash
xcode-select --install
```

### Linux

**Problem**: Missing Python development headers

**Solution**:
```bash
# Ubuntu/Debian
sudo apt-get install python3-dev

# Fedora/RHEL
sudo dnf install python3-devel
```

## Quick Recovery Steps

If all else fails, try this complete reset:

```bash
# 1. Backup your config
cp ~/.config/tunacode.json ~/.config/tunacode.json.backup

# 2. Clean everything
rm -rf venv
rm -rf build/ dist/ *.egg-info
pip cache purge

# 3. Fresh setup
./scripts/setup_dev_env.sh
# or manually:
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

# 4. Verify
python -m tunacode --version
pytest tests/test_import.py
```

## Getting Help

If you're still having issues:

1. Check existing issues: https://github.com/alchemiststudiosDOTai/tunacode/issues
2. Create a new issue with:
   - Your OS and Python version
   - Complete error message
   - Steps to reproduce
   - What you've already tried

## Common Error Messages Reference

| Error | Likely Cause | Quick Fix |
|-------|--------------|-----------|
| `ModuleNotFoundError: pydantic_ai` | Missing dependency | `pip install "pydantic-ai[logfire]==0.2.6"` |
| `No module named 'tunacode'` | Not installed in editable mode | `pip install -e ".[dev]"` |
| `Command not found: tunacode` | Not in PATH or venv not activated | `source venv/bin/activate` |
| `Permission denied` | File ownership issues | `chmod -R u+rw .` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Certificate issues | `pip install --upgrade certifi` |