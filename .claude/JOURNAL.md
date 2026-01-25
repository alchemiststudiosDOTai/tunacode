# Claude Journal

## 2026-01-21: pydantic-ai System Prompt Stripping Fix (Branch: resume-qa)

### Problem
Session resume hangs after user abort. Even with message cleanup (dangling tool calls, empty responses, consecutive requests), the stream would open but receive 0 events.

### Root Cause Discovery
**pydantic-ai v1.21.0+ automatically injects system prompts via `agent.iter()`.**

When `message_history` from a previous session contains `system-prompt` parts, the model receives **duplicate system prompts**:
1. System prompt from history (old)
2. System prompt injected by agent (fresh)

This causes models to hang or behave unpredictably.

### Solution
1. Added `_strip_system_prompt_parts()` - removes system-prompt parts from message history
2. Updated `_sanitize_history_for_resume()` to strip system prompts before `agent.iter()`
3. Added HTTP logging (`Network OUT:`/`Network IN:`) for visibility
4. Added HTTP timeout (connect=10s, read=60s) to prevent infinite hangs

### Verification
Debug logs now show:
- Before: `[0] request (2 parts)` with system-prompt + user-prompt
- After: `[0] request (1 parts)` with only user-prompt

### Key Insight
The `Network OUT:` log confirmed requests ARE being sent. The hang was at the provider level (OpenRouter not responding), not message corruption. But the system prompt fix was still necessary to prevent duplicate prompts.

### Files Modified
- `src/tunacode/core/agents/main.py` - system prompt stripping
- `src/tunacode/core/agents/agent_components/streaming.py` - line fixes
- `src/tunacode/core/agents/agent_components/agent_config.py` - HTTP logging + timeout

### Commit
`c9b71bb` on branch `resume-qa`

### References
- Issue: #269
- pydantic-ai issue #3503: message_history must start with user message (v1.21.0 breaking change)
- Previous fix: ad53e0b (dangling tool calls, empty responses, consecutive requests)

---

## 2026-01-21: Resume Module Refactor (Branch: resume-qa)

### Task
Extract session resume logic from `main.py` into dedicated `resume/` module per plan doc.

### Completed
- Created `src/tunacode/core/agents/resume/` module:
  - `__init__.py` - Public API (9 exports)
  - `sanitize.py` - 7 cleanup functions + debug logging (672 lines)
  - `prune.py` - Tool output pruning from compaction.py (179 lines)
  - `summary.py` - Rolling summary generation (NEW, 203 lines)
  - `filter.py` - filterCompacted equivalent (NEW, 61 lines)
- Reduced main.py from ~1312 to ~740 lines
- Deleted `src/tunacode/core/compaction.py`
- Updated test imports
- All 377 tests passing

### Key Commits
- `0f197d3` - rollback point
- `4f300e3` - refactor: extract session resume logic into dedicated resume/ module

### What Happens on Resume Now
1. Cleanup loop: dangling tool calls -> empty responses -> consecutive requests
2. Trailing request check (drop if sending new message)
3. Prune old tool outputs (>40k tokens)
4. Sanitize for pydantic-ai (strip system prompts, clear run_id)
5. Continue with cleaned history

### Follow-up Issue
#271 - Integrate rolling summary compaction into request loop
- Wire `should_compact()` trigger
- Use `filter_compacted()` on resume
- Add tests for new summary/filter functions

### Architecture
```
src/tunacode/core/agents/
├── resume/
│   ├── __init__.py      # Public API
│   ├── sanitize.py      # Cleanup functions
│   ├── prune.py         # Tool output pruning
│   ├── summary.py       # Rolling summaries (not yet wired)
│   └── filter.py        # History truncation (not yet wired)
└── main.py              # Imports from resume/
```

---

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

---

## 2026-01-21: Session Resume Hang Fix (Abort Recovery)

### Problem:
After user aborts (ESC) mid-request, subsequent requests hang indefinitely. Even fresh sessions hit the issue if corrupted history was persisted.

### Root Causes Found:

**1. CancelledError Not Caught (Python 3.8+)**
- `except Exception` does NOT catch `asyncio.CancelledError`
- CancelledError inherits from `BaseException`, not `Exception`
- Stream cleanup code was bypassed on abort

**2. Empty Response Messages**
- `kind=response parts=0` left in history after abort during response generation
- API can't handle empty responses in message sequence

**3. Consecutive Request Messages**
- Multiple `kind=request` without `kind=response` between them
- Happens when abort before model responds, then user sends new message
- API expects alternating request/response pattern

### Solution:
Added three cleanup functions to `main.py`:
1. `_remove_empty_responses()` - removes `kind=response parts=0`
2. `_remove_consecutive_requests()` - keeps only last request in consecutive runs
3. Added `except asyncio.CancelledError` handler in `streaming.py`

**Cleanup order matters:**
```
dangling_tool_calls -> empty_responses -> consecutive_requests
```

### Files Modified:
- `src/tunacode/core/agents/main.py` - cleanup functions + pre-request validation
- `src/tunacode/core/agents/agent_components/streaming.py` - CancelledError handler

### Commit:
`ad53e0b` - fix: resolve session resume hangs after user abort

### Skill Created:
`~/.claude/skills/llm-agent-abort-recovery/SKILL.md`

### Key Insight:
The debug log `ctx_messages=0` was a red herring - that's pydantic-ai's internal context, not session messages. The real issue was message STRUCTURE corruption (empty responses, consecutive requests), not content corruption.

### Prevention:
- Always validate message structure before API calls, not just tool call pairing
- Test abort scenarios: mid-stream, mid-tool-call, before any response
- Remember: Python 3.8+ CancelledError is BaseException, not Exception

---

## 2026-01-24: First-Run Config Shallow Copy Bug (Branch: config-qa)

### Problem
User deletes config, runs `tunacode`, setup screen appears, saves config - but only user-entered fields saved (model, api_key, base_url). All defaults missing (max_retries, ripgrep, lsp, theme, etc.).

### Root Cause: Python Dict Shallow Copy
```python
self._session.user_config = DEFAULT_USER_CONFIG.copy()  # SHALLOW!
```

`.copy()` only copies the top-level dict. Nested dicts (`settings`, `env`, `ripgrep`, `lsp`) still reference the same objects as `DEFAULT_USER_CONFIG`. Any mutation pollutes the module-level constant.

The user initially noticed the bug, I kept looking for phantom config files and doubting them. They were right - it was in the code.

### Solution (The Journey)

**First attempt:** Just use `deepcopy()` everywhere. User pushed back: "why are we copying at all?"

**Second attempt:** Setup was mutating existing user_config instead of building new. Changed to build fresh dict - but that dict was incomplete (missing defaults).

**Final solution:** User insight: "make default config and start config the same way"
- `state.py`: Assign `DEFAULT_USER_CONFIG` directly when no config (reference gets replaced by setup)
- `setup.py`: Build new config from `deepcopy(DEFAULT_USER_CONFIG)`, add user data, assign to session (replaces reference)
- `main.py`: Auto-show setup if no config file (`show_setup=setup or not _config_exists()`)

### Key Insight
Python dicts are mutable references. If you don't mutate, you don't need to copy. Setup creates a NEW dict and assigns it (replaces reference), so state.py can safely assign the constant directly.

The old code's mistake was **mutating** user_config in-place. The fix isn't "copy more" - it's "don't mutate, replace the reference."

### Files Modified
- `src/tunacode/core/state.py` - assign directly, deepcopy only for merge logic
- `src/tunacode/ui/screens/setup.py` - deepcopy defaults, modify, assign new dict
- `src/tunacode/ui/main.py` - auto-show setup when no config

### Commit
`ceacd276` - fix: shallow copy bug corrupting DEFAULT_USER_CONFIG

### Verification
Config now saves complete with all defaults:
```json
{
    "default_model": "openrouter:anthropic/claude-3.5-haiku",
    "env": { ... all env vars ... },
    "settings": {
        "max_retries": 3,
        "max_iterations": 40,
        "ripgrep": { ... },
        "lsp": { ... },
        "providers": { "openrouter": { "base_url": "..." } }
    }
}
```

### Lesson Learned
When user says "it's in the code" and you're looking for external files - stop. Read the code. Trust the user. The shallow copy bug was on line 165 of state.py the whole time.

---

## 2026-01-25: Canonical Messaging Adoption (Branch: types-architect)

### Task
Implement Task 01 from `.claude/task/task_01_canonical_messaging_adoption.md` - migrate production code to use canonical message types via adapter layer.

### Completed

**P1: Message Content Accessor Migration ✓**
Replaced 3 production call sites using legacy `get_message_content()` with `adapter.get_content()`:

| File | Line | Usage |
|------|------|-------|
| `src/tunacode/core/state.py` | 123 | Token counting in `update_token_count()` |
| `src/tunacode/ui/app.py` | 355 | Session replay in `_replay_session_messages()` |
| `src/tunacode/ui/headless/output.py` | 50 | Output extraction in `_extract_from_messages()` |

**P2: Tool Call Tracking Consolidation ✓**

1. **sanitize.py refactor** (~117 LOC deleted):
   - Imported `_get_attr`, `_get_parts`, `find_dangling_tool_calls` from adapter
   - Deleted duplicate accessor functions: `_get_attr_value`, `_normalize_list`, `_get_message_parts`, `_collect_tool_*`
   - Kept mutation helpers and cleanup orchestration functions
   - `find_dangling_tool_call_ids` now thin wrapper around adapter

2. **sanitize_debug.py update**:
   - Uses adapter functions for reading: `_get_attr`, `_get_parts`, `get_tool_call_ids`, `get_tool_return_ids`
   - No more imports from sanitize internal functions

3. **main.py cleanup loop replaced**:
   - Before: 35-line inline cleanup loop (lines 363-397)
   - After: Single call to `run_cleanup_loop(session_messages, tool_call_args_by_id)`

### Key Files Modified
```
src/tunacode/core/state.py                    # import + call site
src/tunacode/ui/app.py                        # import + call site
src/tunacode/ui/headless/output.py            # import + call site
src/tunacode/utils/messaging/__init__.py      # exports _get_attr, _get_parts
src/tunacode/utils/messaging/adapter.py       # exports _get_attr, _get_parts
src/tunacode/core/agents/resume/sanitize.py   # major refactor (-117 LOC)
src/tunacode/core/agents/resume/sanitize_debug.py  # use adapter functions
src/tunacode/core/agents/main.py              # replaced inline loop
```

### Verification
- All 429 tests pass
- ruff: only pre-existing issue (types/__init__.py import sort)
- mypy: only pre-existing issues

### What's Left (Future Tasks)
According to the architecture plan:
- Task 02: State Manager Type Safety
- Task 03: Tool System Typing
- Task 04: UI Layer Adoption

### Key Insight
The adapter pattern is working well - sanitize.py now only contains mutation logic (session sanitization concerns) while all message reading/parsing goes through the canonical adapter. This clean separation makes the codebase easier to maintain.

### Branch
`types-architect`

### Commands
```bash
uv run pytest tests/ -x -q          # 429 passed
uv run ruff check .                  # pre-existing import sort only
git diff --stat                      # see changes
```

### Fun Note
We deleted 117 lines of duplicated polymorphic accessors! The adapter layer is earning its keep. 🎉
