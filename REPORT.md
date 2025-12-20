# Tunacode Unsloth Fine-Tuning Report

## Summary
- Goal: fine-tune a small LLM to call tunacode tools using JSON tool-call format.
- Status: end-to-end pipeline exists (schema, tool extraction, synthetic data, training script).
- Baseline: 100 synthetic conversations, 1 epoch, Qwen3-0.6B, loss 3.85 -> 1.66.
- Critical behaviors: disable Qwen3 thinking for tool calls and keep system prompt aligned with training.

## Current Pipeline (Repo Map)
- Data schema: `src/tunacode/training/schema.py` defines ShareGPT messages, tool definitions, and JSONL helpers.
- Tool extraction: `src/tunacode/training/tool_extractor.py` converts tool signatures to JSON Schema.
- Scenarios: `src/tunacode/training/scenarios.py` provides 19 synthetic scenarios covering core tools.
- Dataset generation: `src/tunacode/training/dataset_generator.py` builds ShareGPT JSONL.
- Training: `src/tunacode/training/train.py` handles Unsloth SFT + QLoRA and adapter save.
- Config: `src/tunacode/training/config.py` provides default and small-GPU presets.

## Tool Registry (Training Scope)
Extracted in `src/tunacode/training/tool_extractor.py`:
- `read_file`: read file contents (with optional offset/limit).
- `grep`: search file contents by pattern.
- `glob`: find files by pattern.
- `list_dir`: list directory contents.
- `bash`: run shell commands.
- `write_file`: create new files.
- `update_file`: modify existing files.
- `web_fetch`: fetch external documentation.

Not currently in training registry:
- Todo tools (`todowrite`, `todoread`, `todoclear`) defined in `src/tunacode/tools/todo.py`.
- `research_codebase` is referenced in prompts but not extracted for training.

## Data Map (Tunacode Sources)
Available now:
- Tool definitions from decorators in `src/tunacode/tools/` via `tool_extractor.py`.
- Canonical tool usage examples in `src/tunacode/prompts/sections/examples.xml`.
- Tool usage rules and constraints in `src/tunacode/prompts/sections/tool_use.xml`.
- Per-tool prompts in `src/tunacode/tools/prompts/*.xml`.
- Synthetic scenario library in `src/tunacode/training/scenarios.py`.

Missing or planned:
- Real conversation traces with tool calls (instrument `src/tunacode/core/agents/agent_components/node_processor.py`).
- Parallel tool-call examples (batched read-only tools).
- System prompt alignment with the full tunacode tool policy.
- Dataset coverage for todo tools or explicit decision to exclude them.

## Training Data Format (ShareGPT + Tool Calls)
Format encoded in `src/tunacode/training/schema.py`:
```json
{
  "conversations": [
    {"from": "human", "value": "Read README.md"},
    {"from": "function_call", "value": "{\"name\": \"read_file\", \"arguments\": {\"filepath\": \"README.md\"}}"},
    {"from": "observation", "value": "<file>...</file>"},
    {"from": "gpt", "value": "Summary of README.md"}
  ],
  "system": "System prompt (optional)",
  "tools": "[{... JSON Schema ...}]"
}
```

Training formatting behavior in `src/tunacode/training/train.py`:
- `function_call` values are wrapped in `<tool_call>...</tool_call>`.
- `observation` values are wrapped in `<tool_response>...</tool_response>`.
- `tools` field is stored in the dataset but not injected into the prompt today.

## Baseline Training Run (From Journal)
- Model: `unsloth/Qwen3-0.6B`
- Dataset: 100 synthetic conversations
- Epochs: 1
- Effective batch: 8 (batch size 2 x gradient accumulation 4)
- Steps: 13
- Time: 38 seconds
- Loss: 3.85 -> 1.66
- Output: `output/lora_adapter/`

## Repro Commands (Current)
```bash
# Generate training data
uv run python scripts/generate_training_data.py --count 100 --output data/training.jsonl

# Train (separate venv recommended to avoid dependency conflicts)
cd /home/tuna/tunacode
source training_env/.venv/bin/activate
PYTHONPATH=src python -m tunacode.training.train \
  --dataset data/training.jsonl \
  --output ./output \
  --model unsloth/Qwen3-0.6B \
  --epochs 1 \
  --batch-size 2 \
  --max-seq-length 1024
```

Notes:
- `TrainingConfig.dataset_path` defaults to `data/training_data.jsonl` (different from `data/training.jsonl`).
- `SYSTEM_PROMPT_TEMPLATE` exists in `src/tunacode/training/train.py` but is not used today.
- Qwen3 thinking mode should be disabled at inference: `enable_thinking=False`.

## External Guidance (from recent references)
- OpenAI cookbook recommends improving function definitions and prompts before fine-tuning, then using a strong model to generate a "golden" synthetic dataset and evaluating baseline vs tuned results. It highlights that real-world evaluation is preferred for production.
- Function calling reliability drops as tool count and function complexity grow, so keep tool descriptions distinct and unambiguous.
- Evaluation is typically measured as tool selection accuracy plus argument correctness; multi-turn tool use is a separate stress case.

References:
- https://cookbook.openai.com/examples/fine_tuning_for_function_calling
- https://cookbook.openai.com/examples/how_to_call_functions_with_chat_models
- https://gorilla.cs.berkeley.edu/leaderboard.html (BFCL benchmark)
- https://openreview.net/pdf?id=2GmDdhBdDk (BFCL paper)

## Improvement Plan
### 1) Data Scale and Variety
- Grow dataset to 1k-5k conversations with balanced tool coverage.
- Add multi-tool workflows (search funnel: `glob` -> `grep` -> `read_file`).
- Include parallel read-only tool calls in a single turn.
- Expand error recovery: bad path, invalid args, permission errors, timeouts.
- Inject tool policy constraints from `src/tunacode/prompts/sections/tool_use.xml`.
- Add a "golden set" created by a stronger model and compare against real traces.

### 2) Prompt Alignment
- Use the same system prompt at training and inference.
- Embed tool definitions into the system prompt or modify training to use the `tools` field.
- Enforce rules like "no absolute paths" and "avoid bash for search" in data.

### 3) Tool Coverage and Scope
- Decide whether todo tools and `research_codebase` are in-scope.
- If in-scope, add tool extraction, scenarios, and prompt examples.
- Keep tool list consistent across training data, prompts, and runtime registry.

### 4) Model and Hyperparameters
- Compare `Qwen3-0.6B`, `Qwen3-4B`, and FunctionGemma for tool-call accuracy.
- Try 3-5 epochs once dataset grows; tune LoRA rank (r=8,16) and seq length.
- Evaluate merged vs adapter-only for deployment compatibility (GGUF later).

### 5) Evaluation and QA
- Build a held-out test set with labeled tool calls and expected arguments.
- Measure exact tool selection accuracy, argument accuracy, and recovery rate.
- Add regression tests for formatting and ShareGPT validation.
- Track multi-turn and parallel tool-call accuracy separately (BFCL-style).

## Risks and Mitigations
- Dependency conflicts: keep training in `training_env/.venv` with uv.
- Synthetic overfitting: mix real traces with templated data.
- Prompt mismatch: lock system prompt and tools schema for training and inference.
- Tool drift: update extractor and scenarios when tools change.

## Next Actions (Concrete)
1. Decide tool scope (include todo and research or keep the 8-core list).
2. Update training to inject tool definitions into the prompt (use `tools` field).
3. Expand scenarios to cover parallel reads and error recovery variants.
4. Instrument runtime to capture real tool-call traces for dataset growth.
5. Create a small evaluation set and scoring script to track progress.
