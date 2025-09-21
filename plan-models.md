# Models Registry Pydantic Conversion Plan

## Phase 1: Characterization Tests (Red)

finished

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

   Status: completed

   - Replaced `@dataclass` with `pydantic.BaseModel` for: `ModelCapabilities`, `ModelCost`, `ModelLimits`, `ModelInfo`, `ProviderInfo`
   - Added validation:
     - `ModelCost`: non-negative for `input`, `output`, `cache`
     - `ModelLimits`: positive ints for `context`, `output`
   - Preserved methods/properties: `full_id`, `format_display()`, `format_limits()`, `matches_search()`
   - Backward-compatible field access (attribute-style), `extra="ignore"` to tolerate unknown fields

4. **Update Parsing Logic**

   Status: completed

   - Simplified `_parse_data()` to construct Pydantic models; basic normalization retained
   - Validation is enforced by models; inputs coerced where safe, invalids raise early
   - Fallback data validated on load

5. **Update Dependencies**

   Status: reviewed — no code changes required

   - Call sites use attribute access and type hints only; no `dataclasses.asdict` usage detected
   - Verified imports and usage in: `ui/completers.py`, `ui/input.py`, `ui/model_selector.py`, `cli/commands/implementations/model.py`
   - Integration behavior preserved

## Phase 3: Validation and Testing (Blue)

6. **Create Validation Tests**

   Status: completed

   - Added `tests/unit/utils/test_models_registry_validation.py`
   - Test Pydantic validation scenarios (invalid costs, negative/zero limits)
   - Test type coercion behavior for numeric fields
   - Backward compatibility covered by golden baseline tests

7. **Manual Confirmation**
   - Run existing test suite to ensure no regressions (spot-checked unit scope)
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

Notes

- Golden baseline test `tests/unit/utils/test_models_registry.py` still passes unchanged after conversion.
- Validation tests added in Phase 3 pass.
