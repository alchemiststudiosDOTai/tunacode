# ReAct Shim Memory Anchor

## UUID: react-shim-001

### Component Classification
- **Type**: Coordination layer
- **Pattern**: ReAct (Reasoning + Acting)
- **Integration**: Non-blocking shim

### Key Implementation Details
- **Location**: `src/tunacode/core/agents/main.py:220-404`
- **Configuration**: `src/tunacode/core/agents/agent_components/agent_config.py:56-103`
- **Cache Strategy**: Module-level with version hash invalidation
- **Failure Mode**: Graceful degradation to base behavior

### Integration Points
1. **process_request()**: Main orchestration
2. **get_react_agents()**: Agent provisioning
3. **StateFacade**: State management
4. **UI integration**: Thought logging when enabled

### Configuration Constants
- `REACT_MAX_STEPS`: 4
- `UNPRODUCTIVE_LIMIT`: 3
- Cache version hash includes: plan_mode, max_retries, react_prompt_version

### Behavioral Characteristics
- Provides step-by-step guidance messages
- Respects iteration limits and completion signals
- Automatic disable on agent failures
- Minimal performance overhead when disabled
