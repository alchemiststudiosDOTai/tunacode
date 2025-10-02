# Research – Model Command Validation Error

**Date:** 2025-10-01 11:15:38 CDT
**Owner:** Claude Code Research Agent
**Phase:** Research
**Git Commit:** bbbf6fdc4be2da943d7f10c277a621a8feb78447

## Goal
Summarize all *existing knowledge* about the `/model` command validation error where ModelLimits rejects 0 values with "limits must be positive integers" error.

- Additional Search:
  - `grep -ri "limits must be positive integers" .claude/`

## Findings

- **src/tunacode/utils/models_registry.py:61-67** → Contains ModelLimits validator that rejects 0 values
- **src/tunacode/utils/models_registry.py:361** → Where ModelLimits is instantiated, triggering the validation error
- **src/tunacode/utils/models_registry.py:180** → Cache loading calls _parse_data which triggers validation
- **src/tunacode/cli/commands/implementations/model.py:66** → Entry point where _ensure_registry() loads cache
- **tests/unit/utils/test_models_registry_validation.py:48-52** → Test that expects 0 values to fail validation

## Key Patterns / Solutions Found

- **ModelLimits validator inconsistency**: The validator uses `iv <= 0` to reject 0 values, but ModelCost validator uses `v < 0` to allow 0 values
- **API data contains legitimate 0 values**: models.dev API includes models with context/output limits of 0 to represent unlimited/not applicable limits
- **Missing vs 0 values**: Missing limit fields are correctly converted to None, but explicit 0 values raise ValidationError
- **Cache file location**: `~/.tunacode/cache/models_cache.json` stores the problematic data
- **Graceful degradation**: The system has fallback models but fails entirely on validation error before reaching fallbacks

## Knowledge Gaps

- Which specific models in the API have 0 limits and whether this represents valid data or data quality issues
- Whether the validation should be changed to allow 0 values or if 0 values should be filtered out during parsing
- Impact on existing users who may have cached data with 0 values

## References

- **src/tunacode/utils/models_registry.py** → Core models registry with validation logic
- **src/tunacode/cli/commands/implementations/model.py** → Model command implementation
- **tests/unit/utils/test_models_registry_validation.py** → Validation tests showing expected behavior
- **GitHub Permalink**: https://github.com/alchemiststudiosDOTai/tunacode/blob/bbbf6fdc4be2da943d7f10c277a621a8feb78447/src/tunacode/utils/models_registry.py#L61
- **GitHub Permalink**: https://github.com/alchemiststudiosDOTai/tunacode/blob/bbbf6fdc4be2da943d7f10c277a621a8feb78447/tests/unit/utils/test_models_registry_validation.py#L48
