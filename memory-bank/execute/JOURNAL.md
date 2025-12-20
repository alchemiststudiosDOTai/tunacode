# Unsloth Fine-Tuning Journal

**Date**: 2025-12-20
**Branch**: `unsloth`
**Model**: `unsloth/Qwen3-0.6B`

---

## Objective

Fine-tune a small LLM to use tunacode's 8 core tools via JSON tool-calling format.

---

## What We Built

### Training Pipeline (M1-M4)

| Milestone | File | Purpose |
|-----------|------|---------|
| M1 | `schema.py` | ShareGPT Pydantic schemas for conversation format |
| M2 | `tool_extractor.py` | Extracts 8 tools to JSON Schema from decorators |
| M3 | `scenarios.py`, `dataset_generator.py` | 19 synthetic scenarios, CLI generator |
| M4 | `train.py`, `config.py` | TrainingConfig, Unsloth training loop, QLoRA |

### Tools Extracted

1. `read_file` - Read file contents
2. `write_file` - Write/create files
3. `edit_file` - Line-based edits
4. `bash` - Execute shell commands
5. `glob_files` - Pattern-based file search
6. `grep_search` - Content search with regex
7. `list_directory` - List directory contents
8. `web_search` - Web search queries

---

## Training Run

```
Model: unsloth/Qwen3-0.6B (606M params)
LoRA: 10M trainable params (1.67%)
Dataset: 100 synthetic conversations
Epochs: 1
Batch size: 2 x 4 gradient accumulation = 8 effective
Steps: 13
Time: 38 seconds
Loss: 3.85 -> 1.66
```

Output: `output/lora_adapter/`

---

## Key Learnings

### 1. Qwen3 Thinking Mode Must Be Disabled

Qwen3 models have built-in "thinking mode" that outputs `<think>...</think>` tags before responding. This interferes with tool-calling.

**Solution**: Pass `enable_thinking=False` to `apply_chat_template()`:

```python
input_ids = tokenizer.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    enable_thinking=False,  # Critical for tool-calling
    return_tensors='pt',
)
```

Alternative soft switch: Add `/no_think` to user prompt.

### 2. System Prompt Must Match Training

The model only outputs tool calls correctly when the system prompt matches what it saw during training:

```python
messages = [
    {'role': 'system', 'content': 'You are a coding assistant. Use tools...'},
    {'role': 'user', 'content': 'Read main.py'}
]
```

Without system prompt, model responds conversationally instead of with tool calls.

### 3. Unsloth formatting_func Quirks

The `formatting_func` for `SFTTrainer` can receive either:
- Single example (dict)
- Batched examples (dict of lists)

Must handle both:

```python
def formatting_func(examples):
    if isinstance(examples.get("conversations"), list) and \
       len(examples["conversations"]) > 0 and \
       isinstance(examples["conversations"][0], list):
        # Batched mode
        return [format_single(conv, sys, tools)
                for conv, sys, tools in zip(...)]
    else:
        # Single mode
        return [format_single(...)]
```

### 4. Separate Virtual Environment Required

Unsloth has specific PyTorch/CUDA dependencies that conflict with tunacode's main environment.

```bash
# Created training_env/.venv specifically for training
cd training_env && uv venv && source .venv/bin/activate
uv pip install unsloth transformers datasets peft trl
```

### 5. LoRA Adapter Loading

The saved adapter remembers its base model. Load directly:

```python
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="output/lora_adapter",  # Just the adapter path
    max_seq_length=1024,
    load_in_4bit=True,
)
FastLanguageModel.for_inference(model)  # 2x faster inference
```

### 6. 100 Examples + 1 Epoch = Sufficient for Format Learning

Even minimal training (100 examples, 1 epoch, 38 seconds) was enough to teach the model the tool-calling JSON format. The model correctly outputs:

```json
{"tool_call": {"name": "read_file", "arguments": {"file_path": "main.py"}}}
```

---

## Commands Reference

```bash
# Validate dataset (no GPU needed)
uv run python scripts/validate_training.py

# Generate more training data
uv run python scripts/generate_training_data.py --count 1000 --output data/training.jsonl

# Quick test run (10 steps, proves pipeline works)
cd /home/tuna/tunacode
source training_env/.venv/bin/activate
PYTHONPATH=src python -m tunacode.training.train \
    --dataset data/training.jsonl \
    --output ./output \
    --model unsloth/Qwen3-0.6B \
    --fast

# Full training run (1000 examples)
PYTHONPATH=src python -m tunacode.training.train \
    --dataset data/training.jsonl \
    --output ./output \
    --model unsloth/qwen3-4b \
    --epochs 1 \
    --batch-size 2 \
    --max-seq-length 2048

# Small GPU config (8-12GB VRAM)
PYTHONPATH=src python -m tunacode.training.train \
    --dataset data/training.jsonl \
    --output ./output \
    --model unsloth/Qwen3-0.6B \
    --batch-size 1 \
    --max-seq-length 1024 \
    --lora-r 8

# Test inference
source training_env/.venv/bin/activate && PYTHONPATH=src python -c "
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained('output/lora_adapter', load_in_4bit=True)
FastLanguageModel.for_inference(model)
# ... generate with enable_thinking=False
"
```

---

## Next Steps

1. **More training data**: Generate 500-1000 examples for better generalization
2. **More epochs**: Train 3-5 epochs to reinforce patterns
3. **GGUF export**: Convert to GGUF for llama.cpp/ollama deployment
4. **Integration**: Connect trained model to tunacode agent runtime
5. **Evaluation**: Create test set to measure tool-calling accuracy

---

## Rollback Point

```bash
git reset --hard 1736b42  # Before unsloth implementation
```

---

## Related Files

- Plan: `memory-bank/plan/2025-12-20_15-06-30_unsloth-finetuning-tools.md`
- Execution log: `memory-bank/execute/2025-12-20_15-30-00_unsloth-finetuning-tools.md`
- Training module: `src/tunacode/training/`
