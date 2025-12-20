# Research - Tunacode Codebase Overview
**Date:** 2025-12-20
**Owner:** agent
**Phase:** Research

## Goal
Comprehensive codebase overview for tunacode, a TUI-based AI coding assistant with LLM fine-tuning capabilities.

## Findings

### Architecture Overview

Tunacode is a **TUI-based AI coding assistant** built with:
- **Textual** for the terminal UI (NeXTSTEP-inspired design)
- **pydantic-ai** for agent orchestration
- **Unsloth + QLoRA** for LLM fine-tuning

The codebase follows a clean three-layer architecture:

```
src/tunacode/
├── ui/           # TUI layer (Textual-based)
├── core/         # Agent logic and state management
├── tools/        # File ops, shell, search tools
└── training/     # LLM fine-tuning pipeline
```

---

### Core Components

#### 1. Entry Points
| File | Purpose |
|------|---------|
| `src/tunacode/ui/main.py:46` | CLI entry point (`tunacode` command) |
| `src/tunacode/ui/main.py:83-111` | `_default_command()` dispatches to TUI or headless mode |
| `src/tunacode/ui/app.py:68-534` | `TextualReplApp` main TUI application |

#### 2. Agent Core (`src/tunacode/core/`)
| File | Purpose |
|------|---------|
| `core/agents/main.py:527-545` | `process_request()` - main agent entry |
| `core/agents/main.py:270-454` | `RequestOrchestrator` - iteration loop |
| `core/state.py:36-128` | `SessionState` - conversation, tokens, costs |
| `core/state.py:130-410` | `StateManager` - singleton session manager |
| `core/compaction.py` | Token management via pruning |

**Agent Components** (`core/agents/agent_components/`):
- `node_processor.py` - Process pydantic-ai iteration nodes
- `streaming.py` - Token streaming to UI
- `tool_executor.py` - Parallel tool execution
- `response_state.py` - Completion/guidance tracking
- `task_completion.py` - DONE marker detection

#### 3. Tools System (`src/tunacode/tools/`)

**File Operations:**
- `read_file.py` - Read with offset/limit
- `write_file.py` - Create/overwrite
- `update_file.py` - Apply diffs

**Code Search:**
- `grep.py` - Regex search (ripgrep)
- `glob.py` - Pattern matching
- `list_dir.py` - Directory listing

**Execution:**
- `bash.py:34-102` - Command execution with security validation
- `web_fetch.py` - HTTP fetching

**Authorization** (`tools/authorization/`):
- `handler.py` - Tool confirmation coordinator
- `policy.py` - Yolo mode, ignore list
- `rules.py` - Tool restriction rules

**Decorators** (`tools/decorators.py`):
- `@base_tool` - Error handling wrapper
- `@file_tool` - File-specific errors + LSP integration

#### 4. UI Components (`src/tunacode/ui/`)

**Main App Flow:**
| Location | Purpose |
|----------|---------|
| `app.py:100-116` | `compose()` - UI hierarchy |
| `app.py:303-321` | `on_editor_submit_requested()` - Input handling |
| `app.py:367-383` | `streaming_callback()` - Throttled token display |
| `app.py:464-511` | `_show_inline_confirmation()` - Tool approval |

**Screens:**
- `screens/setup.py` - Initial setup wizard
- `screens/model_picker.py` - Model selection
- `screens/theme_picker.py` - Theme selection
- `screens/session_picker.py` - Session restore

**Widgets:**
- `widgets/messages.py` - `Editor` input with autocomplete
- `widgets/file_autocomplete.py` - Path completion
- `components/tool_panel.py` - Tool result rendering

---

### Training Module (`src/tunacode/training/`)

**Purpose:** Complete pipeline for fine-tuning LLMs on tool-calling patterns.

| File | Purpose |
|------|---------|
| `schema.py` | ShareGPT format models (Message, FunctionCall, ToolDefinition) |
| `tool_extractor.py` | Extract Python functions to JSON Schema |
| `scenarios.py` | 19 predefined tool-calling patterns |
| `dataset_generator.py` | Convert scenarios to training JSONL |
| `config.py` | QLoRA hyperparameters (LoraConfig, TrainingConfig) |
| `train.py` | Unsloth fine-tuning script |

**Data Generation Script:**
- `scripts/generate_training_data.py` - CLI for synthetic data generation

#### ShareGPT Format
```json
{
  "conversations": [
    {"from": "human", "value": "Read README.md"},
    {"from": "function_call", "value": "{\"name\": \"read_file\", \"arguments\": {\"filepath\": \"README.md\"}}"},
    {"from": "observation", "value": "File contents..."},
    {"from": "gpt", "value": "The README contains..."}
  ],
  "system": "You are a helpful coding assistant...",
  "tools": "[... JSON Schema array ...]"
}
```

#### Scenario Categories (19 total)
| Category | Count | Examples |
|----------|-------|----------|
| Read File | 2 | Basic read, offset/limit |
| Grep | 2 | Pattern search, function defs |
| Glob | 2 | Python files, test files |
| List Dir | 2 | Basic, subdirectory |
| Bash | 3 | Git status, pytest, pip install |
| Write/Update | 3 | New file, fix typo, refactor |
| Web Fetch | 1 | Fetch docs |
| Multi-Step | 2 | Explore codebase, find+read |
| Error Recovery | 2 | File not found, typo recovery |

#### Unsloth Integration
- `FastLanguageModel.from_pretrained()` - 4-bit quantization
- `FastLanguageModel.get_peft_model()` - Apply LoRA adapters
- Target modules: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj
- Default LoRA rank: 16
- Gradient checkpointing enabled

**Config Presets:**
- `default_config()` - Sensible defaults
- `small_gpu_config()` - 8-12GB VRAM (batch=1, grad_accum=8)
- `fast_iteration_config()` - Testing (max_steps=10)

---

### Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Build system, deps, ruff, mypy, bandit |
| `pytest.ini` | Test configuration |
| `.pre-commit-config.yaml` | Pre-commit hooks |
| `CLAUDE.md` | Project instructions for Claude agents |
| `docs/configuration/tunacode.json.example` | Example user config |

### Data Files

| File | Purpose |
|------|---------|
| `data/training.jsonl` | Training data (1000 examples, ~9.7MB) |

### Knowledge Base (`.claude/`)

```
.claude/
├── metadata/        # Component summaries
├── debug_history/   # Debugging sessions
├── qa/              # Q&A knowledge
├── patterns/        # Reusable solutions
├── cheatsheets/     # Quick references
├── delta/           # API/behavior changes
└── memory_anchors/  # Core concepts
```

### Session Tracking (`memory-bank/`)

```
memory-bank/
├── research/   # 30 research sessions
├── plan/       # 9 planning docs
├── execute/    # 11 execution logs + JOURNAL.md
└── cleanup-sweep/  # Code cleanup notes
```

---

## Key Patterns / Solutions Found

| Pattern | Description |
|---------|-------------|
| Factory Pattern | `create_research_agent()`, authorization policy factories |
| Decorator Pattern | `@base_tool`, `@file_tool` for cross-cutting concerns |
| Observer Pattern | Callbacks for streaming, tool confirmation, results |
| State Machine | `ResponseState` for completion tracking |
| Strategy Pattern | Authorization policies (yolo, ignore list) |

---

## Data Flow

### User Request to Agent Response:
1. User types in Editor
2. `EditorSubmitRequested` event
3. Command check via `handle_command()`
4. Queued to `request_queue`
5. Worker picks up request
6. `RequestOrchestrator` initialized
7. Agent created via `get_or_create_agent()`
8. Message history pruned (compaction)
9. Iteration loop via `agent.iter()`
10. Tokens streamed to UI
11. Final response displayed

### Tool Execution:
1. Agent decides to use tool
2. `ToolHandler.should_confirm()` checks policy
3. If needed, confirmation panel shown
4. User presses 1/2/3 (approve/skip/reject)
5. Tool executes with decorators
6. Result displayed in UI

---

## Knowledge Gaps

- Test coverage is minimal (noted as expected during rewrite)
- Some documentation in memory-bank may be stale
- Error recovery scenarios could be expanded

## References

- Main README: `/home/tuna/tunacode/README.md`
- Project instructions: `/home/tuna/tunacode/CLAUDE.md`
- Training report: `/home/tuna/tunacode/REPORT.md`
- UI design: `/home/tuna/tunacode/docs/ui/design_philosophy.md`
- Tools architecture: `/home/tuna/tunacode/docs/tools/architecture.md`
- Current training data: `/home/tuna/tunacode/data/training.jsonl`
