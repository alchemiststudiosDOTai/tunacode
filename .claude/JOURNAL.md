# Claude Journal

## 2026-01-07: Renderer Unification

Unifying the 8 tool renderers in `src/tunacode/ui/renderers/tools/` to eliminate duplication via a shared base class and registry pattern.

### Completed:
- T2: Created `base.py` with `BaseToolRenderer[T]` ABC and `ToolRendererProtocol`
- T3: Extracted shared helpers: `truncate_line`, `truncate_content`, `pad_lines`
- T4: Added registry pattern: `@tool_renderer`, `get_renderer`, `list_renderers`
- Migrated `list_dir.py` to use `BaseToolRenderer` (199 -> 149 lines)
- Created documentation at `docs/ui/tool_renderers.md`
- All 182 tests passing

### Next Action:
Migrate remaining 7 renderers to use `BaseToolRenderer`:
- `bash.py` (has conditional border color based on exit code - good test of override pattern)
- `read_file.py`
- `update_file.py`
- `glob.py`
- `grep.py`
- `web_fetch.py`
- `research.py`

### Remaining Work:
1. Migrate bash renderer (tests `get_border_color`/`get_status_text` overrides)
2. Migrate remaining 6 renderers
3. Delete duplicated `BOX_HORIZONTAL`, `SEPARATOR_WIDTH`, `_truncate_line` from each file
4. Update subplan document with completion status

### Key Context:
- Files:
  - `src/tunacode/ui/renderers/tools/base.py` - base class + helpers + registry
  - `src/tunacode/ui/renderers/tools/list_dir.py` - migrated example
  - `docs/ui/tool_renderers.md` - documentation
  - `memory-bank/plan/subplan-renderer-ui.md` - original analysis
- Branch: master
- Commands: `uv run ruff check src/tunacode/ui/renderers/tools/` and `uv run pytest tests/ -x -q`

### Notes:
- Each renderer has a `Data` dataclass that stays tool-specific
- The `render_*` function stays as public API, delegates to class instance
- `bash.py` is a good next target because it uses conditional coloring (exit code)
- Pattern: keep dataclass, create Renderer class, instantiate at module level, decorate render function

### Architecture Decisions Made:
- Module-level singleton renderer instances (not created per-call)
- Render functions remain the public API (backward compatible)
- `@tool_renderer` decorator for self-registration
- Helpers are standalone functions, not methods (easier to use without instantiation)

---

## 2026-01-07: Local Mode Context Optimization

### Task: Reduce context usage for local models with small context windows (10k)

### Problem:
- System prompt + tool schemas used ~3.5k tokens before any conversation
- Each file read could use 2000 lines (~20k tokens)
- With 10k context, only ~6.5k left for conversation
- LLM APIs are stateless - system prompt sent every turn

### Completed:

**1. Minimal System Prompt**
- Created `CLAUDE_LOCAL.md` - condensed project instructions (~400 tokens)
- Added `LOCAL_TEMPLATE` in `templates.py` - only 3 sections: AGENT_ROLE, TOOL_USE, USER_INSTRUCTIONS
- `local_mode: true` setting triggers minimal template

**2. Minimal Tool Schemas**
- Reduced from 11 tools to 6 (bash, read_file, update_file, write_file, glob, list_dir)
- Removed: grep, web_fetch, research_codebase, todo tools
- 1-word descriptions ("Shell", "Read", "Edit", etc.) - saves ~1k tokens

**3. Aggressive Pruning**
- LOCAL_PRUNE_PROTECT_TOKENS: 2,000 (vs 40,000)
- LOCAL_PRUNE_MINIMUM_THRESHOLD: 500 (vs 20,000)
- Messages pruned much faster to save context

**4. Tool Output Limits**
- LOCAL_DEFAULT_READ_LIMIT: 200 lines (vs 2,000)
- LOCAL_MAX_LINE_LENGTH: 500 chars (vs 2,000)
- LOCAL_MAX_COMMAND_OUTPUT: 1,500 chars (vs 5,000)

**5. Response Limit**
- local_max_tokens: 1000 - caps model output per turn

### Key Files Modified:
- `CLAUDE_LOCAL.md` - Condensed project guide with few-shot example
- `src/tunacode/core/prompting/templates.py` - Added LOCAL_TEMPLATE
- `src/tunacode/core/prompting/__init__.py` - Export LOCAL_TEMPLATE
- `src/tunacode/core/agents/agent_components/agent_config.py` - Local mode tool/prompt selection
- `src/tunacode/core/compaction.py` - Dynamic thresholds via get_prune_thresholds()
- `src/tunacode/constants.py` - Local mode limit constants
- `src/tunacode/tools/read_file.py` - Uses local limits
- `src/tunacode/tools/bash.py` - Uses local limits
- `tests/test_compaction.py` - Mock get_prune_thresholds for tests
- `~/.config/tunacode.json` - User config
- `~/.config/tunacode.json.bak` - Backup of original config

### Current Config (~/.config/tunacode.json):
```json
{
  "default_model": "openai:NousResearch/NousCoder-14B",
  "env": {
    "OPENAI_BASE_URL": "http://127.0.0.1:8080/v1",
    "OPENAI_API_KEY": "not-needed"
  },
  "settings": {
    "local_mode": true,
    "local_max_tokens": 1000,
    "context_window_size": 10000,
    "guide_file": "CLAUDE_LOCAL.md"
  }
}
```

### Token Budget (Local Mode):
| Component | Tokens |
|-----------|--------|
| System prompt | ~1,117 |
| Guide file | ~527 |
| 6 tools (minimal) | ~575 |
| **Total base** | **~2,200** |

With 10k context: ~7.8k available for conversation

### Key Insight:
LLM APIs are stateless. Every request sends: system prompt + tool schemas + full conversation history. Model has no memory - re-reads everything each turn.

### Commands:
- `uv run pytest tests/ -x -q` - All tests pass
- `uv run ruff check --fix .` - Lint
- Restore config: `cp ~/.config/tunacode.json.bak ~/.config/tunacode.json`

### Branch: master

### Notes:
- llama.cpp uses KV cache efficiently (LCP similarity) so repeated prompt not re-computed
- guide_file setting now actually used (was hardcoded to AGENTS.md)
- Few-shot example in CLAUDE_LOCAL.md uses real JSON tool call format

### Next Steps:
- Test with actual local model to verify token savings
- Consider further prompt compression if needed
- May add more few-shot examples for complex tasks

---

## 2026-01-06: Local Model Support

### Task: Add local model support to tunacode

### Completed:
- Created condensed system prompt at `src/tunacode/prompts/local_model_prompt.txt` (~500 bytes vs 34KB full prompt)
- Added `local_model: true/false` setting in config defaults
- Modified `load_system_prompt()` to use condensed prompt when `local_model=true`
- Added cache invalidation for `local_model` setting in `_compute_agent_version()`
- Skip AGENTS.md loading for local models to save tokens
- Created `fallback_executor.py` for models that output tool calls in text (e.g., `<tool_call>` tags)
- Updated `node_processor.py` to detect and execute fallback tool calls
- Passed `agent_ctx` through the call chain for result injection
- Tested with multiple local models via LM Studio/vLLM

### Key Files Modified:
- `src/tunacode/prompts/local_model_prompt.txt` - Condensed prompt
- `src/tunacode/configuration/defaults.py` - Added `local_model` setting
- `src/tunacode/core/agents/agent_components/agent_config.py` - Local model loading logic
- `src/tunacode/core/agents/agent_components/node_processor.py` - Fallback tool parsing
- `src/tunacode/core/agents/agent_components/fallback_executor.py` - Direct tool execution
- `src/tunacode/core/agents/main.py` - Pass agent_ctx to node processor
- `~/.config/tunacode.json` - User config with local model settings

### Current Config:
```json
{
  "default_model": "openai:cerebras_Qwen3-Coder-REAP-25B-A3B-Q3_K_L.gguf",
  "env": {
    "OPENAI_BASE_URL": "http://localhost:8080/v1",
    "OPENAI_API_KEY": "lm-studio"
  },
  "settings": {
    "local_model": true
  }
}
```

### Current Prompt:
```
###Role###
You are TunaCode, a coding assistant.

###Rules###
- ONE tool call at a time max
- Keep responses to 1 sentence
- No explanations. No chitchat.
Say "TUNACODE DONE:" when task complete.

###Tools###
glob(pattern) - Find files
grep(pattern, directory) - Search code
read_file(filepath) - Read file
list_dir(directory) - List dir
write_file(filepath, content) - Create file
update_file(filepath, old_text, new_text) - Edit file
bash(command) - Run command

Working directory: {{CWD}}
```

### Notes:
- Qwen2.5-Coder-14B supports native OpenAI tool calling format
- Smaller models (0.6B-1.7B) output `<tool_call>` tags in content - fallback parser handles this
- Model is still chatty despite "keep short" instructions - may need further prompt tuning
- Branch: master
- Version bumped to 0.1.21

### Next Steps:
- Continue testing prompt variations for brevity
- Consider adding few-shot examples if model continues verbose
- May need model-specific prompt variations

---

## 2026-01-07: Centralized Limits Module + Tool Tweaks

### Task: Refactor scattered local_mode checks into centralized limits.py module

### Completed:

**1. Created `src/tunacode/core/limits.py`**
- Centralized all tool output limits with 3-tier precedence: explicit setting > local_mode default > standard default
- Functions: `is_local_mode()`, `get_read_limit()`, `get_max_line_length()`, `get_command_limit()`, `get_max_files_in_dir()`, `get_max_tokens()`
- Uses `@lru_cache` for settings, `clear_cache()` to invalidate

**2. Refactored tools to use limits module**
- `bash.py` → `get_command_limit()`
- `read_file.py` → `get_read_limit()`, `get_max_line_length()`
- `agent_config.py` → `is_local_mode()`, `get_max_tokens()`

**3. Kept prune thresholds binary in compaction.py**
- Decided prune thresholds are internal optimization, not user-configurable
- `compaction.py` imports `is_local_mode()` from limits, does binary switch

**4. Renamed CLAUDE_LOCAL.md → src/tunacode/core/prompting/local_prompt.md**
- Moved into prompting directory as part of the system
- `load_tunacode_context()` loads it automatically for local_mode

**5. Documentation**
- `docs/configuration/README.md` - tool limits + local mode sections
- `docs/configuration/tunacode.json.example` - all new settings
- `docs/codebase-map/modules/core-limits.md` - new module doc
- Updated INDEX.md and core-compaction.md

### Key Design Decision:
- **Tool limits** (read_limit, max_command_output, etc.) → Option 3: user configurable with cascading defaults
- **Prune thresholds** → Binary switch only (local_mode on/off), not user-configurable

### PR #215: feat: local mode + configurable tool limits
- Branch: `local`
- Status: Open
- URL: https://github.com/alchemiststudiosDOTai/tunacode/pull/215

---

**6. Tool-tweaks branch (separate PR)**
- Fixed `list_dir.py`: FileNotFoundError → ModelRetry for recoverable errors
- Added debug history: `.claude/debug_history/list-dir-tool-execution-error.md`
- Added KB entries to CLAUDE.md for list_dir bug and glob/grep smell

### Branch: tool-tweaks
- Status: Pushed, ready for PR
- Commits:
  - `cfbafb3 chore: add debug history`
  - `3a9edf7 docs: add KB entries for list_dir bug and glob/grep smell`
  - `4e4d0bc fix: list_dir uses ModelRetry for recoverable errors`

### Key Files:
- `src/tunacode/core/limits.py` - NEW centralized limits
- `src/tunacode/core/prompting/local_prompt.md` - renamed from CLAUDE_LOCAL.md
- `src/tunacode/tools/list_dir.py` - ModelRetry fix (tool-tweaks branch)

### Commands:
- `uv run pytest tests/ -x -q` - 188 tests pass
- `uv run ruff check --fix .` - lint

### Next Steps:
- Open PR for tool-tweaks branch
- Consider fixing glob/grep to use ModelRetry pattern (noted smell)
- Test local_mode with actual local model
