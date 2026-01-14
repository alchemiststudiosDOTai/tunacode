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

### Notes:
- Qwen2.5-Coder-14B supports native OpenAI tool calling format
- Smaller models (0.6B-1.7B) output `<tool_call>` tags in content - fallback parser handles this
- llama.cpp uses KV cache efficiently (LCP similarity) so repeated prompt not re-computed

---

## 2026-01-08: Config Restoration & Local Mode Docs

### Task: Restore pre-local-mode config and document local mode setup

### Completed:

**1. Config Backup Discovery**
Found three config variants in `~/.config/`:
- `tunacode.json` - was set to local mode (grok-code-fast-1, 10k context)
- `tunacode.json.bak` - MiniMax-M2.1, 200k context, no local mode
- `@tunacode.json` - Gemini 3 Pro via OpenRouter

**2. Restored Config**
- Restored `~/.config/tunacode.json` from `.bak` (MiniMax config)
- Settings: `minimax:MiniMax-M2.1`, 200k context, `guide_file: AGENTS.md`

**3. Created Local Mode Example**
- Created `docs/configuration/tunacode.local.json.example`
- Documents all local mode settings:
  - `local_mode: true`
  - `local_max_tokens: 1000`
  - `context_window_size: 10000`
  - `OPENAI_BASE_URL: http://127.0.0.1:8080/v1`
  - `guide_file: CLAUDE_LOCAL.md`

### Key Files:
- `~/.config/tunacode.json` - user config (restored to MiniMax)
- `docs/configuration/tunacode.json.example` - standard example
- `docs/configuration/tunacode.local.json.example` - NEW: local mode example

### Notes:
- Local mode uses condensed prompts and minimal tool schemas for small context windows
- The `.bak` file preserved the pre-experimentation state - good backup hygiene!
- User was testing local models, now back to cloud (MiniMax)

---

## 2026-01-08: Syntax Highlighting for Tool Renderers (Branch: ui-model-work)

### The Mission:
Make tool outputs pretty! All those ugly plain text viewports were a crime against NeXTSTEP aesthetics. Time to add syntax highlighting everywhere.

### Completed (Commit 9db8e92):

**1. Created `syntax_utils.py` - The Shared Foundation**
- `EXTENSION_LEXERS` - 60+ file extension → lexer mappings
- `get_lexer(filepath)` - Get pygments lexer from file path
- `syntax_or_text(content, filepath)` - Render highlighted or plain
- `detect_code_lexer(content)` - Heuristic code detection (shebangs, JSON, Python/JS patterns)
- `SYNTAX_THEME = "monokai"` - Consistent theme everywhere

**2. Created `write_file.py` - New Renderer!**
- Was missing entirely - now shows syntax-highlighted preview of written content
- Green "NEW" badge in header, file stats

**3. Updated 8 Existing Renderers:**

| Renderer | What Changed |
|----------|-------------|
| `read_file` | Syntax highlighting by file extension, built-in line numbers from Syntax component |
| `grep` | Cyan file paths, yellow `reverse` highlighted matches, styled line numbers with `│` |
| `glob` | Files colored by type: Python=bright_blue, JS=yellow, JSON=green, etc. Dir path dim, filename bold |
| `list_dir` | Tree chars dim, directories bold cyan, files colored by lexer type |
| `bash` | Smart detection: `git diff`→diff lexer, JSON commands→json lexer, labeled stdout/stderr |
| `web_fetch` | URL-based detection (raw.githubusercontent.com, .json, /api/), content heuristics |
| `research` | New "Code" section with syntax-highlighted examples from `code_examples` field |
| `update_file` | Already had Syntax("diff") - unchanged, the OG |

**4. Updated `__init__.py`:**
- Added `write_file` renderer to exports
- Added syntax utility functions to `__all__`
- Better docstring explaining the 4-zone pattern

### Key Design Decisions:
- `syntax_or_text()` returns `RenderableType` - graceful fallback to `Text()` for unknown extensions
- File-type coloring consistent across `glob`, `list_dir`, `grep` (same color = same type)
- Bash output detection is conservative - only highlights when confident
- Research viewport prioritizes findings over code (code is supplementary)

### Files Modified:
```
src/tunacode/ui/renderers/tools/
├── __init__.py        (exports + docstring)
├── syntax_utils.py    (NEW - shared utilities)
├── write_file.py      (NEW - renderer)
├── read_file.py       (syntax highlighting)
├── grep.py            (styled matches)
├── glob.py            (colored paths)
├── list_dir.py        (styled tree)
├── bash.py            (smart detection)
├── web_fetch.py       (URL/content detection)
└── research.py        (code examples)
```

### What's Left on This Branch:
- Other UI model work (the branch name suggests more to do)
- Unstaged: `.claude/JOURNAL.md`, `CLAUDE.md`, research docs, config example

### Commands:
```bash
uv run ruff check src/tunacode/ui/renderers/tools/  # All checks pass
uv run python -c "from tunacode.ui.renderers.tools import list_renderers; print(list_renderers())"
# ['bash', 'glob', 'grep', 'list_dir', 'read_file', 'research_codebase', 'update_file', 'web_fetch', 'write_file']
```

### Fun Fact:
We went from 0 syntax-highlighted viewports to 8 in one session. The `update_file` renderer was the lonely pioneer - now it has friends!

---

## 2026-01-08: The Great Panel Width Debugging Adventure (Branch: master)

### The Problem:
Tool panels were narrower than agent panels. User showed screenshot - `read_file` panel was ~50 chars wide while `agent` panel was full width. Classic NeXTSTEP violation!

### The Red Herring (What We Thought):
Initially believed the issue was `width=TOOL_PANEL_WIDTH` (50 chars) on `Panel()` calls. Spent time:
- Removing `width=TOOL_PANEL_WIDTH` from 7 Panel() calls in `panels.py`
- Removing it from `search.py`, `update_file.py`, `app.py`
- Cleaning up unused imports

But panels were STILL narrow after restart. User called me out: "stop being lazy, dig deeper"

### The Actual Root Cause (The AHA Moment):

**Textual's `RichLog.write()` has its OWN `expand` parameter that defaults to `False`!**

From `.venv/lib/python3.13/site-packages/textual/widgets/_rich_log.py`:
```python
def write(
    self,
    content: RenderableType | object,
    width: int | None = None,
    expand: bool = False,  # <-- THIS IS THE VILLAIN
    shrink: bool = True,
    ...
)
```

When `expand=False` (default), RichLog measures the content's minimum width and renders at that width, **completely ignoring** the Panel's own `expand=True` property!

The Panel's expand tells Rich "expand to console width", but RichLog overrides the console width to be just the measured content width. Two different expand flags, two different systems!

### The Real Fix:
Pass `expand=True` to `rich_log.write()`:

```python
# Before
self.rich_log.write(panel)

# After
self.rich_log.write(panel, expand=True)
```

### Files Modified:
| File | Change |
|------|--------|
| `src/tunacode/ui/app.py` | 3 panel writes → `expand=True` (lines 325, 377, 558) |
| `src/tunacode/ui/plan_approval.py` | 1 panel write → `expand=True` (line 132) |
| `src/tunacode/ui/renderers/panels.py` | Removed `width=TOOL_PANEL_WIDTH` (harmless cleanup) |
| `src/tunacode/ui/renderers/search.py` | Removed unused import |
| `src/tunacode/ui/renderers/tools/update_file.py` | Removed unused import |

### The Lesson:
When Rich Panel has `expand=True` but isn't expanding in Textual:
1. The Panel's expand is **not** the issue
2. Check how the panel is being **written** to the widget
3. RichLog.write() has its own expand parameter!

### Status:
- Changes made, ruff passes
- NOT COMMITTED YET - user needs to test
- Previous width removal changes are technically unnecessary but harmless

### Commands:
```bash
git diff --stat  # See all changes
uv run ruff check src/tunacode/ui/  # Verify
# Restart tunacode and make NEW request to test
```

### Philosophical Note:
This bug was a perfect example of "the abstraction leaked". Panel.expand and RichLog.write(expand=) look like they should be the same thing, but they operate at different levels. Panel tells Rich what to do. RichLog tells Rich what size canvas to give it. The canvas size wins.

---

## 2026-01-14: Glob Tool Dead Code Cleanup (Branch: glob-improvements)

### The Mission:
Clean up glob tool based on research doc findings. Remove dead code, fix deprecations.

### The Discovery: Semantically Dead Code

Static analysis (Vulture) reported "no dead code" in glob.py. But manual review found:

```python
# Line 29: Global declared
_gitignore_patterns: set[str] | None = None

# Line 73-74: Function called
if use_gitignore:
    await _load_gitignore_patterns(root_path)

# Lines 155-174: Function populates global
async def _load_gitignore_patterns(root: Path) -> None:
    global _gitignore_patterns
    # ... reads .gitignore files, populates set
```

**The Problem:** `_gitignore_patterns` was NEVER READ. All 7 references were writes. The actual filtering used `DEFAULT_EXCLUDE_DIRS`. The `use_gitignore` parameter was a lie.

### Why Vulture Missed It

Vulture checks: "Is this symbol referenced?"
It does NOT check: "Is the result consumed?"

The function WAS called. The variable WAS assigned. But the data went nowhere.

### Completed:

**Commit 61384fe - Dead Code Removal:**
- Removed `_gitignore_patterns` global
- Removed `_load_gitignore_patterns()` function (21 lines)
- Removed `use_gitignore` parameter from signature
- Replaced 2x `asyncio.get_event_loop().run_in_executor()` with `asyncio.to_thread()`
- Created QA card: `.claude/qa/semantically-dead-code.md`
- Added lesson to CLAUDE.md Continuous Learning

**Commit 745a56b - Asyncio Deprecation Fixes:**
Fixed all remaining `get_event_loop()` calls in codebase:

| File | Calls | Fix |
|------|-------|-----|
| `grep.py` | 2 | `get_running_loop().run_in_executor()` (custom executor) |
| `startup.py` | 2 | `asyncio.to_thread()` |
| `app.py` | 2 | `asyncio.to_thread()` |
| `lsp/client.py` | 3 | `get_running_loop()` for create_future/time |

### Key Insight: asyncio.to_thread() vs get_running_loop()

- `asyncio.to_thread(func)` - For default executor (None), simpler API
- `asyncio.get_running_loop().run_in_executor(exec, func)` - For custom executors

### Prevention Rule

When adding `load_X()` function:
1. Grep for READS of X, not just references
2. If a parameter "controls behavior", trace data flow to prove it changes output
3. Question unused returns - if nothing reads it, why compute it?

### Status:
- Branch: `glob-improvements`
- Tests: 304 passed
- Ruff: clean
- Zero `get_event_loop()` calls remain in src/
- Ready to push

### Next:
Push branch, optionally create PR

### References:
- Research: `memory-bank/research/2026-01-14_12-27-29_glob-tool-bottlenecks.md`
- QA Card: `.claude/qa/semantically-dead-code.md`
- Skill used: `.claude/skills/dead-code-detector/` (Vulture - catches syntactic, not semantic)
