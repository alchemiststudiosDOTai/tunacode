---
title: "Rust Provider-Specific Tool Support – Plan"
phase: Plan
date: "2025-09-30_15-03-22"
owner: "context-engineer"
parent_research: "memory-bank/research/2025-09-30_14-47-40_rust-provider-specific-tools.md"
git_commit_at_plan: "8dffc5f"
tags: [plan, rust, provider-tools, tunacode]
---

## Goal
**Implement provider-specific tool support in tunacode's Rust codebase to enable selective tool enabling/disabling per provider, solving API compatibility issues with providers like chutes that don't support certain tools.**

**Non-goals**: Complete rewrite of tool system, breaking changes to existing provider integrations, provider-specific tool implementations.

## Scope & Assumptions

### In Scope
- Add `ToolSupportLevel` field to `ModelProviderInfo` struct
- Extend tool filtering logic to respect provider capabilities
- Implement graceful degradation for unsupported tools
- Update built-in provider configurations
- Add comprehensive error handling and user messaging

### Out of Scope
- Provider-specific tool parameter transformation
- Alternative tool implementations per provider
- Breaking changes to existing API contracts
- Dynamic tool discovery at runtime

### Assumptions & Constraints
- Existing tool filtering and WireAPI patterns remain intact
- Backward compatibility must be preserved for all current providers
- Configuration should be declarative and easily extensible
- Tool capabilities should be determined by provider, not model family

## Deliverables (DoD)

1. **Enhanced ModelProviderInfo struct** with `ToolSupportLevel` field and serialization support
2. **Provider-aware tool filtering logic** that checks provider capabilities before tool inclusion
3. **Updated provider configurations** for all built-in providers with accurate tool support flags
4. **Graceful degradation implementation** with clear error messages for unsupported tools
5. **Comprehensive test coverage** for provider-specific tool filtering scenarios
6. **Documentation updates** explaining the provider tool configuration system

## Readiness (DoR)

### Preconditions
- ✅ Research completed and validated for code freshness
- ✅ Core tool system patterns verified and functional
- ✅ Git repository state clean and ready for implementation

### Required Environment/Access
- Rust development environment with cargo
- Access to provider configuration files
- Test environment with multiple provider API endpoints

### Fixtures/Data
- Existing provider configurations in `core/src/model_provider_info.rs`
- Tool definitions in `core/src/openai_tools.rs`
- Test cases for tool filtering scenarios

## Milestones

### M1: Foundation & Architecture (Day 1)
- Define `ToolSupportLevel` enum with variants for different support levels
- Extend `ModelProviderInfo` struct with tool capability fields
- Add serialization/deserialization support for new fields
- Create foundation for provider capability detection

### M2: Tool Filtering Implementation (Day 2-3)
- Extend `create_tools_json_for_chat_completions_api()` with provider awareness
- Add provider capability checks to existing tool filtering logic
- Implement graceful degradation patterns for unsupported tools
- Add comprehensive error handling and user messaging

### M3: Configuration & Integration (Day 4)
- Update all built-in provider configurations with accurate tool support
- Integrate provider checks into tool selection workflow
- Add provider capability validation during configuration loading
- Test with real provider endpoints (especially chutes)

### M4: Testing & Hardening (Day 5)
- Comprehensive test suite for provider-specific tool filtering
- Integration tests with multiple provider configurations
- Error handling validation for edge cases
- Performance testing of tool filtering logic

### M5: Documentation & Polish (Day 6)
- Update documentation for provider tool configuration
- Add examples and usage patterns
- Code review and final polish
- Release preparation

## Work Breakdown (Tasks)

### T101: Define Tool Support Enum (M1)
**Summary**: Create `ToolSupportLevel` enum to represent different levels of tool support per provider
**Owner**: core-engineer
**Estimate**: 4 hours
**Dependencies**: None

**Acceptance Tests**:
- ✅ Enum compiles with all support variants (Full, Partial, None, Custom)
- ✅ Serialization/deserialization works correctly
- ✅ Default values preserve backward compatibility

**Files/Interfaces**:
- `core/src/model_provider_info.rs` - Add ToolSupportLevel enum
- `protocol/src/models.rs` - Add protocol definitions if needed

### T102: Extend ModelProviderInfo Struct (M1)
**Summary**: Add tool capability fields to ModelProviderInfo for provider-specific configuration
**Owner**: core-engineer
**Estimate**: 6 hours
**Dependencies**: T101

**Acceptance Tests**:
- ✅ New fields added without breaking existing functionality
- ✅ Default values maintain backward compatibility
- ✅ Configuration parsing works with extended struct
- ✅ Provider loading/unloading functions correctly

**Files/Interfaces**:
- `core/src/model_provider_info.rs` - Extend ModelProviderInfo struct
- `core/src/config.rs` - Update configuration parsing logic
- `core/src/config_profile.rs` - Update profile handling

### T103: Extend Tool Filtering Logic (M2)
**Summary**: Modify `create_tools_json_for_chat_completions_api()` to check provider capabilities
**Owner**: tools-engineer
**Estimate**: 8 hours
**Dependencies**: T101, T102

**Acceptance Tests**:
- ✅ Tools filtered based on provider support level
- ✅ Graceful degradation for unsupported tools
- ✅ Performance impact minimal (<5% overhead)
- ✅ Error messages clear and actionable

**Files/Interfaces**:
- `core/src/openai_tools.rs` - Extend tool filtering functions
- `core/src/chat_completions.rs` - Update tool integration point
- `core/src/client_common.rs` - Add provider capability checks

### T104: Update Provider Configurations (M3)
**Summary**: Configure all built-in providers with accurate tool support levels
**Owner**: config-engineer
**Estimate**: 6 hours
**Dependencies**: T101, T102

**Acceptance Tests**:
- ✅ All providers configured with correct tool support levels
- ✅ chutes provider configured with restricted tool support
- ✅ OpenRouter provider configured with full tool support
- ✅ Default configurations maintain backward compatibility

**Files/Interfaces**:
- `core/src/model_provider_info.rs` - Update built-in provider definitions
- `core/src/config.rs` - Update default configuration loading
- Configuration files for external providers if any

### T105: Integration Testing (M4)
**Summary**: Comprehensive test suite for provider-specific tool functionality
**Owner**: test-engineer
**Estimate**: 8 hours
**Dependencies**: T103, T104

**Acceptance Tests**:
- ✅ Unit tests for provider capability detection
- ✅ Integration tests with multiple providers
- ✅ End-to-end tests with chutes provider
- ✅ Performance benchmarks for tool filtering

**Files/Interfaces**:
- `core/tests/suite/provider_tool_filtering.rs` - New test file
- `core/tests/common/` - Test utilities and fixtures
- Existing test files to extend with provider scenarios

### T106: Documentation Updates (M5)
**Summary**: Update documentation to explain provider tool configuration system
**Owner**: docs-engineer
**Estimate**: 4 hours
**Dependencies**: T104, T105

**Acceptance Tests**:
- ✅ README updated with provider tool configuration examples
- ✅ API documentation updated for new fields
- ✅ Troubleshooting guide for tool support issues
- ✅ Migration guide for existing configurations

**Files/Interfaces**:
- `README.md` - Update overview and examples
- `config.md` - Update configuration documentation
- New documentation files for provider tool configuration

## Risks & Mitigations

### Risk 1: Breaking Changes to Existing Providers
**Impact**: High | **Likelihood**: Medium
**Mitigation**: Use default values that preserve current behavior, extensive backward compatibility testing
**Trigger**: Any failing tests for existing provider configurations

### Risk 2: Performance Impact on Tool Filtering
**Impact**: Medium | **Likelihood**: Low
**Mitigation**: Efficient capability checking with caching, performance benchmarks
**Trigger**: Tool filtering latency increases >10%

### Risk 3: Complex Provider Configuration Management
**Impact**: Medium | **Likelihood**: Medium
**Mitigation**: Clear configuration schema, validation during loading, comprehensive examples
**Trigger**: Configuration parsing errors or user confusion

### Risk 4: Inconsistent Tool Support Across Providers
**Impact**: Low | **Likelihood**: High
**Mitigation**: Clear documentation, standardized capability levels, graceful degradation
**Trigger**: User reports of unexpected tool behavior

## Test Strategy

**Primary Integration Test**: `test_provider_specific_tool_filtering()`
- **Scenario**: Test with chutes provider configured for limited tool support
- **Expected**: Tools filtered appropriately, graceful degradation for unsupported features
- **Coverage**: Provider capability detection, tool filtering logic, error handling

**No Additional Test Files**: Limit to ONE new integration test file to maintain focus

## References

- **Research Document**: `memory-bank/research/2025-09-30_14-47-40_rust-provider-specific-tools.md`
- **Tool System**: `core/src/openai_tools.rs:302-328` (filtering pattern)
- **Provider Config**: `core/src/model_provider_info.rs:42-89` (ModelProviderInfo struct)
- **WireAPI Pattern**: `core/src/model_provider_info.rs:31-40` (WireApi enum)
- **Graceful Degradation**: `core/src/client_common.rs` (Option return pattern)

## Agents

- **context-synthesis**: Validate research freshness and analyze current codebase patterns
- **codebase-analyzer**: Examine specific implementation patterns and integration points

## Final Gate

**Plan Path**: `memory-bank/plan/2025-09-30_15-03-22_rust-provider-specific-tools.md`
**Milestones**: 5 (M1-M5)
**Total Tasks**: 6 (T101-T106)
**Estimated Duration**: 6 days
**Next Command**: `/execute "memory-bank/plan/2025-09-30_15-03-22_rust-provider-specific-tools.md"`

**Success Criteria**:
- Provider-specific tool filtering implemented without breaking changes
- chutes provider compatibility issue resolved
- All existing providers maintain current functionality
- Comprehensive test coverage validates implementation