# Phased Plan: Improving Test Quality for test_input_handling.py

## Overview
This document outlines a comprehensive plan to improve the test quality of the REPL input handling tests, addressing issues with timing dependencies, implementation-focused testing, and complex mocking.

## Phase 1: Refactor Existing Test to Follow Best Practices

### 1.1 Extract Common Test Fixtures
- Create a `conftest.py` file for REPL tests with common fixtures
- Define fixtures for:
  - `mock_state_manager`: Properly configured StateManager mock
  - `mock_agent`: Agent instance with MCP context
  - `mock_ui_methods`: Collection of UI method mocks

### 1.2 Remove Timing Dependencies
- Replace `asyncio.sleep(0.01)` with proper task synchronization
- Use `asyncio.Event` or `asyncio.Queue` to coordinate between input and processing
- Ensure tests are deterministic and not timing-sensitive

### 1.3 Test Behavior, Not Implementation
- Instead of counting mock calls, verify actual behavior:
  - Track which inputs were processed
  - Verify the order of processing
  - Check that empty strings are skipped
  - Confirm whitespace-only strings are processed

## Phase 2: Split Into Focused Tests

### 2.1 Create Separate Test Functions
Split the parametrized test into specific scenarios:
- `test_repl_skips_empty_strings()`: Verify empty strings are ignored
- `test_repl_processes_whitespace_strings()`: Verify whitespace is processed
- `test_repl_processes_valid_inputs_in_order()`: Verify processing order
- `test_repl_exits_on_exit_command()`: Verify exit behavior

### 2.2 Add Edge Case Tests
- `test_repl_handles_concurrent_requests()`: Multiple rapid inputs
- `test_repl_handles_task_already_running()`: Input while busy
- `test_repl_handles_special_characters()`: Unicode, newlines, etc.

## Phase 3: Improve Test Structure

### 3.1 Use Async Context Managers
- Create helper context managers for common setup/teardown
- Example: `async with mock_repl_session() as session:`

### 3.2 Add Integration Tests
- Create tests that verify actual REPL behavior without heavy mocking
- Use in-memory implementations where possible
- Test the actual flow from input to output

### 3.3 Improve Test Documentation
- Add docstrings explaining what each test verifies
- Include examples of expected behavior
- Document any non-obvious test setup

## Phase 4: Establish Testing Patterns

### 4.1 Create Test Helpers
- `create_repl_session()`: Factory for test sessions
- `simulate_user_input()`: Helper for simulating input sequences
- `assert_processed_inputs()`: Helper for verifying processing

### 4.2 Document Best Practices
- Create `tests/README.md` with testing guidelines
- Include examples of good vs bad test patterns
- Document how to test async code properly

## Implementation Order

1. **Start with Phase 1.2**: Fix timing issues (most critical)
2. **Then Phase 1.3**: Refactor to test behavior
3. **Then Phase 1.1**: Extract fixtures for reusability
4. **Then Phase 2**: Split and add new tests
5. **Finally Phase 3-4**: Improve structure and establish patterns

## Example of Improved Test

```python
@pytest.mark.asyncio
async def test_repl_processes_non_empty_inputs():
    """Test that REPL processes all non-empty inputs including whitespace."""
    
    # Setup
    processed_inputs = []
    input_queue = asyncio.Queue()
    
    # Add test inputs
    for inp in ["", "foo", "   ", "bar", "exit"]:
        await input_queue.put(inp)
    
    async def track_processing(text, state_manager, **kwargs):
        processed_inputs.append(text)
        state_manager.session.current_task = None
    
    async with mock_repl_session() as session:
        session.mock_process_request.side_effect = track_processing
        session.mock_input.side_effect = input_queue.get
        
        await run_repl_until_exit(session)
        
        # Verify behavior - empty strings skipped, others processed
        assert processed_inputs == ["foo", "   ", "bar"]
```

## Benefits of This Approach

1. **No timing dependencies**: Tests are deterministic
2. **Behavior-focused**: Tests verify what happens, not how
3. **Clear and readable**: Easy to understand test intent
4. **Reusable components**: Fixtures and helpers reduce duplication
5. **Maintainable**: Changes to implementation won't break tests

## Current Issues Addressed

1. **Timing dependency on `asyncio.sleep(0.01)`**: Replaced with proper synchronization
2. **Complex mocking setup**: Extracted to reusable fixtures
3. **Implementation-focused testing**: Changed to behavior verification
4. **Brittle test structure**: Made more resilient to changes

## Success Criteria

- All tests pass consistently without timing issues
- Tests clearly express their intent
- New developers can easily understand and modify tests
- Tests serve as documentation of expected behavior
- Test failures provide clear indication of what broke