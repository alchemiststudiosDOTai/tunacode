# Research - Pydantic-AI to TinyAgent Migration & Recent Changes

**Date:** 2026-02-09
**Owner:** claude
**Phase:** Research
**git_commit:** 3f8dea1a0c688beb98e22f83a2aaeda4b6103eec

## Goal

Comprehensive research on the recent pydantic-ai to tinyAgent migration and related changes (textual-css migration, copy-on-select, cache layer refactoring, documentation updates) to prepare for changelog and README updates.

## Findings

### 1. Pydantic-AI to TinyAgent Migration (PR #374)

**Primary Commit:** `3f8dea1a` - "feat: complete pydantic-ai to tinyAgent migration"

#### Key Files Modified

**Core Agent Files:**
- `src/tunacode/core/agents/main.py` - Primary request loop, now uses tinyagent events
- `src/tunacode/core/agents/agent_components/agent_config.py` - Agent factory now constructs `tinyagent.Agent`
- `src/tunacode/core/tinyagent/__init__.py` - **NEW**: Scaffolding with version checking
- `src/tunacode/tools/decorators.py` - **MAJOR**: Added `to_tinyagent_tool()` adapter

**Deleted Files (Orchestrator/Tool Dispatcher):**
- `src/tunacode/core/agents/agent_components/orchestrator/*.py` - Entire orchestrator removed
- `src/tunacode/core/agents/agent_components/streaming.py` - pydantic-ai specific
- `src/tunacode/core/agents/agent_components/tool_executor.py` - tinyAgent handles this
- `src/tunacode/infrastructure/llm_types.py` - pydantic-ai shim layer
- `src/tunacode/types/pydantic_ai.py` - pydantic-ai specific types

**Configuration:**
- `pyproject.toml` - Added `tiny-agent-os==1.1.0`, removed pydantic-ai
- `uv.lock` - Updated with tinyagent dependency
- `.pre-commit-config.yaml` - Removed pydantic-usage guard, excluded `tinyAgent/` vendor

#### Breaking Changes

| Aspect | Before (pydantic-ai) | After (tinyagent) |
|--------|---------------------|-------------------|
| Agent class | `pydantic_ai.Agent` | `tinyagent.Agent` |
| Tool format | `@agent.tool` decorator | `to_tinyagent_tool(adapter)` |
| Message format | Message objects with `.parts` | Dict messages with `role`/`content` |
| Tool execution | Parallel (custom orchestrator) | Sequential (tinyAgent native) |
| Event handling | Node-based orchestrator | Stream of `AgentEvent` objects |
| Tool retry | `ModelRetry` exception | `ToolRetryError` domain type |
| Session persistence | pydantic `TypeAdapter` | Hard break - dict messages only |

**Removed Features:**
- Token pruning/compaction
- Rolling summaries
- Tool output pruning
- Parallel tool execution

---

### 2. Textual CSS Migration (PR #373)

**Primary Commit:** `2cd1d750` - "feat: migrate from rich panels to textual-css"

#### Key Files Modified

**New CSS Stylesheet Files:**
- `src/tunacode/ui/styles/panels.tcss` - Panel styling (tool, error, search, agent panels)
- `src/tunacode/ui/styles/theme-nextstep.tcss` - NeXTSTEP theme with 3D bevel borders
- `src/tunacode/ui/styles/layout.tcss` - Main layout structure
- `src/tunacode/ui/styles/widgets.tcss` - Widget-specific styles
- `src/tunacode/ui/styles/modals.tcss` - Modal dialog styles

**Core Implementation:**
- `src/tunacode/ui/widgets/chat.py` - Added `SelectableRichVisual` (lines 32-145) and `CopyOnSelectStatic` (lines 166-242), `PanelMeta` dataclass (lines 147-160)
- `src/tunacode/ui/app.py` - CSS_PATH configuration (lines 58-64)

**Renderer Files:**
- `src/tunacode/ui/renderers/panels.py` - `RichPanelRenderer`, `PANEL_CSS_CLASS` mapping
- `src/tunacode/ui/renderers/agent_response.py` - Agent response with CSS classes
- `src/tunacode/ui/renderers/errors.py` - Error rendering with PanelMeta
- `src/tunacode/ui/renderers/search.py` - Search results with PanelMeta

#### Before/After Pattern

**Before (Rich Panel):**
```python
from rich.panel import Panel
return Panel(content, title="Tool Name", border_style="cyan")
```

**After (CSS-based):**
```python
meta = PanelMeta(
    css_class="tool-panel",
    border_title=f"[{styles['title']}]{tool_name}[/]",
    border_subtitle=f"[{styles['subtitle']}]{timestamp}[/]"
)
return content, meta
```

**CSS Classes Defined:**
- `.chat-message`, `.expand`, `.agent-panel`
- `.tool-panel` (with `.running`, `.completed`, `.failed` states)
- `.error-panel`, `.search-panel`, `.info-panel`, `.success-panel`, `.warning-panel`

---

### 3. Copy-On-Select Feature (PR #371)

**Primary Commit:** `0fd3c798` - "feat: auto-copy highlighted text to clipboard on mouse release"

#### Implementation

**SelectableRichVisual** (`src/tunacode/ui/widgets/chat.py:32-145`):
- Injects `{"offset": (x, y)}` metadata into Rich segments
- Required for Textual's text selection to map mouse coordinates

**CopyOnSelectStatic** (`src/tunacode/ui/widgets/chat.py:166-242`):
- Automatically copies selected text to clipboard on mouse release
- Uses `Visual.to_strips()` to extract selected text from Rich renderables

---

### 4. Cache Layer Refactoring

**Primary Commits:** `56b014b1` through `82f46246` (cache unification PR #370)

#### Key Files Modified

**Infrastructure:**
- `src/tunacode/infrastructure/cache/manager.py` - `CacheManager` singleton, `Cache` class
- `src/tunacode/infrastructure/cache/strategies.py` - `ManualStrategy`, `MtimeStrategy`
- `src/tunacode/infrastructure/cache/metadata.py` - `MtimeMetadata` dataclass

**Typed Cache Accessors:**
- `src/tunacode/infrastructure/cache/caches/agents.py` - Version-aware agent caching
- `src/tunacode/infrastructure/cache/caches/tunacode_context.py` - Mtime-driven AGENTS.md caching
- `src/tunacode/infrastructure/cache/caches/limits_settings.py` - User settings caching
- `src/tunacode/infrastructure/cache/caches/models_registry.py` - Models.dev registry caching
- `src/tunacode/tools/cache_accessors/ignore_manager_cache.py` - .gitignore-driven caching
- `src/tunacode/tools/cache_accessors/ripgrep_cache.py` - Platform and binary path caching
- `src/tunacode/tools/cache_accessors/xml_prompts_cache.py` - XML tool prompt caching

#### Architecture Changes

**Before (lru_cache pattern):**
```python
from functools import lru_cache

@lru_cache(maxsize=None)
def load_context(path: Path) -> str:
    # No control over invalidation
```

**After (CacheManager pattern):**
```python
from tunacode.infrastructure.cache.caches import tunacode_context as context_cache

def load_context(path: Path) -> str:
    return context_cache.get_context(path)
```

**Key Patterns:**
- Singleton Pattern: `CacheManager` with thread-safe double-checked locking
- Strategy Pattern: Pluggable `CacheStrategy` (Manual vs Mtime-based)
- Accessor Pattern: Typed modules as the only public boundary
- Sentinel Pattern: Distinguish cached `None` from cache miss

---

### 5. Documentation Changes

**Primary Commits:** `b0253799` - "docs: restore agent loop ontology and map"

#### Documentation Files (Referenced, Not Present in Working Tree)

**Agent Loop & Architecture:**
- `docs/architecture/agent-loop.md`
- `docs/architecture/compaction-ontology.md`
- `docs/architecture/DEPENDENCY_MAP.md`
- `docs/architecture/DEPENDENCY_LAYERS.md`
- `docs/architecture/layers_html.html`

**Codebase Map:**
- `docs/codebase-map/modules/core-agents.md`
- `docs/codebase-map/modules/core-prompting.md`
- `docs/codebase-map/modules/prompts.md`
- `docs/codebase-map/modules/tools-overview.md`

**UI Documentation:**
- `docs/ui/layout.md`
- `docs/ui/agent_response_panel.md`
- `docs/ui/nextstep_panels.md`
- `docs/ui/tool_renderers.md`

**Interactive:**
- `docs/agent-loop-map.html` - Interactive agent loop visualization

**Note:** The `docs/` directory does not currently exist in the working tree. These files are referenced in commits and research documents but may have been moved or deleted.

---

### 6. Recent Commits Summary (Last 20)

```
3f8dea1a feat: complete pydantic-ai to tinyAgent migration (#374)
7330e2e1 feat(text-selection): implement SelectableRichVisual to enable copy-on-select
b0253799 docs: restore agent loop ontology and map
2cd1d750 feat: migrate from rich panels to textual-css (#373)
afbe1ad6 docs: add agent loop ontology and interactive map
1cf75e4a fix: use explicit RenderableType signature in CopyOnSelectStatic
0fd3c798 feat: auto-copy highlighted text to clipboard on mouse release (#371)
43e94951 chore: bump version to 0.1.61
4d2437bd Merge pull request #370 (cache unification)
c6c7ab7c fix: satisfy pre-commit dead code checks
82f46246 Migrate remaining lru_cache caches into CacheManager layer
bc07e0b8 Document cache layer + typed accessor pattern
c7ea7790 Add end-to-end tests for mtime-driven caches
83c09ac5 Use cache accessor for ignore manager
2f2dc638 Refactor agent_config to use typed cache accessors
56b014b1 Add typed cache accessors for agents, context, ignore manager
a8e9c835 Add strict cache infrastructure with strategies
```

---

## Key Patterns / Solutions Found

### 1. TinyAgent Event Stream Architecture

```
TunaCode UI -> process_request() -> RequestOrchestrator
    -> agent.stream(message) -> yields AgentEvent objects
    -> Dispatched to handlers by event.type
    -> UI callbacks for streaming, tool execution
```

**Event Handlers in RequestOrchestrator:**
- `_handle_stream_turn_end` - Max iteration check
- `_handle_stream_message_update` - Stream text delta
- `_handle_stream_message_end` - Capture assistant message
- `_handle_stream_tool_execution_start` - Register tool call
- `_handle_stream_tool_execution_end` - Record result
- `_handle_stream_agent_end` - Persist conversation

### 2. Tool Adapter Pattern

`to_tinyagent_tool()` converts TunaCode async tools to tinyagent's `AgentTool`:
- Extracts function signature for JSON schema
- Wraps execution with abort signal checking
- Converts string results to `AgentToolResult`

### 3. CSS Separation Pattern

Content and styling are now separate:
- Renderers return `(content, PanelMeta)` tuples
- `ChatContainer.write()` applies CSS classes and border titles
- Themeable via CSS without code changes

### 4. Cache Invalidation Strategies

- **ManualStrategy**: Never auto-invalidates (agents, models registry, ripgrep)
- **MtimeStrategy**: Invalidates on file modification (AGENTS.md, .gitignore, XML prompts)

---

## Knowledge Gaps

1. **Documentation Status**: The `docs/` directory referenced in commits is not present in the working tree. Need to determine if docs were moved, deleted, or are on a different branch.

2. **Migration Guide**: No user-facing migration guide exists for the pydantic-ai to tinyagent transition. Users may need guidance if they have custom integrations.

3. **Performance Impact**: No benchmarks comparing pydantic-ai vs tinyagent performance (especially sequential vs parallel tool execution).

4. **Session Compatibility**: The hard break in session persistence format means existing sessions may not load correctly.

---

## References

### Code References (permalinks)

**Core Agent:**
- `src/tunacode/core/agents/main.py:179-560` - RequestOrchestrator implementation
- `src/tunacode/core/agents/agent_components/agent_config.py:238-298` - Agent creation with tinyagent
- `src/tunacode/tools/decorators.py:134-207` - `to_tinyagent_tool()` adapter

**Cache Layer:**
- `src/tunacode/infrastructure/cache/manager.py:14-120` - CacheManager and Cache classes
- `src/tunacode/infrastructure/cache/strategies.py:8-35` - CacheStrategy protocols

**UI/CSS:**
- `src/tunacode/ui/widgets/chat.py:32-242` - SelectableRichVisual and CopyOnSelectStatic
- `src/tunacode/ui/app.py:58-64` - CSS_PATH configuration
- `src/tunacode/ui/styles/` - All CSS stylesheet files

### Research Documents

- `memory-bank/research/2026-02-07_tinyagent-v2.5-migration-map.md` - Comprehensive migration research
- `memory-bank/research/2026-02-09_11-28-57_dev_install_tinyagent_setup.md` - tinyagent setup

### Delta/Change Logs

- `.claude/delta/tun-00df-add-tinyagent-dependency.md` - Phase 1: dependency addition
- `.claude/delta/tun-1ad5-wrap-tools-as-tinyagent-agenttool.md` - Phase 2: tool wrapper
- `.claude/delta/2026-02-07_remove-orchestrator-tool-dispatcher.md` - Orchestrator removal
- `.claude/delta/tun-1658-phase6-messaging-normalization.md` - Messaging normalization

### GitHub

- PR #374: pydantic-ai to tinyAgent migration
- PR #373: textual-css migration
- PR #371: copy-on-select feature
- PR #370: cache unification
