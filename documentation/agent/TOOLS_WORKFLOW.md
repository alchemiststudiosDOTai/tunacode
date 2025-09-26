# TUNACODE Tools Architecture & Usage Guide

## Overview
This document outlines the complete tool logic, file locations, and workflow patterns for the TUNACODE CLI agent system.

## Tool Categories & Performance

### 🔍 **Read-Only Tools (Parallel - 3x Faster)**
Operate simultaneously in batches of 3-4 for optimal performance.

| Tool | Purpose | Pattern | Example Output |
|------|---------|---------|----------------|
| **read_file** | Direct file access | `read_file("src/main.py")` | Line-numbered content |
| **grep** | Text search across files | `grep("TODO", ".")` | Matching lines with context |
| **list_dir** | Directory exploration | `list_dir("src/")` | [D] dirs, [F] files, sorted |
| **glob** | Pattern-based file finding | `glob("**/*.py")` | Recursive file paths |

**Performance Note**: 3 tools parallel = ~350ms vs 900ms sequential

### 📋 **Task Management Tools**
| Tool | Purpose | Pattern |
|------|---------|---------|
| **todo** | Break down complex work | `todo("add", "Task", priority="high")` |

### ⚡ **Write/Execute Tools (Sequential + Confirmation)**
Require user confirmation, execute one at a time for safety.

| Tool | Purpose | Safety |
|------|---------|--------|
| **write_file** | Create new files | Fails if file exists |
| **update_file** | Modify existing | Shows diff before apply |
| **run_command** | Simple shell commands | Full command confirmation |
| **bash** | Advanced shell scripting | Enhanced security limits |

## File System Rules

### Path Handling
- **ALWAYS use relative paths**: `src/main.py` ✅
- **NEVER use absolute paths**: `/home/user/file.py` ❌
- **Current directory context**: Respects `pwd` location
- **Directory verification**: Use `list_dir()` to confirm existence

### File Locations
```
├── src/                    # Main source code
│   ├── __init__.py
│   └── *.py               # Python modules
├── tests/                  # Test files
│   ├── __init__.py
│   └── test_*.py          # pytest test files
├── docs/                   # Documentation
│   └── TOOLS_WORKFLOW.md  # This file
├── config/                 # Configuration files
│   └── *.json/*.yaml
├── cli/                   # CLI components
├── core/                  # Core modules
└── logs/                  # Log files
```

## Workflow Patterns

### Pattern 1: Quick Exploration (3-4 Tools)
```bash
# Investigate project structure
❯ list_dir(".")                    # Current directory
❯ read_file("README.md")          # Project docs
❯ read_file("pyproject.toml")      # Package config
❯ glob("src/**/*.py")             # Python files

# Find authentication code
❯ grep("auth", "src/")            # Auth mentions
❯ glob("**/*auth*.py")            # Auth files
❯ read_file("src/auth.py")        # Auth module
```

### Pattern 2: Bug Investigation (Sequential)
```bash
# Step 1: Find the error
❯ grep("ValueError", "logs/")
❯ grep("TypeError", "src/")

# Step 2: Read relevant files
❯ read_file("src/validator.py")
❯ read_file("tests/test_validator.py")

# Step 3: Make fix (requires confirmation)
❯ update_file("src/validator.py", old_code, new_code)

# Step 4: Verify
❯ run_command("pytest tests/test_validator.py -v")
```

### Pattern 3: Complex Implementation
```bash
# Breakdown complex task
❯ todo("add_multiple", todos=[
    {"content": "Analyze current system", "priority": "high"},
    {"content": "Design new feature", "priority": "high"},
    {"content": "Implement core logic", "priority": "medium"},
    {"content": "Write tests", "priority": "low"}
  ])

# Execute each step
❯ todo("update", todo_id="1", status="in_progress")
[...work...]
❯ todo("complete", todo_id="1")
```

## Performance Optimization

### Optimal Batch Sizes
- **3 tools**: Ideal parallelization (~350ms total)
- **4 tools**: Still optimal (~400ms total)
- **5+ tools**: Diminishing returns, harder to track

### Speed Comparisons
- **1 tool sequential**: ~300ms
- **3 tools sequential**: ~900ms (3x slower)
- **3 tools parallel**: ~350ms (3x faster!)
- **8+ tools parallel**: ~600ms+ (inefficient)

### Memory Limits
- **read_file**: 4KB file limit
- **Command outputs**: 5KB limit
- **grep results**: 50 results max by default

## Error Handling Patterns

### Common Scenarios
```bash
# File doesn't exist
❯ read_file("nonexistent.py")        → Error message returned

# Directory empty
❯ list_dir("empty_dir/")             → "Directory empty"

# No matches
❯ grep("pattern", "empty_dir/")       → "No results found"

# Permission issues
❯ read_file("/etc/passwd")           → Relative path required error
```

### Verification Patterns
```bash
# Before operations
❯ list_dir("path/")                  # Check directory exists
❯ glob("src/**/*.py")               # Confirm file patterns
❯ run_command("ls path/")            # Shell verification
```

## Security Model

### Tool Safety Levels
1. **Read-only tools**: No user confirmation needed
2. **Write/execute tools**: Always confirm with diff
3. **Bash commands**: Enhanced security with environment controls
4. **File paths**: Restricted to working directory only

### Risk Mitigation
- **write_file**: Fails if file exists (no overwrites)
- **update_file**: Shows exact diff before applying
- **run_command**: Full command confirmation required
- **bash**: Output limits prevent infinite loops

## Integration with AGENTS.md
The system loads AGENTS.md (found via directory tree walk) and appends its content to the agent's system prompt, providing:
- Build commands
- Code style guidelines
- Architecture notes
- Best practices

## Usage Examples

### Quick Start
```bash
# Explore current project
❯ list_dir(".")
❯ read_file("README.md")
❯ glob("**/*.py")

# Find specific functionality
❯ grep("class.*Handler", "src/")
❯ grep("import requests", "src/")

# Create new feature
❯ write_file("src/new_feature.py", "def process(): pass")
```

### Advanced Patterns
```bash
# Find and read all tests
❯ glob("**/test_*.py")
❯ read_file("tests/test_main.py")
❯ read_file("tests/test_utils.py")

# Investigate dependencies
❯ grep("requirements", ".")
❯ read_file("requirements.txt")
❯ read_file("pyproject.toml")
```

---

*File Location: `./TOOLS_WORKFLOW.md`*
*Created by: TUNACODE CLI Agent*
*Version: 1.0*
