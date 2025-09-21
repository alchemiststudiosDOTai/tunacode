# Delta: Models Registry Pydantic Conversion (Phase 2)

- Date: 2025-09-21
- Component: `src/tunacode/utils/models_registry.py`
- Change Type: Internal type conversion + validation

Summary
- Converted dataclasses to Pydantic `BaseModel`:
  - `ModelCapabilities`, `ModelCost`, `ModelLimits`, `ModelInfo`, `ProviderInfo`
- Added validation:
  - `ModelCost`: non-negative `input|output|cache`
  - `ModelLimits`: positive integer `context|output`
- Kept public surface compatible:
  - Attribute access unchanged, methods (`full_id`, `format_display`, `format_limits`, `matches_search`) unchanged
  - `extra="ignore"` to tolerate unknown fields from API

Rationale
- Improve input validation and reduce manual parsing logic per plan-models.md Phase 2.
- Fail-fast on invalid data while preserving existing behavior for valid inputs.

Behavioral Impact
- No changes to expected outputs in golden tests; `tests/unit/utils/test_models_registry.py` passes unchanged.
- Invalid negative costs/limits will now raise validation errors during parse.

Follow-ups
- Add Phase 3 validation tests for malformed inputs and error paths.
