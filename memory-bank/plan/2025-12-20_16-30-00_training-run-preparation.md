---
title: "Training Run Preparation - Plan"
phase: Plan
date: "2025-12-20T16:30:00"
owner: "agent"
parent_research: "memory-bank/research/2025-12-20_tunacode-codebase-overview.md"
git_commit_at_plan: "6da52f2"
tags: [plan, training, unsloth, fine-tuning, coding]
---

## Goal

- Prepare and validate the training environment for running Unsloth fine-tuning on `data/training.jsonl` (1000 examples, ~9.7MB).

### Non-goals

- Actually executing the full training run (GPU-dependent)
- Deployment or model serving
- Adding new training scenarios

## Scope & Assumptions

### In Scope

- Validate dataset format and integrity
- Verify config file paths match actual data location
- Create a dry-run script to validate the pipeline end-to-end without GPU
- Document the exact training command

### Out of Scope

- GPU/CUDA setup (user environment)
- Unsloth installation (separate environment per docs)
- Model upload to HuggingFace Hub

### Assumptions

- User has a separate Python environment with Unsloth installed
- User has GPU access for actual training
- Dataset at `data/training.jsonl` is the target file

## Deliverables

1. **Config path fix** - Update `config.py` default dataset path from `data/training_data.jsonl` to `data/training.jsonl`
2. **Validation script** - `scripts/validate_training.py` to check dataset integrity without GPU
3. **Training command cheatsheet** - Quick reference for running training

## Readiness

### Preconditions

- [x] Dataset exists: `data/training.jsonl` (confirmed: 9.7MB)
- [x] Training module complete: `src/tunacode/training/` (config, train, schema, scenarios)
- [x] ShareGPT format documented in research

### Missing

- Config default path points to wrong filename (`training_data.jsonl` vs `training.jsonl`)

## Milestones

- **M1**: Fix config path mismatch
- **M2**: Create validation script
- **M3**: Document training commands

## Work Breakdown (Tasks)

| ID | Summary | Owner | Deps | Milestone | Files |
|----|---------|-------|------|-----------|-------|
| T1 | Fix default dataset_path in TrainingConfig | agent | - | M1 | `src/tunacode/training/config.py` |
| T2 | Create validate_training.py script | agent | T1 | M2 | `scripts/validate_training.py` |
| T3 | Add training commands to JOURNAL.md | agent | T2 | M3 | `memory-bank/execute/JOURNAL.md` |

### Task Details

#### T1: Fix default dataset_path in TrainingConfig
- **Change**: `data/training_data.jsonl` -> `data/training.jsonl`
- **File**: `src/tunacode/training/config.py:76`
- **Acceptance**: Config default matches actual file location

#### T2: Create validate_training.py script
- **Purpose**: Validate dataset without requiring GPU/Unsloth
- **Checks**:
  - Dataset file exists and is valid JSONL
  - All records have required fields (`conversations`, `system`, `tools`)
  - Conversation structure valid (from/value pairs)
  - Report stats (total examples, avg conversation length)
- **File**: `scripts/validate_training.py`
- **Acceptance**: Script runs successfully on `data/training.jsonl`

#### T3: Document training commands
- **Location**: `memory-bank/execute/JOURNAL.md`
- **Content**:
  - Full training command with recommended settings
  - Fast iteration command for testing
  - Small GPU command for limited VRAM
- **Acceptance**: Commands are copy-paste ready

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Dataset format drift | Validation script catches schema issues early |
| Unsloth API changes | Pin version in training env, document tested version |

## Test Strategy

- T2 includes validation script that serves as the test for T1/T2
- No new unit tests required (validation script is the test)

## References

- Research: `memory-bank/research/2025-12-20_tunacode-codebase-overview.md`
- Training module: `src/tunacode/training/`
- Dataset: `data/training.jsonl`
- Unsloth docs: See `train.py:16-18` for install command

## Final Gate

- **Plan path**: `memory-bank/plan/2025-12-20_16-30-00_training-run-preparation.md`
- **Milestone count**: 3
- **Task count**: 3
- **Ready for coding**: Yes

**Next command**: `/context-engineer:execute "memory-bank/plan/2025-12-20_16-30-00_training-run-preparation.md"`
