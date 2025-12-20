---
title: "Unsloth Fine-Tuning for Tool Calling - Plan"
phase: Plan
date: "2025-12-20_15-06-30"
owner: "agent"
parent_research: "memory-bank/research/2025-12-20_14-58-03_unsloth-finetuning-tools.md"
git_commit_at_plan: "3862f91"
tags: [plan, unsloth, finetuning, tool-calling, coding]
---

## Goal

- Build a training data pipeline and fine-tuning script to train a small LLM (qwen3-4b or FunctionGemma) on tunacode's tool-calling patterns using Unsloth/QLoRA.

**Non-goals:**
- Production deployment infrastructure
- Model serving/hosting
- Performance benchmarking at scale
- Integration with tunacode runtime (future work)

## Scope & Assumptions

**In Scope:**
- Training data generation from tunacode tool definitions
- ShareGPT-format dataset creation with tool calls
- Unsloth fine-tuning script with QLoRA
- Synthetic conversation generation for tool usage patterns

**Out of Scope:**
- Real conversation trace collection (requires runtime instrumentation)
- Model export to GGUF/other formats
- Inference integration with tunacode agent

**Assumptions:**
- CUDA-capable GPU available (or Colab/Kaggle)
- `unsloth/qwen3-4b` cached locally at `~/.cache/huggingface/hub/`
- Python 3.10+ with `uv` for environment management

## Deliverables

1. `src/tunacode/training/` - New module for fine-tuning pipeline
2. `src/tunacode/training/schema.py` - Pydantic models for dataset format
3. `src/tunacode/training/tool_extractor.py` - Extract tool definitions to JSON Schema
4. `src/tunacode/training/dataset_generator.py` - Generate synthetic training data
5. `src/tunacode/training/train.py` - Unsloth fine-tuning script
6. `scripts/generate_training_data.py` - CLI entry point for data generation

## Readiness

**Preconditions:**
- [x] Research complete on Unsloth/ShareGPT format
- [x] Tool definitions exist in `src/tunacode/tools/`
- [x] qwen3-4b model cached locally
- [ ] `unsloth` package installable (verify in .venv)

**Required packages:**
```
unsloth
trl
transformers
datasets
pydantic
```

## Milestones

### M1: Skeleton & Schema Setup
Set up training module structure and define data schemas.

### M2: Tool Extraction & Dataset Schema
Extract tunacode tool definitions into JSON Schema format compatible with training.

### M3: Synthetic Data Generation
Generate diverse tool-calling conversations using templates.

### M4: Fine-Tuning Script
Complete Unsloth training script with QLoRA configuration.

## Work Breakdown (Tasks)

### M1: Skeleton & Schema Setup

| ID | Task | Files | Acceptance |
|----|------|-------|------------|
| T1.1 | Create training module skeleton | `src/tunacode/training/__init__.py` | Module imports without error |
| T1.2 | Define ShareGPT pydantic models | `src/tunacode/training/schema.py` | `ShareGPTConversation` validates sample JSON |

### M2: Tool Extraction & Dataset Schema

| ID | Task | Files | Acceptance |
|----|------|-------|------------|
| T2.1 | Build tool signature extractor | `src/tunacode/training/tool_extractor.py` | Extracts all 7 core tools to JSON Schema |
| T2.2 | Create tool definition registry | `src/tunacode/training/tool_extractor.py` | Returns list of `ToolDefinition` objects |

### M3: Synthetic Data Generation

| ID | Task | Files | Acceptance |
|----|------|-------|------------|
| T3.1 | Build conversation template engine | `src/tunacode/training/dataset_generator.py` | Generates single valid ShareGPT conversation |
| T3.2 | Create tool usage scenario library | `src/tunacode/training/scenarios.py` | 10+ scenarios covering all tools |
| T3.3 | Implement multi-turn generator | `src/tunacode/training/dataset_generator.py` | Generates conversations with 2-4 tool calls |
| T3.4 | Add error/retry scenarios | `src/tunacode/training/dataset_generator.py` | Includes FileNotFoundError recovery |
| T3.5 | Build CLI for data generation | `scripts/generate_training_data.py` | `uv run python scripts/generate_training_data.py --count 100` works |

### M4: Fine-Tuning Script

| ID | Task | Files | Acceptance |
|----|------|-------|------------|
| T4.1 | Create training config dataclass | `src/tunacode/training/config.py` | `TrainingConfig` with all hyperparameters |
| T4.2 | Implement dataset loader | `src/tunacode/training/train.py` | Loads ShareGPT JSON into HuggingFace Dataset |
| T4.3 | Build Unsloth training loop | `src/tunacode/training/train.py` | Runs 1 epoch on 10 samples without OOM |
| T4.4 | Add checkpoint saving | `src/tunacode/training/train.py` | Saves LoRA adapter to `./output/` |

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Unsloth package conflicts with existing deps | Medium | Use separate venv or optional dependency group |
| VRAM OOM during training | Medium | Use gradient_accumulation_steps=8, reduce batch_size |
| qwen3-4b chat template mismatch | Low | Use `tokenizer.apply_chat_template()` with tool support |
| Synthetic data too repetitive | Medium | Add randomization to scenarios, vary phrasing |

## Test Strategy

- T1.2: Unit test for schema validation
- T2.1: Unit test extracting `read_file` tool signature
- T3.1: Integration test generating 1 conversation
- T4.3: Smoke test running 1 training step (can be skipped in CI without GPU)

## References

- Research doc: `memory-bank/research/2025-12-20_14-58-03_unsloth-finetuning-tools.md`
- Tool registration: `src/tunacode/core/agents/agent_components/agent_config.py:348-371`
- Tool decorators: `src/tunacode/tools/decorators.py`
- Unsloth ShareGPT: `from unsloth.chat_templates import standardize_sharegpt`

## Final Gate

| Metric | Value |
|--------|-------|
| Plan path | `memory-bank/plan/2025-12-20_15-06-30_unsloth-finetuning-tools.md` |
| Milestones | 4 |
| Tasks | 11 |
| Ready for coding | Yes |

**Next command:** `/context-engineer:execute "memory-bank/plan/2025-12-20_15-06-30_unsloth-finetuning-tools.md"`
