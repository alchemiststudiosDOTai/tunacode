# Characterization Tests

This directory contains the characterization tests for the TunaCode project. These tests capture the current behavior of the codebase and serve as a golden master set.

## Current Status

These tests are now considered the primary test suite for the project. They are stable and are not expected to change until further development work is undertaken. They provide a safety net to ensure that refactoring and other changes do not alter existing behavior unintentionally.

The old test files in the parent `tests/` directory are now considered legacy and are not actively maintained.

## Running the Tests

To run the characterization tests, use the following command from the root of the project:

```bash
venv/bin/python -m pytest -q tests/characterization
```

This will execute all tests within the `tests/characterization` directory.

## Testing Philosophy

For our overall testing approach and best practices, see [TESTING_PHILOSOPHY.md](./TESTING_PHILOSOPHY.md).
