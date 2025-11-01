# Kimi CLI Architecture Documentation Index

This directory contains comprehensive analysis of Kimi CLI's production-grade software architecture.

## Documents

### 1. ARCHITECTURE_SUMMARY.md (Quick Start)
**Length**: 395 lines | **Read Time**: 15 minutes

A high-level overview of the 10 core patterns with:
- Quick reference table for all 10 patterns
- Key design decisions and rationale
- Simplified architecture diagram
- Testing model overview
- Extension points for new tools/agents
- Error handling philosophy
- Performance considerations
- Operational insights

**Start here** if you want a quick understanding of the system design.

### 2. ARCHITECTURE_PATTERNS.md (Deep Dive)
**Length**: 1189 lines | **Read Time**: 45 minutes

Detailed analysis of each pattern with:
- Specific file references from codebase
- Code examples from actual implementation
- Explanation of why each pattern is exemplary
- Comparison to alternative approaches
- Impact on system behavior
- Test coverage examples
- Table summarizing all 10 patterns

**Read this** for comprehensive understanding of each architectural decision.

## The 10 Patterns

All patterns are explained in both documents:

1. **Separation of Concerns** - Each module has one clear responsibility
2. **Declarative Extensibility** - New behavior declared in YAML, not hardcoded in Python
3. **Type-First Design** - Pydantic models ensure correctness at instantiation
4. **Constructor-Based Dependency Injection** - Dependencies are explicit, testable
5. **Explicit Result Types** - Functions return structured results, not strings
6. **Async-by-Default I/O** - All I/O is async with timeouts and cleanup
7. **Production-Grade Error Flow** - Typed exceptions, error chaining, selective retries
8. **Consistent Output Building** - Uniform truncation across all tools
9. **Testability** - Composable fixtures, mockable dependencies, async tests
10. **Operational Clarity** - Semantic naming, self-documenting code, structured logging

## Quick Navigation

### By Pattern Number

| Pattern | Summary Doc | Patterns Doc | Key Files |
|---------|-------------|--------------|-----------|
| 1. Separation of Concerns | Section "1. Separation..." | Section "1. SEPARATION..." | `config.py`, `soul/runtime.py`, `soul/context.py` |
| 2. Declarative Extensibility | Section "2. Declarative..." | Section "2. DECLARATIVE..." | `agentspec.py`, `soul/agent.py` |
| 3. Type-First Design | Section "3. Type-First..." | Section "3. TYPE-FIRST..." | `config.py`, `tools/bash/__init__.py`, `llm.py` |
| 4. Constructor-Based DI | Section "4. Constructor..." | Section "4. CONSTRUCTOR..." | `tools/bash/__init__.py`, `soul/agent.py` |
| 5. Explicit Result Types | Section "5. Explicit..." | Section "5. EXPLICIT..." | `tools/utils.py`, `soul/__init__.py` |
| 6. Async-by-Default I/O | Section "6. Async..." | Section "6. ASYNC-BY-DEFAULT..." | `soul/context.py`, `tools/bash/__init__.py` |
| 7. Production-Grade Errors | Section "7. Production..." | Section "7. PRODUCTION-GRADE..." | `exception.py`, `config.py`, `soul/kimisoul.py` |
| 8. Consistent Output | Section "8. Output..." | Section "8. CONSISTENT..." | `tools/utils.py` |
| 9. Testability | Section "9. Testability" | Section "9. TESTABILITY" | `conftest.py`, `soul/toolset.py`, `test_bash.py` |
| 10. Operational Clarity | Section "10. Operational..." | Section "10. OPERATIONAL..." | `soul/context.py`, `shell_manager.py` |

### By Use Case

#### I want to...

**Understand the system at a high level**
- Read: ARCHITECTURE_SUMMARY.md (all sections)
- Time: 15 minutes

**Implement a new tool**
- Read: ARCHITECTURE_SUMMARY.md → "Extension Points"
- Read: ARCHITECTURE_PATTERNS.md → "4. Constructor-Based DI"
- Read: ARCHITECTURE_PATTERNS.md → "8. Consistent Output"
- Reference: `src/kimi_cli/tools/bash/__init__.py`
- Time: 30 minutes

**Add a new agent**
- Read: ARCHITECTURE_SUMMARY.md → "Extension Points"
- Read: ARCHITECTURE_PATTERNS.md → "2. Declarative Extensibility"
- Reference: `src/kimi_cli/agents/default/agent.yaml`
- Time: 10 minutes

**Understand error handling**
- Read: ARCHITECTURE_SUMMARY.md → "Error Handling Philosophy"
- Read: ARCHITECTURE_PATTERNS.md → "7. Production-Grade Error Flow"
- Reference: `src/kimi_cli/exception.py`
- Time: 15 minutes

**Write tests for a tool**
- Read: ARCHITECTURE_PATTERNS.md → "9. Testability"
- Read: ARCHITECTURE_SUMMARY.md → "Testing Model"
- Reference: `tests/conftest.py`, `tests/test_bash.py`
- Time: 20 minutes

**Debug a runtime issue**
- Read: ARCHITECTURE_SUMMARY.md → "Operational Insights"
- Read: ARCHITECTURE_PATTERNS.md → "7. Production-Grade Error Flow"
- Reference: `src/kimi_cli/utils/logging.py`, `src/kimi_cli/soul/context.py`
- Time: 15 minutes

**Optimize performance**
- Read: ARCHITECTURE_SUMMARY.md → "Performance Considerations"
- Read: ARCHITECTURE_PATTERNS.md → "6. Async-by-Default I/O"
- Reference: `src/kimi_cli/soul/kimisoul.py`, `src/kimi_cli/tools/utils.py`
- Time: 20 minutes

## Key Design Decisions (Summary)

### Reflection-Based Tool Loading
**Why**: New tools are auto-discovered without registration. YAML lists tool paths; Python inspects constructors.
- **Pattern**: 2. Declarative Extensibility
- **Pattern Doc**: Section "**`src/kimi_cli/soul/agent.py` - _load_tool()**"

### ContextVar for Tool Metadata
**Why**: Tools need access to their own tool call context without threading parameters through all layers. Async-safe.
- **Pattern**: 4. Constructor-Based DI
- **Pattern Doc**: Section "**`src/kimi_cli/soul/toolset.py`**"

### Wire Pattern for Soul ↔ UI
**Why**: Decouples agent from UI. Enables streaming output, approval requests, cancellation.
- **Pattern**: 6. Async-by-Default I/O
- **Pattern Doc**: Section "**`src/kimi_cli/wire/__init__.py`**"

### Checkpoint-Based Context
**Why**: Survives process crashes. Enables time-travel messaging (D-Mail) and recovery.
- **Pattern**: 1. Separation of Concerns
- **Pattern Doc**: Section "**`src/kimi_cli/soul/context.py`**"

### ToolResultBuilder Pattern
**Why**: Uniform output limits across all tools. Truncation is transparent to tool authors.
- **Pattern**: 8. Consistent Output Building
- **Pattern Doc**: Entire section "8. CONSISTENT..."

## File References

All patterns reference specific files. Here's the complete list:

**Core System**
- `src/kimi_cli/config.py` - Configuration management (Patterns 1, 3, 7)
- `src/kimi_cli/agentspec.py` - Agent specification (Patterns 2, 3, 7)
- `src/kimi_cli/llm.py` - LLM abstraction (Patterns 3, 4)
- `src/kimi_cli/exception.py` - Exception hierarchy (Patterns 5, 7)

**Soul (Agent Execution)**
- `src/kimi_cli/soul/__init__.py` - Soul protocol (Patterns 3, 5, 6, 7)
- `src/kimi_cli/soul/agent.py` - Agent loading (Patterns 2, 4)
- `src/kimi_cli/soul/kimisoul.py` - Main agent loop (Patterns 5, 6, 7)
- `src/kimi_cli/soul/context.py` - Context management (Patterns 1, 6)
- `src/kimi_cli/soul/runtime.py` - Runtime aggregation (Patterns 1, 4)
- `src/kimi_cli/soul/toolset.py` - Tool context vars (Patterns 4, 9)

**Tools**
- `src/kimi_cli/tools/utils.py` - Result builder (Patterns 5, 8)
- `src/kimi_cli/tools/bash/__init__.py` - Bash tool (Patterns 3, 4, 6, 8)
- `src/kimi_cli/tools/file/read.py` - File reading (Patterns 3, 4, 7, 8)

**Wire (Communication)**
- `src/kimi_cli/wire/__init__.py` - Soul ↔ UI wire (Patterns 6)

**Shell**
- `src/kimi_cli/shell_manager.py` - Persistent shell (Patterns 6, 10)

**Utilities**
- `src/kimi_cli/utils/logging.py` - Structured logging (Pattern 10)

**Tests**
- `tests/conftest.py` - Test fixtures (Pattern 9)
- `tests/test_bash.py` - Tool tests (Patterns 9)
- `tests/test_result_builder.py` - Builder tests (Patterns 8, 9)

## Summary Tables

### Pattern Coverage by File

See ARCHITECTURE_PATTERNS.md section "Summary Table" for comprehensive mapping of:
- Each pattern
- Primary exemplary file
- Key insight
- How it impacts system behavior

### Design Decision Rationale

See ARCHITECTURE_SUMMARY.md sections:
- "Key Design Decisions" - 5 major decisions
- "Comparison to Alternatives" - Why these choices over others

## Next Steps

1. **First time?** → Read ARCHITECTURE_SUMMARY.md (15 min)
2. **Deep dive?** → Read ARCHITECTURE_PATTERNS.md (45 min)
3. **Implementing?** → Find your use case above, read referenced sections
4. **Questions?** → Search this index for relevant pattern/file

---

Generated: 2025-11-01
