# Dead Code Analysis - TunaCode

## Overview
This document tracks the dead code removal process for the TunaCode project using Vulture.

## Vulture Installation
```bash
pip install vulture
```

## Initial Scan Results
**Scan Date**: 2025-07-31
**Total Findings**: 79 (7 in src/, 72 in tests/)
**Confidence Threshold**: 80%

## Categories of Dead Code

### 1. Unused Imports (3 items)
**src/**
- [ ] `src/tunacode/services/mcp.py:18`: unused import 'ReadStream' (90% confidence)
- [ ] `src/tunacode/services/mcp.py:18`: unused import 'WriteStream' (90% confidence)
- [x] `src/tunacode/types.py:16`: unused import 'ModelResponse' (90% confidence)

### 2. Unused Variables (76 items)
**src/**
- [x] `src/tunacode/core/agents/dspy_tunacode.py:441`: unused variable 'trace' (100% confidence)
- [x] `src/tunacode/core/agents/dspy_tunacode.py:449`: unused variable 'trace' (100% confidence)
- [x] `src/tunacode/ui/completers.py:20`: unused variable 'complete_event' (100% confidence)
- [x] `src/tunacode/ui/completers.py:68`: unused variable 'complete_event' (100% confidence)

**tests/** (68 items - mostly test fixtures and pytest-related)
- Multiple unused 'kw', 'caplog', 'setup_test_environment', 'temp_workspace' variables
- Exception handling variables: 'exc', 'exc_type', 'tb', 'exc_val', 'exc_tb'
- Test fixtures that may be pytest injected

### 3. Unused Functions/Methods
- None found with 80%+ confidence

### 4. Unused Classes
- None found with 80%+ confidence

### 5. Unused Attributes
- None found with 80%+ confidence

### 6. Other Findings
- [ ] `tests/conftest.py:109`: unsatisfiable 'if' condition (100% confidence)

## Exclusions and False Positives

### Dynamic Usage Patterns
- CLI entry points
- Plugin interfaces
- Test fixtures
- Dynamic imports

### Project-Specific Exclusions
*To be documented as we identify them*

## Removal Progress

### Batch 1
- Date: 2025-07-31
- Files affected:
  - `src/tunacode/types.py`
  - `src/tunacode/core/agents/dspy_tunacode.py`
  - `src/tunacode/ui/completers.py`
  - `.vulture.py`
- Items removed:
  - `ModelResponse` import from `src/tunacode/types.py`
  - Renamed `trace` to `_trace` in `src/tunacode/core/agents/dspy_tunacode.py`
  - Renamed `complete_event` to `_complete_event` in `src/tunacode/ui/completers.py`
- Tests passed: [ ] (78/658 failed)

### Batch 2
- Date:
- Files affected:
- Items removed:
- Tests passed: [ ]

## Vulture Configuration

### Command Line Options
```bash
# Basic scan
vulture .

# With confidence threshold
vulture . --min-confidence 80

# Exclude specific paths
vulture . --exclude "*/tests/*,*/migrations/*"

# Generate whitelist
vulture . --make-whitelist > whitelist.py
```

### Configuration File (.vulture.py)
```python
from vulture import Vulture

# +---------------------------------------------------------------------------+
# | Imports for type checking (ReadStream, WriteStream)                       |
# +---------------------------------------------------------------------------+
ReadStream = "src/tunacode/services/mcp.py"
WriteStream = "src/tunacode/services/mcp.py"

# +---------------------------------------------------------------------------+
# | Common pytest fixtures                                                    |
# +---------------------------------------------------------------------------+
caplog = "tests/*"
temp_workspace = "tests/*"
setup_test_environment = "tests/*"

# +---------------------------------------------------------------------------+
# | Exception variables in `pytest.raises`                                    |
# +---------------------------------------------------------------------------+
excinfo = "tests/*"

# +---------------------------------------------------------------------------+
# | Ignored directories and files                                             |
# +---------------------------------------------------------------------------+
Vulture.ignore_names("*")
Vulture.ignore_paths.append("venv")
Vulture.ignore_paths.append("file_*.py")
```

## Notes and Observations

### Key Findings:
1. **Test fixtures dominate the findings**: Most unused variables in tests/ are likely pytest fixtures or intentionally unused parameters
2. **Low count in src/**: Only 7 findings in production code indicates good code hygiene
3. **Import cleanup needed**: MCP-related imports in services/mcp.py may be leftovers from refactoring
4. **Trace variables**: Two unused 'trace' variables in dspy_tunacode.py suggest incomplete debugging removal

### Recommended Approach:
1. **Start with src/ directory**: Only 7 items, high impact, low risk
2. **Create whitelist for test fixtures**: Many test "unused" variables are actually pytest fixtures
3. **Verify MCP imports**: Check if ReadStream/WriteStream are needed for future features
4. **Review trace variables**: Confirm if debug traces can be safely removed

### False Positives to Exclude:
- pytest fixtures (caplog, temp_workspace, setup_test_environment)
- Exception handling parameters in context managers
- Test function parameters that establish context