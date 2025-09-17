# Backward Compatibility During Major Refactoring

## Pattern
When performing significant architectural refactoring, maintain API compatibility through:
1. **Compatibility shims**: Keep old APIs intact by delegating to new implementations
2. **Gradual migration**: Allow gradual adoption without breaking existing integrations
3. **Export alignment**: Ensure all necessary exports are available at expected locations

## Example from Main Agent Refactor
- New internal structure with component-based architecture
- Old `process_request` function maintained as compatibility shim
- CLI imports adjusted to work with new structure
- Tool recovery patches aligned with new agent exports

## Benefits
- Zero breaking changes for external users
- Internal improvements can continue
- Smooth transition period for migration
