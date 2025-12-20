# Research - Small Model RL Training for Tunacode Search Workflows

**Date:** 2025-12-19
**Owner:** Agent
**Phase:** Research

## Goal

Design a complete plan for training a very small experimental RL model using prime-rl to handle tunacode's search workflows (glob, grep, read tool selection and execution).

## Executive Summary

This research synthesizes findings from both the **prime-rl** RL training framework and **tunacode** agent codebase to create a viable plan for training a small (0.6B-1.7B parameter) model to perform code search tasks. The model will learn to:

1. Select appropriate tools (glob, grep, read_file) based on user queries
2. Chain tools in the correct order (GLOB -> GREP -> READ funnel)
3. Generate valid tool call parameters
4. Interpret results and decide next actions

---

## Part 1: Prime-RL Framework Analysis

### 1.1 Architecture Overview

Prime-RL is a disaggregated async RL framework with three components:

| Component | Role | Hardware |
|-----------|------|----------|
| **Orchestrator** | Coordinates rollouts, computes advantages, manages buffer | CPU-only |
| **Trainer** | FSDP2-based model training with AIPO loss | GPU (1-N) |
| **Inference** | vLLM-based rollout generation | GPU (1-N) |

**Key Files:**
- `/root/tunacode/prime-rl/src/prime_rl/rl.py` - Main entry point
- `/root/tunacode/prime-rl/src/prime_rl/trainer/rl/train.py` - Training loop
- `/root/tunacode/prime-rl/src/prime_rl/orchestrator/orchestrator.py` - Rollout coordination
- `/root/tunacode/prime-rl/src/prime_rl/trainer/rl/loss.py` - AIPO loss computation

### 1.2 Training Loop

```
1. Orchestrator samples tasks from buffer
2. Inference generates completions via vLLM
3. Environment (verifier) scores completions -> rewards
4. Advantages computed per-group (GRPO-style)
5. Trainer receives packed batches with advantages
6. Forward-backward with importance-weighted loss (AIPO)
7. Weights broadcast back to inference servers
8. Repeat
```

### 1.3 GRPO/AIPO Implementation

**Advantage Computation** (`orchestrator/advantage.py:6-29`):
```python
# Group-relative: advantage = reward - mean(group_rewards)
rewards = torch.tensor(rewards).view(-1, samples_per_problem)
baseline = rewards.mean(dim=1, keepdim=True)
advantages = (rewards - baseline).flatten()
```

**Loss Function** (`trainer/rl/loss.py:49-151`):
- Token-level importance sampling with clipping
- KL penalty term for distribution drift
- Configurable masking strategies (token, sequence, geometric)

### 1.4 Small Model Configuration

**Supported Small Models:**
- `Qwen/Qwen3-0.6B` (600M params) - Primary recommendation
- `TinyLlama/TinyLlama-1.1B` (1.1B params)
- `microsoft/phi-2` (2.7B params)

**Memory Optimization Options:**
```toml
[model]
name = "Qwen/Qwen3-0.6B"

[model.debug]
num_layers = 8  # Truncate to 8 layers (half default)

[model.lora]
rank = 8
alpha = 16.0
target_modules = ["q_proj", "v_proj", "o_proj"]

[model]
ac = { freq = 1 }  # Full activation checkpointing
fsdp_cpu_offload = true  # Offload optimizer to CPU
```

### 1.5 Hardware Requirements

| Setup | GPUs | Config |
|-------|------|--------|
| Minimal | 1 GPU | Shared memory (inference 50%, trainer 50%) |
| Small | 2 GPUs | 1 inference + 1 trainer |
| Medium | 8 GPUs | 6 inference (DP=6) + 2 trainer |

**Single GPU Command:**
```bash
uv run rl \
  --trainer @ config/train.toml \
  --orchestrator @ config/orch.toml \
  --inference @ config/infer.toml \
  --trainer-gpu-ids 0 \
  --inference-gpu-ids 0 \
  --inference.gpu-memory-utilization 0.5
```

---

## Part 2: Tunacode Tool System Analysis

### 2.1 Tool Interfaces

The model must learn to generate valid JSON tool calls for these tools:

#### Glob Tool
```json
{
  "tool": "glob",
  "args": {
    "pattern": "**/*.py",           // Required: glob pattern
    "directory": ".",               // Optional: search root
    "recursive": true,              // Optional: recursive search
    "include_hidden": false,        // Optional: hidden files
    "max_results": 5000             // Optional: result limit
  }
}
```

**File:** `/root/tunacode/src/tunacode/tools/glob.py:46-57`

#### Grep Tool
```json
{
  "tool": "grep",
  "args": {
    "pattern": "function_name",     // Required: search pattern
    "directory": ".",               // Optional: search root
    "case_sensitive": false,        // Optional
    "include_files": "*.py",        // Optional: file filter
    "max_results": 50,              // Optional: result limit
    "context_lines": 2,             // Optional: context
    "output_mode": "content"        // Optional: content|files_with_matches|count
  }
}
```

**File:** `/root/tunacode/src/tunacode/tools/grep.py:419-432`

#### Read File Tool
```json
{
  "tool": "read_file",
  "args": {
    "filepath": "/absolute/path/to/file.py",  // Required: absolute path
    "offset": 0,                               // Optional: start line
    "limit": 2000                              // Optional: max lines
  }
}
```

**File:** `/root/tunacode/src/tunacode/tools/read_file.py:17-23`

### 2.2 Search Funnel Pattern

Tunacode enforces a **GLOB -> GREP -> READ** workflow via system prompts:

```
1. GLOB: Find candidate files by pattern
   Input: "Find all Python files"
   Output: List of file paths

2. GREP: Search content in candidates
   Input: "Search for 'def process_request'"
   Output: File paths with matching lines + context

3. READ: Read specific files for details
   Input: "Read /root/tunacode/src/tunacode/core/agents/main.py"
   Output: File content with line numbers
```

**Enforcement:** `/root/tunacode/src/tunacode/prompts/sections/search_pattern.xml:1-80`

### 2.3 Tool Execution Flow

```
Model generates tool_call parts
    -> Tools categorized (read-only vs write)
    -> Read-only tools execute in parallel (max 3 concurrent)
    -> Results returned to model
    -> Model decides next action or completion
```

**Key Files:**
- `/root/tunacode/src/tunacode/core/agents/agent_components/node_processor.py:270-386`
- `/root/tunacode/src/tunacode/core/agents/agent_components/tool_executor.py:44-101`

### 2.4 Model Integration Points

To swap in a trained model:

1. **Provider Config** (`agent_config.py:252-269`):
```python
PROVIDER_CONFIG = {
    "local": {
        "api_key_name": "LOCAL_API_KEY",
        "base_url": "http://localhost:8000/v1",
    },
}
```

2. **Model Selection** (`app.py:248`):
```python
state_manager.session.current_model = "local:tunacode-search-0.6b"
```

3. **Tool Subset** (`agent_config.py:348-371`):
```python
# For small model, limit to search tools only
tools_list = [
    Tool(glob, ...),
    Tool(grep, ...),
    Tool(read_file, ...),
    Tool(list_dir, ...),
]
```

---

## Part 3: Training Plan

### 3.1 Phase 1: Environment Creation

Create a **verifiers environment** for code search tasks:

```python
# tunacode_search_env/environment.py
import verifiers as vf

class CodeSearchEnvironment(vf.Environment):
    """Environment for training code search tool selection."""

    def get_dataset(self):
        """Return dataset of search tasks."""
        return [
            {
                "prompt": "Find all Python files that define a class named 'Agent'",
                "ground_truth": {"tool_sequence": ["glob", "grep", "read_file"]},
                "codebase_root": "/path/to/test/codebase",
            },
            # ... more examples
        ]

    @property
    def rubric(self):
        return CompositeRubric([
            ToolSequenceRubric(weight=0.3),   # Correct tool order
            ToolArgsRubric(weight=0.3),        # Valid parameters
            TaskCompletionRubric(weight=0.4),  # Found correct answer
        ])
```

**Rubric Components:**

1. **ToolSequenceRubric**: Rewards correct tool selection order
   - +1.0 for GLOB -> GREP -> READ when appropriate
   - +0.5 for partial correct sequences
   - 0.0 for incorrect tool choice

2. **ToolArgsRubric**: Rewards valid tool parameters
   - +1.0 for syntactically valid args
   - +0.5 for mostly valid with minor issues
   - 0.0 for invalid args that would fail

3. **TaskCompletionRubric**: Rewards finding correct answer
   - +1.0 for correct file/content found
   - +0.5 for partial match
   - 0.0 for wrong answer

### 3.2 Phase 2: Dataset Creation

**SFT Dataset Format:**
```json
{
  "prompt": "<|system|>You are a code search assistant with tools: glob, grep, read_file...<|user|>Find all test files that import pytest",
  "completion": "<|assistant|>I'll search for test files importing pytest.\n\n<tool_call>{\"name\": \"glob\", \"arguments\": {\"pattern\": \"**/test_*.py\"}}</tool_call>",
  "task": "code-search"
}
```

**Dataset Sources:**
1. Recorded tunacode sessions (real user queries)
2. Synthetic tasks from codebases (GitHub repos)
3. Curated examples of correct tool usage

**Recommended Size:**
- SFT warmup: 1,000-10,000 examples
- RL training: Buffer of 10,000+ tasks (sampled online)

### 3.3 Phase 3: SFT Warmup

**Config:** `tunacode_search_sft.toml`
```toml
max_steps = 100
clean = true

[model]
name = "Qwen/Qwen3-0.6B"
seq_len = 2048

[wandb]
project = "tunacode-search"
name = "sft-warmup"

[data]
name = "your-org/tunacode-search-sft"
seq_len = 2048
batch_size = 32

[optim]
type = "adamw"
lr = 2e-5
weight_decay = 0.01

[scheduler]
type = "cosine"
warmup_steps = 10
min_lr = 1e-6
```

**Command:**
```bash
uv run sft @ tunacode_search_sft.toml \
  --wandb.project tunacode-search \
  --wandb.name sft-warmup-v1
```

### 3.4 Phase 4: RL Training

**Config:** `tunacode_search_rl.toml`
```toml
max_steps = 50
clean = true

[model]
name = "path/to/sft-checkpoint"  # From Phase 3
seq_len = 2048

[wandb]
project = "tunacode-search"
name = "rl-training"

[orchestrator]
batch_size = 64
rollouts_per_example = 8
seq_len = 2048

[orchestrator.sampling]
temperature = 0.8
max_tokens = 512

[[orchestrator.env]]
id = "your-org/tunacode-search"
args = { max_turns = 5 }

[orchestrator.buffer]
online_difficulty_filtering = true
easy_threshold = 0.9
hard_threshold = 0.1

[orchestrator.advantage]
length_weighted_mean = false

[trainer.loss]
ratio_type = "token"
kl_tau = 0.01

[trainer.optim]
type = "adamw"
lr = 1e-5
weight_decay = 0.01

[trainer.scheduler]
type = "cosine"
warmup_steps = 5
min_lr = 1e-6

[inference]
gpu-memory-utilization = 0.5

[inference.model]
enable_auto_tool_choice = true
tool_call_parser = "hermes"
```

**Command:**
```bash
uv run rl @ tunacode_search_rl.toml \
  --trainer-gpu-ids 0 \
  --inference-gpu-ids 0 \
  --inference.gpu-memory-utilization 0.5
```

### 3.5 Phase 5: Evaluation

**Metrics to Track:**
1. **Tool Selection Accuracy**: % correct tool for task type
2. **Argument Validity**: % syntactically valid tool args
3. **Task Completion Rate**: % tasks finding correct answer
4. **Efficiency**: Average tools per task (lower is better)

**Eval Command:**
```bash
uv run vf-eval tunacode-search \
  -m /path/to/rl-checkpoint \
  -b http://localhost:8000/v1 \
  -n 100 \
  --max-tokens 512
```

### 3.6 Phase 6: Integration

**Deploy trained model:**

1. **Serve with vLLM:**
```bash
python -m vllm.entrypoints.openai.api_server \
  --model /path/to/rl-checkpoint \
  --port 8000 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes
```

2. **Configure tunacode:**
```python
# In agent_config.py
PROVIDER_CONFIG["local"] = {
    "api_key_name": "LOCAL_API_KEY",
    "base_url": "http://localhost:8000/v1",
}
```

3. **Set as default:**
```json
// ~/.config/tunacode/tunacode.json
{
  "default_model": "local:tunacode-search-0.6b"
}
```

---

## Part 4: Implementation Checklist

### 4.1 Environment Setup
- [ ] Install prime-rl: `curl -sSL .../install.sh | bash`
- [ ] Install verifiers: `uv pip install verifiers>=0.1.8`
- [ ] Verify GPU access: `nvidia-smi`
- [ ] Test debug config: `uv run sft @ configs/debug/sft/train.toml`

### 4.2 Dataset Creation
- [ ] Define task taxonomy (file search, content search, etc.)
- [ ] Record tunacode sessions for real examples
- [ ] Generate synthetic tasks from public codebases
- [ ] Format as HuggingFace dataset
- [ ] Split train/val/test (80/10/10)

### 4.3 Environment Implementation
- [ ] Create verifiers environment package
- [ ] Implement ToolSequenceRubric
- [ ] Implement ToolArgsRubric
- [ ] Implement TaskCompletionRubric
- [ ] Test with `prime env install ./tunacode-search-env`

### 4.4 Training Pipeline
- [ ] Run SFT warmup (100 steps)
- [ ] Validate SFT checkpoint with eval
- [ ] Run RL training (50-200 steps)
- [ ] Monitor W&B metrics
- [ ] Select best checkpoint by eval score

### 4.5 Integration
- [ ] Deploy trained model with vLLM
- [ ] Add provider config to tunacode
- [ ] Test tool execution end-to-end
- [ ] Compare against baseline (full model)
- [ ] Document performance tradeoffs

---

## Key Patterns / Solutions Found

| Pattern | Description | Relevance |
|---------|-------------|-----------|
| **GRPO Advantages** | Group-relative baseline subtraction | Core RL algorithm |
| **AIPO Loss** | Token-level importance sampling with clipping | Handles off-policy data |
| **Tool Schemas** | pydantic-ai JSON schema generation | Model must output valid schemas |
| **Search Funnel** | GLOB->GREP->READ enforced pattern | Training target behavior |
| **Async Training** | Inference ahead by N steps | Compute efficiency |

## Knowledge Gaps

1. **Tool Call Format**: Need to verify Hermes format compatibility with tunacode's expected format
2. **Multi-turn Trajectories**: Unclear if interleaved or branching strategy is better for search
3. **Reward Shaping**: Optimal balance between tool selection vs task completion rewards
4. **Context Window**: Impact of small model's 2048 context vs tunacode's typical usage

## References

### Prime-RL
- `/root/tunacode/prime-rl/README.md` - Overview
- `/root/tunacode/prime-rl/docs/entrypoints.md` - Component docs
- `/root/tunacode/prime-rl/docs/configs.md` - Configuration system
- `/root/tunacode/prime-rl/examples/wiki_search/` - Tool-use example

### Tunacode
- `/root/tunacode/src/tunacode/tools/` - Tool implementations
- `/root/tunacode/src/tunacode/core/agents/agent_components/agent_config.py` - Model integration
- `/root/tunacode/src/tunacode/prompts/sections/search_pattern.xml` - Search workflow prompt

### External
- [verifiers library](https://github.com/willccbb/verifiers) - Environment framework
- [pydantic-ai](https://ai.pydantic.dev/) - Agent framework
- [vLLM](https://docs.vllm.ai/) - Inference server
