# TunaCode Testing Philosophy

## Core Principles

Our testing approach balances thoroughness with development speed:

- **One test per key feature** - Focus on testing each important functionality once
- **Focused on core functionality without overengineering** - Avoid testing implementation details
- **Used mocking to isolate unit behavior** - Test units in isolation from external dependencies  
- **Covered both success and failure paths** - Ensure robustness by testing error scenarios
- **Quick to run (< 2 seconds total)** - Fast feedback loop for developers

## Test Organization

### Unit Tests (`tests/unit/`)
- Test individual components in isolation
- Mock external dependencies (agents, state managers, etc.)
- Focus on public API behavior, not implementation details
- Use `pytest.mark.asyncio` for async functions

### Characterization Tests (`tests/characterization/`)
- Capture existing behavior as golden master
- Provide safety net for refactoring
- More integration-focused than unit tests

### Integration Tests (`tests/integration/`)
- Test component interactions
- May use real dependencies where appropriate
- Test end-to-end workflows

## Writing Effective Tests

### Example: Testing RecursiveTaskExecutor

```python
@pytest.mark.asyncio
async def test_complex_task_triggers_decomposition(self, executor, mock_state_manager):
    """Test that complex tasks trigger decomposition into subtasks."""
    # 1. Mock only what's necessary
    async def mock_analyze(request):
        return TaskComplexityResult(
            is_complex=True,
            complexity_score=0.85,
            reasoning="Task requires multiple operations"
        )
    
    executor._analyze_task_complexity = mock_analyze
    
    # 2. Test the behavior, not the implementation
    success, result, error = await executor.execute_task("Complex task")
    
    # 3. Assert on outcomes
    assert success is True
    assert error is None
```

### Best Practices

1. **Test names should describe behavior**: `test_complex_task_triggers_decomposition` not `test_execute_task`
2. **Use fixtures for common setup**: Reduces duplication and improves maintainability
3. **Mock at the right level**: Mock external boundaries, not internal methods (unless necessary)
4. **Test edge cases**: Empty lists, None values, boundary conditions
5. **Keep tests independent**: Each test should run in isolation

## Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/unit/test_recursive_executor.py

# Run with coverage
make coverage

# Run only unit tests
pytest tests/unit/

# Run tests matching pattern
pytest -k "decomposition"
```

## Test Coverage Goals

- New features should have corresponding tests
- Aim for >80% coverage on critical paths
- Don't chase 100% coverage - focus on meaningful tests
- Coverage is a tool, not a target

## Continuous Integration

All tests run on every commit via CI/CD pipeline. Keep tests fast and reliable to maintain developer productivity.