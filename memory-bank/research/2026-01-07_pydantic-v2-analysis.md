# Research – Pydantic V2 Usage Analysis
**Date:** 2026-01-07
**Owner:** claude-agent
**Phase:** Research

## Goal
Audit tunacode's Pydantic usage against latest V2 best practices. Identify antipatterns, deprecated code, and migration opportunities.

## Findings

### Current Usage Summary

| File | Pattern | V2 Status | Issues |
|------|---------|-----------|--------|
| `src/tunacode/core/state.py:256-299` | TypeAdapter with `dump_python`/`validate_python` | ✅ Modern V2 | None |
| `src/tunacode/utils/parsing/tool_parser.py` | dataclass + manual JSON parsing | N/A (not Pydantic) | Appropriate for use case |
| `src/tunacode/types/pydantic_ai.py` | Type re-exports only | ✅ V2 | None |
| `src/tunacode/core/agents/agent_components/agent_config.py` | pydantic-ai Agent construction | ✅ V2 | None |

### Detailed File Analysis

**Core Pydantic Usage (2 files):**
- `src/tunacode/core/state.py:258-271` - Message serialization with TypeAdapter
- `src/tunacode/types/pydantic_ai.py` - Type wrapper/re-exports

**Pydantic-AI Framework (20 files):**
- Agent creation: `core/agents/main.py`, `core/agents/research_agent.py`
- Message types: `ui/app.py`, `ui/headless/output.py`
- Retry handling: All tool files use `ModelRetry` from pydantic_ai.exceptions
- Streaming: `core/agents/agent_components/streaming.py`

### V2 Compliance Verification

**Patterns Found (All Correct V2):**
```python
# state.py - TypeAdapter usage (CORRECT)
from pydantic import TypeAdapter
msg_adapter = TypeAdapter(ModelMessage)
result.append(msg_adapter.dump_python(msg, mode="json"))
result.append(msg_adapter.validate_python(item))
```

**V1 Deprecated Patterns NOT Found:**
- ❌ `parse_obj()` - Not used
- ❌ `parse_raw()` - Not used
- ❌ `.dict()` - Not used
- ❌ `.json()` - Not used
- ❌ `@validator` - Not used
- ❌ `BaseModel` direct usage - Not used

### Pydantic V2 Best Practices Reference

| V1 (Deprecated) | V2 (Current) |
|-----------------|--------------|
| `.parse_obj(obj)` | `.model_validate(obj)` |
| `.parse_raw(json_str)` | `.model_validate_json(json_str)` |
| `.json()` | `.model_dump_json()` |
| `.dict()` | `.model_dump()` |
| `@validator` | `@field_validator` |

**TypeAdapter Best Practices:**
- `dump_python(mode='json')` - JSON-compatible output (used correctly in state.py)
- `validate_python()` - Runtime validation (used correctly)
- Cache TypeAdapter instances - Don't recreate per call (done correctly)

### Migration Opportunities

**High Priority (Manual Validation → Pydantic):**

1. **UserConfig** (`types/base.py`)
   - Currently: `dict[str, Any]`
   - Opportunity: Pydantic model with field validation
   - Impact: 15+ files use this type

2. **Session Persistence** (`core/state.py`)
   - Currently: Manual dict validation in `_serialize_messages`/`_deserialize_messages`
   - Already uses TypeAdapter correctly - no changes needed

3. **Tool Arguments** (`utils/parsing/tool_parser.py`)
   - Currently: Plain dataclass + json.loads
   - Opportunity: Pydantic model for structured validation
   - Note: Current approach is appropriate for unpredictable LLM output formats

**Medium Priority:**

4. **Configuration Models** (`configuration/models.py`)
   - ModelConfig, ModelPricing could be Pydantic models
   - Would add validation during JSON registry loading

5. **Renderer Data Classes** (26 dataclasses in `ui/renderers/`)
   - GrepData, BashData, ReadFileData, etc.
   - Could benefit from Pydantic for validation

6. **Search Structures** (`tools/grep_components/`)
   - SearchResult, SearchConfig dataclasses
   - Good candidates for Pydantic models

### Codebase Statistics

- **JSON parsing locations**: 12 files
- **Dataclass definitions**: 26 dataclasses across 15 files
- **Manual isinstance() checks**: 20+ files
- **Existing Pydantic/pydantic-ai usage**: 22 files
- **Type aliases as dict[str, Any]**: 6+ in types/base.py

## Key Patterns / Solutions Found

- `TypeAdapter`: Correct pattern for non-BaseModel serialization - used properly
- `mode='json'`: JSON-compatible output mode - used correctly in state.py
- `validate_python()`: Runtime validation replacing V1's `parse_obj()` - used correctly
- `ModelRetry`: Consistent exception pattern across all tools - good hygiene
- Type isolation: pydantic dependencies isolated to `types/pydantic_ai.py` - excellent practice

## Knowledge Gaps

- No custom Pydantic BaseModel classes exist in codebase
- Heavy reliance on `dict[str, Any]` for configuration types
- Manual validation scattered across 20+ files could be consolidated

## Verdict

**The codebase is 100% Pydantic V2 compliant.**

- TypeAdapter usage in `state.py` matches current best practices
- No deprecated V1 patterns anywhere
- `tool_parser.py` appropriately uses plain dataclasses for unpredictable LLM output
- All pydantic-ai framework usage is modern

**Recommendations:**
1. No migration needed - already V2 compliant
2. Consider adding Pydantic models for `UserConfig` and configuration validation
3. Current dataclass approach for renderer data is fine (display-only, no validation needed)

## References

- `src/tunacode/core/state.py:256-299` - TypeAdapter usage
- `src/tunacode/types/pydantic_ai.py` - Type re-exports
- `src/tunacode/utils/parsing/tool_parser.py` - Manual parsing (appropriate)
- `src/tunacode/core/agents/agent_components/agent_config.py` - Agent construction
- Pydantic V2 Docs: https://docs.pydantic.dev/latest/
- TypeAdapter API: https://docs.pydantic.dev/latest/api/type_adapter
- Migration Guide: https://docs.pydantic.dev/latest/migration
