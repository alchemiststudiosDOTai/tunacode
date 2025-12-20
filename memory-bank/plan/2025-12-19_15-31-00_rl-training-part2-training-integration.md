---
title: "Small Model RL Training Part 2: Training & Integration - Plan"
phase: Plan
date: "2025-12-19_15-31-00"
owner: "Agent"
parent_research: "memory-bank/research/2025-12-19_small-model-rl-training-plan.md"
parent_plan: "memory-bank/plan/2025-12-19_15-31-00_rl-training-part1-env-rubrics.md"
git_commit_at_plan: "226445c"
tags: [plan, rl-training, training-config, integration, coding]
---

## Goal

Create training configuration files and integrate the trained model into tunacode.

**Non-goals:**
- Environment/rubric implementation (Part 1)
- Hyperparameter optimization
- Production deployment infrastructure

## Scope & Assumptions

**In Scope:**
- SFT training config file
- RL training config file
- Environment wiring to prime-rl
- Training validation (config runs)
- Local provider config in tunacode
- vLLM serve script

**Out of Scope:**
- Environment package (Part 1 - must be complete)
- Dataset generation (Part 1 - must be complete)
- Full training runs (manual step)

**Assumptions:**
- Part 1 complete (environment + rubrics + dataset exist)
- prime-rl installed at `/root/tunacode/prime-rl/`
- Single GPU with 16GB+ VRAM
- Qwen3-0.6B accessible via HuggingFace

## Deliverables

| # | Deliverable | Location |
|---|-------------|----------|
| D1 | SFT training config | `prime-rl/configs/tunacode/sft.toml` |
| D2 | RL training config | `prime-rl/configs/tunacode/rl.toml` |
| D3 | Environment pyproject.toml | `prime-rl/envs/tunacode_search/pyproject.toml` |
| D4 | Local provider config | `src/tunacode/core/agents/agent_components/agent_config.py` |
| D5 | vLLM serve script | `scripts/serve_local_model.sh` |

## Readiness

**Preconditions:**
- [ ] Part 1 complete (environment, rubrics, dataset)
- [ ] GPU with 16GB+ VRAM available
- [ ] HuggingFace token configured

## Milestones

| Milestone | Description | Exit Criteria |
|-----------|-------------|---------------|
| M3 | Feature completion | Configs run without errors, training starts |
| M4 | Integration | Local model serves, tunacode connects |

## Work Breakdown (Tasks)

### M3: Feature Completion & Refinement

| ID | Task | Est | Deps | Files |
|----|------|-----|------|-------|
| T3.1 | Create SFT training config | S | Part1 | `prime-rl/configs/tunacode/sft.toml` |
| T3.2 | Create RL training config | S | Part1 | `prime-rl/configs/tunacode/rl.toml` |
| T3.3 | Wire environment into prime-rl entry point | S | Part1 | `prime-rl/envs/tunacode_search/pyproject.toml` |
| T3.4 | Validate SFT config runs | S | T3.1, T3.3 | - |
| T3.5 | Validate RL config runs | S | T3.2, T3.3 | - |

**T3.1 Acceptance:** `uv run sft @ configs/tunacode/sft.toml --max-steps 1` runs
**T3.2 Acceptance:** Config TOML parses without error
**T3.3 Acceptance:** `prime env install ./envs/tunacode_search` succeeds
**T3.4 Acceptance:** SFT training starts, logs first loss value
**T3.5 Acceptance:** RL training starts, logs first reward

---

### M4: Integration

| ID | Task | Est | Deps | Files |
|----|------|-----|------|-------|
| T4.1 | Add local provider config to tunacode | S | - | `src/tunacode/core/agents/agent_components/agent_config.py` |
| T4.2 | Create vLLM serve script | S | - | `scripts/serve_local_model.sh` |
| T4.3 | Test tool execution with local model | M | T4.1, T4.2 | - |

**T4.1 Acceptance:** `PROVIDER_CONFIG["local"]` exists with base_url
**T4.2 Acceptance:** Script starts vLLM server with tool-call parser
**T4.3 Acceptance:** Tunacode connects to local model, executes one search query

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Qwen3-0.6B tool format incompatible | High | Use Hermes parser, fallback to regex extraction |
| GPU OOM on single-GPU mode | Medium | Enable activation checkpointing, reduce batch size to 8 |

## Test Strategy

| Task | Test |
|------|------|
| T4.3 | Manual end-to-end test documented in README |

## References

**Research Document:**
- Part 1.4: Small model configuration
- Part 1.5: Hardware requirements / single GPU command
- Part 3.3: SFT warmup config
- Part 3.4: RL training config
- Part 3.6: Integration steps

**Key Code References:**
- `prime-rl/src/prime_rl/rl.py` - Main entry point
- `tunacode/src/tunacode/core/agents/agent_components/agent_config.py:252-269` - Provider config

## Final Gate

| Check | Status |
|-------|--------|
| Plan file written | memory-bank/plan/2025-12-19_15-31-00_rl-training-part2-training-integration.md |
| Milestone count | 2 |
| Tasks ready for coding | 8 |
| Dependency on Part 1 | Documented |

**Next command:** `/ce:ex "memory-bank/plan/2025-12-19_15-31-00_rl-training-part2-training-integration.md"`
