---
title: "Small Model RL Training Part 1: Environment & Rubrics - Plan"
phase: Plan
date: "2025-12-19_15-31-00"
owner: "Agent"
parent_research: "memory-bank/research/2025-12-19_small-model-rl-training-plan.md"
git_commit_at_plan: "226445c"
tags: [plan, rl-training, verifiers, environment, rubrics, coding]
---

## Goal

Create the verifiers environment package with reward rubrics for training a small model on tunacode's search tool workflows.

**Non-goals:**
- Training configuration files
- Model training execution
- Tunacode integration code

## Scope & Assumptions

**In Scope:**
- Verifiers environment package structure
- Task schema dataclass
- Three rubric implementations (ToolSequence, ToolArgs, TaskCompletion)
- Composite rubric combining all three
- Dataset generation script
- Seed dataset (100 examples)

**Out of Scope:**
- Training configs (Part 2)
- Integration code (Part 2)
- Large-scale dataset curation

**Assumptions:**
- prime-rl is installed at `/root/tunacode/prime-rl/`
- verifiers library available (`uv pip install verifiers`)

## Deliverables

| # | Deliverable | Location |
|---|-------------|----------|
| D1 | Environment package | `prime-rl/envs/tunacode_search/` |
| D2 | Task schema | `prime-rl/envs/tunacode_search/schema.py` |
| D3 | Rubric implementations | `prime-rl/envs/tunacode_search/rubrics.py` |
| D4 | Dataset generation script | `scripts/generate_search_dataset.py` |
| D5 | Seed dataset | `data/tunacode_search_sft.jsonl` |

## Readiness

**Preconditions:**
- [x] prime-rl cloned to `/root/tunacode/prime-rl/`
- [ ] verifiers library installed

## Milestones

| Milestone | Description | Exit Criteria |
|-----------|-------------|---------------|
| M1 | Skeleton & architecture | Package imports, schema validates, env instantiates |
| M2 | Core logic & data flow | Rubrics score correctly, dataset script outputs JSONL |

## Work Breakdown (Tasks)

### M1: Skeleton & Architecture

| ID | Task | Est | Deps | Files |
|----|------|-----|------|-------|
| T1.1 | Create environment package directory structure | S | - | `prime-rl/envs/tunacode_search/__init__.py`, `environment.py`, `rubrics.py` |
| T1.2 | Define task schema dataclass | S | T1.1 | `prime-rl/envs/tunacode_search/schema.py` |
| T1.3 | Implement base environment class skeleton | S | T1.2 | `prime-rl/envs/tunacode_search/environment.py` |

**T1.1 Acceptance:** `from tunacode_search import CodeSearchEnvironment` imports without error
**T1.2 Acceptance:** `SearchTask` dataclass validates sample input
**T1.3 Acceptance:** Environment instantiates and `get_dataset()` returns empty list

---

### M2: Core Logic & Data Flow

| ID | Task | Est | Deps | Files |
|----|------|-----|------|-------|
| T2.1 | Implement ToolSequenceRubric | M | T1.3 | `prime-rl/envs/tunacode_search/rubrics.py` |
| T2.2 | Implement ToolArgsRubric | M | T1.3 | `prime-rl/envs/tunacode_search/rubrics.py` |
| T2.3 | Implement TaskCompletionRubric | M | T1.3 | `prime-rl/envs/tunacode_search/rubrics.py` |
| T2.4 | Create CompositeRubric combining all three | S | T2.1-T2.3 | `prime-rl/envs/tunacode_search/rubrics.py` |
| T2.5 | Implement dataset generation script | M | T1.2 | `scripts/generate_search_dataset.py` |
| T2.6 | Generate seed dataset (100 examples) | S | T2.5 | `data/tunacode_search_sft.jsonl` |

**T2.1 Acceptance:** Rubric returns 1.0 for correct GLOB->GREP->READ sequence
**T2.2 Acceptance:** Rubric returns 1.0 for valid JSON tool args, 0.0 for invalid
**T2.3 Acceptance:** Rubric returns 1.0 when expected files found in response
**T2.4 Acceptance:** Composite returns weighted average of component scores
**T2.5 Acceptance:** Script runs and outputs valid JSONL
**T2.6 Acceptance:** 100 examples in JSONL, all parseable

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| verifiers API changes | Low | Pin version in pyproject.toml |
| Tool schema mismatch | Medium | Validate against tunacode's actual pydantic schemas |

## Test Strategy

| Task | Test |
|------|------|
| T2.1-T2.4 | `test_rubrics.py::test_composite_rubric_weights` |
| T2.5 | `test_dataset_generation.py::test_output_format` |

## References

**Research Document:**
- Part 2.1: Tool interfaces (glob, grep, read_file schemas)
- Part 2.2: Search funnel pattern (GLOB->GREP->READ)
- Part 3.1: Environment creation template
- Part 3.2: Dataset format

**Key Code References:**
- `tunacode/src/tunacode/tools/glob.py:46-57` - Glob tool schema
- `tunacode/src/tunacode/tools/grep.py:419-432` - Grep tool schema
- `tunacode/src/tunacode/tools/read_file.py:17-23` - Read file schema

## Final Gate

| Check | Status |
|-------|--------|
| Plan file written | memory-bank/plan/2025-12-19_15-31-00_rl-training-part1-env-rubrics.md |
| Milestone count | 2 |
| Tasks ready for coding | 9 |

**Next command:** `/ce:ex "memory-bank/plan/2025-12-19_15-31-00_rl-training-part1-env-rubrics.md"`
