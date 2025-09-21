# Models Registry Pydantic Conversion Plan

## Phase 1: Characterization Tests (Red)

1. **Create Golden Baseline Tests**
   - Create `tests/unit/utils/test_models_registry.py`
   - Test current dataclass behavior and field access patterns
   - Test the complex `_parse_data()` method with various inputs
   - Test all method signatures (`format_display()`, `matches_search()`, etc.)
   - Test fallback data loading and parsing

2. **Integration Characterization**
   - Document current error handling behavior (silent fallbacks)
   - Test field access patterns used by dependent components
   - Verify current serialization/deserialization behavior

## Phase 2: Pydantic Conversion (Green)

3. **Convert Data Classes to Pydantic Models**
   - Replace `@dataclass` with `BaseModel` for all 5 classes
   - Add proper validation rules (non-negative costs, positive limits)
   - Preserve all existing methods and properties
   - Ensure backward compatibility for field access

4. **Update Parsing Logic**
   - Simplify `_parse_data()` method using Pydantic validation
   - Remove manual type checking code
   - Add proper error handling for validation failures
   - Validate hardcoded fallback data

5. **Update Dependencies**
   - Update 4 dependent files (`completers.py`, `input.py`, `model_selector.py`, `model.py`)
   - Ensure all imports and field access patterns work with Pydantic models
   - Test integration points still function correctly

## Phase 3: Validation and Testing (Blue)

6. **Create Validation Tests**
   - Test Pydantic validation scenarios (invalid costs, negative limits)
   - Test error handling with malformed data
   - Test type coercion behavior
   - Test backward compatibility

7. **Manual Confirmation**
   - Run existing test suite to ensure no regressions
   - Test CLI model selection functionality manually
   - Verify UI components still work correctly
   - Check performance impact on model loading

---

### Success Criteria

- All existing tests pass
- New validation tests pass
- Field access patterns preserved
- Method signatures unchanged
- Parsing logic simplified from 66 lines to ~20 lines
- Proper validation errors raised for invalid data
- Performance impact < 10%
