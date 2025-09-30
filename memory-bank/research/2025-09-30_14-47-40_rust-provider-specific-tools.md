# Research – Rust Provider-Specific Tool Support Implementation

**Date:** 2025-09-30_14-47-40
**Owner:** context-engineer
**Phase:** Research

## Goal
Research how to implement provider-specific tool support in Rust for tunacode, similar to the JavaScript pattern that handles API compatibility differences between providers like OpenRouter and chutes.

- Additional Search:
  - `grep -ri "wire_api" core/src/`
  - `grep -ri "model_family" core/src/`
  - `grep -ri "supports_" core/src/`

## Findings

### Relevant Files & Why They Matter:
- `core/src/openai_tools.rs` → Contains the complete tool definition system, OpenAiTool enum, and API-specific serialization functions
- `core/src/model_provider_info.rs` → Defines ModelProviderInfo struct with WireApi enum for provider configuration
- `core/src/chat_completions.rs` → Shows how tools are included in API requests with current filtering logic
- `core/src/client.rs` → Demonstrates provider routing between different wire APIs
- `core/src/model_family.rs` → Model family detection system for capability determination
- `protocol/src/models.rs` → Protocol definitions for tool-related types

## Key Patterns / Solutions Found

### 1. **Wire API Enum Pattern** (`core/src/model_provider_info.rs:31-40`)
```rust
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum WireApi {
    Responses,  // OpenAI Responses API
    Chat,       // Chat Completions API
}
```
- **Relevance**: Provides foundation for provider-specific protocol handling
- **Pattern**: Enum-based routing between different API endpoints

### 2. **Tool Filtering Logic** (`core/src/openai_tools.rs:302-328`)
```rust
pub(crate) fn create_tools_json_for_chat_completions_api(
    tools: &[OpenAiTool],
) -> crate::error::Result<Vec<serde_json::Value>> {
    let responses_api_tools_json = create_tools_json_for_responses_api(tools)?;
    let tools_json = responses_api_tools_json
        .into_iter()
        .filter_map(|mut tool| {
            if tool.get("type") != Some(&serde_json::Value::String("function".to_string())) {
                return None;  // Filter out non-function tools
            }
            // Transform for Chat Completions format
        })
        .collect::<Vec<serde_json::Value>>();
    Ok(tools_json)
}
```
- **Relevance**: Shows existing pattern for filtering tools based on API capabilities
- **Pattern**: Function-type filtering with format transformation

### 3. **Model Family-Based Capability Detection** (`core/src/model_family.rs`)
```rust
pub struct ModelFamily {
    pub uses_local_shell_tool: bool,
    pub apply_patch_tool_type: Option<ApplyPatchToolType>,
    pub supports_reasoning_summaries: bool,
    // ... other capability fields
}
```
- **Relevance**: Existing pattern for capability detection based on model rather than provider
- **Pattern**: Feature flags per model family for conditional feature inclusion

### 4. **Provider Configuration Structure** (`core/src/model_provider_info.rs:42-89`)
```rust
pub struct ModelProviderInfo {
    pub name: String,
    pub base_url: Option<String>,
    pub env_key: Option<String>,
    pub wire_api: WireApi,
    pub query_params: Option<HashMap<String, String>>,
    pub http_headers: Option<HashMap<String, String>>,
    // ... other configuration fields
}
```
- **Relevance**: Existing extensibility points for provider-specific configuration
- **Pattern**: Comprehensive configuration with optional fields for customization

### 5. **Graceful Degradation Pattern** (`core/src/client_common.rs`)
```rust
pub(crate) fn create_reasoning_param_for_request(
    model_family: &ModelFamily,
    effort: Option<ReasoningEffortConfig>,
    summary: ReasoningSummaryConfig,
) -> Option<Reasoning> {
    if !model_family.supports_reasoning_summaries {
        return None;  // Graceful fallback
    }
    // ... proceed with reasoning parameters
}
```
- **Relevance**: Shows pattern for handling unsupported features gracefully
- **Pattern**: Capability checks with Option returns for graceful degradation

## Knowledge Gaps

### Missing Provider-Specific Tool Support
1. **Tool Capability Field**: No field in ModelProviderInfo to indicate tool support level
2. **Provider-Specific Filtering**: Current filtering only works by tool type, not by provider capabilities
3. **Tool Configuration Per Provider**: No mechanism to enable/disable specific tools per provider

### Configuration Extension Points
1. **Provider Tool Configuration**: Need to add tool capability flags to ModelProviderInfo
2. **Tool Filtering Logic**: Need to extend create_tools_json functions to respect provider limitations
3. **Error Handling**: Need specific error messages for unsupported tool features

### Architecture Considerations
1. **Backward Compatibility**: Any changes must preserve existing functionality
2. **Configuration Granularity**: Balance between global and per-provider tool configuration
3. **Model vs Provider Logic**: Clarify when capabilities should be determined by model family vs provider

## Existing Extension Points

### 1. **ModelProviderInfo Extension**
Current struct has extensibility points that can be leveraged:
- `http_headers`: Provider-specific HTTP headers
- `env_http_headers`: Environment-based headers
- `query_params`: URL query parameters

**Potential Extension**: Add `supported_tools: Option<ToolSupportLevel>` field

### 2. **ToolsConfig Enhancement**
Current `ToolsConfig` in `openai_tools.rs:64-122` could be extended:
- Add provider awareness to tool selection logic
- Modify `get_openai_tools()` to respect provider limitations
- Create provider-specific tool variants

### 3. **Wire API Routing Enhancement**
Current routing in `client.rs:124-164` could be extended:
- Add tool capability check before API call
- Implement provider-specific request modification
- Add fallback logic for unsupported features

## Implementation Strategy Recommendations

### Phase 1: Add Provider Capability Detection
1. Extend `ModelProviderInfo` with tool support field
2. Add configuration parsing for provider tool capabilities
3. Update built-in provider definitions

### Phase 2: Implement Conditional Tool Logic
1. Modify `create_tools_json_for_chat_completions_api()` to check provider capabilities
2. Add tool filtering logic based on provider support
3. Implement graceful degradation patterns

### Phase 3: Provider-Specific Tool Adaptation
1. Add provider-specific tool parameter transformation
2. Implement alternative tool implementations where needed
3. Add comprehensive error handling and user messaging

## Architecture Strengths for Extension

1. **Clear Separation of Concerns**: Tool definition, serialization, and routing are well-separated
2. **Flexible Configuration**: Extensive provider configuration options already exist
3. **Model-Centric Approach**: Using model families for capability detection is more accurate than provider names
4. **Established Patterns**: Existing graceful degradation and error handling patterns can be extended

## Recommended Next Steps

1. **Prototype Provider Tool Field**: Add a simple boolean field to ModelProviderInfo to indicate tool support
2. **Extend Tool Filtering**: Modify existing filtering logic to respect provider limitations
3. **Test with chutes Provider**: Implement and test the changes with the problematic chutes provider
4. **Document Provider Capabilities**: Create clear documentation of which providers support which features

## References

- **Tool Definitions**: `core/src/openai_tools.rs:43-54` (OpenAiTool enum)
- **API Filtering**: `core/src/openai_tools.rs:302-328` (Chat Completions filtering)
- **Provider Config**: `core/src/model_provider_info.rs:42-89` (ModelProviderInfo struct)
- **Client Routing**: `core/src/client.rs:124-164` (Wire API routing)
- **Capability Detection**: `core/src/model_family.rs` (Model family capabilities)
- **Error Handling**: `core/src/client_common.rs` (Graceful degradation patterns)