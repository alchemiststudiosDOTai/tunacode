# Claude Journal

## 2026-01-07: Renderer Unification

Unifying the 8 tool renderers in `src/tunacode/ui/renderers/tools/` to eliminate duplication via a shared base class and registry pattern.

### Completed:
- Created `base.py` with `BaseToolRenderer[T]` ABC and `ToolRendererProtocol`
- Extracted shared helpers: `truncate_line`, `truncate_content`, `pad_lines`
- Added registry pattern: `@tool_renderer`, `get_renderer`, `list_renderers`
- Migrated `list_dir.py` to use `BaseToolRenderer` (199 -> 149 lines)
- Created documentation at `docs/ui/tool_renderers.md`

### Architecture Decisions:
- Module-level singleton renderer instances (not created per-call)
- Render functions remain the public API (backward compatible)
- `@tool_renderer` decorator for self-registration
- Helpers are standalone functions, not methods

---

## 2026-01-07: Local Mode Context Optimization

### Problem:
- System prompt + tool schemas used ~3.5k tokens before any conversation
- Each file read could use 2000 lines (~20k tokens)
- With 10k context, only ~6.5k left for conversation
- LLM APIs are stateless - system prompt sent every turn

### Solution:

**1. Minimal System Prompt**
- `LOCAL_TEMPLATE` in `templates.py` - only 3 sections: AGENT_ROLE, TOOL_USE, USER_INSTRUCTIONS
- `local_mode: true` setting triggers minimal template

**2. Minimal Tool Schemas**
- Reduced from 11 tools to 6 (bash, read_file, update_file, write_file, glob, list_dir)
- 1-word descriptions ("Shell", "Read", "Edit", etc.) - saves ~1k tokens

**3. Aggressive Pruning**
- LOCAL_PRUNE_PROTECT_TOKENS: 2,000 (vs 40,000)
- LOCAL_PRUNE_MINIMUM_THRESHOLD: 500 (vs 20,000)

**4. Tool Output Limits**
- LOCAL_DEFAULT_READ_LIMIT: 200 lines (vs 2,000)
- LOCAL_MAX_LINE_LENGTH: 500 chars (vs 2,000)
- LOCAL_MAX_COMMAND_OUTPUT: 1,500 chars (vs 5,000)

**5. Response Limit**
- local_max_tokens: 1000 - caps model output per turn

### Token Budget (Local Mode):
| Component | Tokens |
|-----------|--------|
| System prompt | ~1,100 |
| Guide file | ~500 |
| 6 tools (minimal) | ~575 |
| **Total base** | **~2,200** |

With 10k context: ~7.8k available for conversation.

### Key Insight:
LLM APIs are stateless. Every request sends: system prompt + tool schemas + full conversation history. Model has no memory - re-reads everything each turn.

### Key Files:
- `src/tunacode/core/limits.py` - Centralized limit configuration
- `src/tunacode/core/prompting/templates.py` - LOCAL_TEMPLATE
- `src/tunacode/core/prompting/local_prompt.md` - Condensed prompt
- `src/tunacode/core/compaction.py` - Dynamic prune thresholds
- `src/tunacode/constants.py` - Local mode limit constants
