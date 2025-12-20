# Research - Unsloth Fine-Tuning for Tool Calling

**Date:** 2025-12-20
**Owner:** agent
**Phase:** Research

## Goal

Understand how to fine-tune a small LLM using Unsloth for tool/function calling, specifically to train a model that can use tunacode's agent tools effectively.

## Findings

### 1. Unsloth Framework Overview

**Key Capabilities:**
- Fine-tune LLMs with minimal resources (3GB VRAM with QLoRA)
- Supports 4-bit quantization (QLoRA), 8-bit, 16-bit LoRA, and full fine-tuning
- 2x faster inference with `FastLanguageModel.for_inference(model)`
- Free on Colab/Kaggle, Windows/Linux only

**Recommended Starting Model:**
- Small instruct model like Llama 3.1 8B or smaller
- FunctionGemma (270M params) - designed specifically for function calling, runs on 550MB RAM

**Installation:**
```bash
pip install unsloth
```

### 2. Dataset Format for Tool Calling

**ShareGPT Format with Tools (Recommended):**
```json
{
  "conversations": [
    {"from": "human", "value": "user instruction"},
    {"from": "function_call", "value": "tool arguments"},
    {"from": "observation", "value": "tool result"},
    {"from": "gpt", "value": "model response"}
  ],
  "system": "system prompt (optional)",
  "tools": "tool description (optional)"
}
```

**OpenAI-Compatible Format:**
```json
{
  "messages": [
    {"role": "user", "content": "What is the weather?"},
    {"role": "assistant", "tool_calls": [
      {
        "id": "call_id",
        "type": "function",
        "function": {
          "name": "get_weather",
          "arguments": "{\"location\": \"SF\"}"
        }
      }
    ]},
    {"role": "tool", "tool_call_id": "call_id", "content": "21.0"},
    {"role": "assistant", "content": "It is 21 degrees."}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get current weather",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {"type": "string"}
          },
          "required": ["location"]
        }
      }
    }
  ]
}
```

### 3. Tunacode Tool Format

**Tool Definition (Python signatures -> JSON Schema):**

| Tool | Signature |
|------|-----------|
| `read_file` | `(filepath: str, offset: int = 0, limit: int \| None = None) -> str` |
| `grep` | `(pattern: str, directory: str = ".", case_sensitive: bool = False, ...) -> str` |
| `bash` | `(command: str, cwd: str \| None = None, timeout: int = 30) -> str` |
| `update_file` | `(filepath: str, target: str, patch: str) -> str` |
| `write_file` | `(filepath: str, content: str) -> str` |
| `glob` | `(pattern: str, directory: str = ".", recursive: bool = True, ...) -> str` |
| `list_dir` | `(directory: str = ".", max_files: int, show_hidden: bool = False) -> str` |

**Tool Call Format (pydantic-ai):**
```python
{
    "part_kind": "tool-call",
    "tool_name": "read_file",
    "tool_call_id": "unique_id",
    "args": {
        "filepath": "/path/to/file.py",
        "offset": 0,
        "limit": 2000
    }
}
```

**Tool Return Format:**
```python
{
    "part_kind": "tool-return",
    "tool_call_id": "unique_id",
    "tool_name": "read_file",
    "content": "<file>\n00001| import sys\n...</file>"
}
```

### 4. Training Configuration

**Selected Model: unsloth/qwen3-4b**
- 4B parameters - good balance of capability and efficiency
- Already cached locally at `~/.cache/huggingface/hub/models--unsloth--qwen3-4b`
- Unsloth-optimized for faster training

**Recommended Hyperparameters:**
```python
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments

# Load model
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/qwen3-4b",  # locally cached
    max_seq_length=2048,
    load_in_4bit=True,
    dtype=None,  # auto-detect
)

# Configure LoRA
model = FastLanguageModel.get_peft_model(
    model,
    r=16,  # LoRA rank
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_alpha=16,
    lora_dropout=0,
    use_gradient_checkpointing=True,
)

# Training args
training_args = TrainingArguments(
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,  # try 1e-4, 5e-5 for fine-tuning
    num_train_epochs=1,  # 1-3 epochs to avoid overfitting
    warmup_steps=10,
    output_dir="./output",
)
```

### 5. FunctionGemma (Specialized Option)

**Advantages:**
- Only 270M parameters
- Designed for function calling
- Runs on 550MB RAM CPU
- Supports reasoning before calls

**Chat Template:**
```
<developer>You are a model that can do function calling with the following functions.</developer>
<user>User query here</user>
<model>Function call or response</model>
```

### 6. Key Patterns for Tool Calling Training

**Multi-turn Conversation Structure:**
1. System prompt with tool definitions
2. User query
3. Model thinks/reasons (optional chain-of-thought)
4. Model generates function_call
5. System provides observation (tool result)
6. Model generates final response

**Parallel Tool Calls:**
Tunacode supports parallel read-only tools (grep, read_file, glob, list_dir, web_fetch). Training data should include examples of batched tool calls.

**Error Recovery:**
Include examples of:
- FileNotFoundError -> ModelRetry with corrected path
- Invalid arguments -> ModelRetry with corrections

## Key Patterns / Solutions Found

- **ShareGPT format**: Best for multi-turn tool calling with `from: function_call` and `from: observation` roles
- **Unsloth standardize_sharegpt**: `from unsloth.chat_templates import standardize_sharegpt` for data prep
- **Small models work**: FunctionGemma (270M) proves small models can do function calling effectively
- **QLoRA for efficiency**: 4-bit quantization with LoRA enables training on consumer GPUs

## Knowledge Gaps

1. **Conversation traces needed**: No existing tunacode conversation logs with tool calls for training data
2. **Multi-turn reasoning**: How to format chain-of-thought before tool selection
3. **Tool combination strategies**: When to use grep vs read_file vs list_dir
4. **Error recovery examples**: Need diverse error -> retry -> success patterns
5. **Parallel tool call format**: How to represent batched tool calls in training data

## Next Steps

1. **Generate synthetic training data**: Use Claude/GPT to generate diverse tool-calling conversations
2. **Collect real traces**: Instrument tunacode to log conversations with tool calls
3. **Choose base model**: FunctionGemma (270M) for minimal resources, Llama-3.2-1B for better reasoning
4. **Format dataset**: Convert to ShareGPT format with tool definitions
5. **Train with Unsloth**: Use QLoRA on Colab/local GPU

## References

- Unsloth docs: https://docs.unsloth.ai/get-started/fine-tuning-llms-guide
- FunctionGemma: https://docs.unsloth.ai/models/functiongemma
- ShareGPT format: https://raw.githubusercontent.com/HKUNLP/DiffuLLaMA/main/LLaMA-Factory/data/README.md
- Tool calling format: https://easyllm.tech/docs/data-preparation-tools.html
- Azure function fine-tuning: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/fine-tuning-functions

## Tunacode Tool Files

- Tool registration: `src/tunacode/core/agents/agent_components/agent_config.py:348-371`
- Tool decorators: `src/tunacode/tools/decorators.py`
- XML prompts: `src/tunacode/tools/prompts/`
- Tool examples: `src/tunacode/prompts/sections/examples.xml`
- Node processor (execution): `src/tunacode/core/agents/agent_components/node_processor.py`
