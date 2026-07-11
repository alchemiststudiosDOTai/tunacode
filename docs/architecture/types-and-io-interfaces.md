---
title: Types & I/O Data Interfaces Map
summary: Field-level map of every data boundary in TunaCode — tool args, session persistence, agent messages, runtime state, UI display shapes — with the concrete types that flow through each `Any` annotation and the target type design for issue #441.
read_when: Replacing an `Any` annotation, adding a tool renderer, changing session persistence, or touching the tinyagent message boundary.
depends_on: [types, core, ui]
feeds_into: []
when_to_read:
  - Replacing an `Any` annotation (issue #441)
  - Adding or modifying a tool renderer's args/result contract
  - Changing the session file schema or message serialization
  - Working on the tinyagent message boundary
last_updated: "2026-07-11"
---

# Types & I/O Data Interfaces Map

**Scope:** issue #441 (`Any` proliferation). This document maps the actual data
shapes that flow through every `Any` annotation in `src/tunacode/`, so the
replacement types are designed from real I/O contracts, not guessed.

Baseline trace: 2026-07-11, master @ `0ae3c8c` — ~111 real `Any` annotations
across 27 files (excluding import lines).

**Progress so far:**

| Commit | Work | Result |
|--------|------|--------|
| `5ce24c4` | Dead-code deletion (dead aliases, dead adapter functions, `RipgrepExecutor`, vestigial `SessionState` fields and the unwired recursion cluster) | −389 lines |
| `f0fe551` | B1 tool-args boundary typed: `ToolArgs` across the render pipeline + per-tool TypedDicts in `types/tool_args.py` | 12 files |

Remaining after both: 87 grep occurrences of `Any` across 17 files (count
includes `import` lines).

## The five data boundaries

```
                 ┌──────────────────────────────────────────────────────┐
                 │                    tinyagent (tiny-agent-os)         │
                 │  AgentMessage · ToolCallContent · JsonObject · Agent │
                 └───────┬───────────────────────────┬──────────────────┘
        (B3) messages    │                           │  (B1) tool-call args
                         ▼                           ▼
                 ┌───────────────┐          ┌──────────────────┐
    (B4) runtime │ core/session  │          │ agent_streaming  │
    state fields │ SessionState  │          │ events + callback│
                 └───┬───────────┘          └────────┬─────────┘
      (B2) JSON file ▼                               ▼  (B5) display shapes
                 ┌───────────────┐          ┌──────────────────┐
                 │ disk:         │          │ ui/renderers     │
                 │ {proj}_{id}   │          │ parse_result → T │
                 │ .json         │          │ typed dataclasses│
                 └───────────────┘          └──────────────────┘
```

| # | Boundary | Status | Real shape |
|---|----------|--------|------------|
| B1 | LLM tool-call args → renderers | **done** (`f0fe551`) | `ToolArgs` in transit; per-tool TypedDicts at `parse_result` |
| B2 | Session file on disk | open | Fixed v1 schema (below) |
| B3 | Agent messages | already typed | tinyagent pydantic models (below) |
| B4 | Runtime state fields | partial — vestigial fields deleted; 2 live `Any` fields remain | `tinyagent.Agent`, `CompactionController` |
| B5 | UI display dicts | partial — `arguments` now `ToolArgs`; `context`/`results` remain | 3 small fixed-key dicts |

---

## B1 — Tool-call args: LLM → renderer pipeline ✅

The `args` dict every renderer receives is **the model's JSON-decoded tool-call
arguments, propagated unchanged**:

1. Model emits `ToolCallContent.arguments: JsonObject` (tinyagent `agent_types.py`).
2. Surfaced on `ToolExecutionStart/Update/EndEvent.args: JsonObject | None`.
3. Cached in `_TinyAgentStreamState.tool_args_by_call_id` (`agent_streaming.py`), popped at end.
4. `tool_result_callback(tool_name, status, tool_args, result, duration_ms)`.
5. `ToolResultDisplay` Textual message (`widgets/messages.py`) → `app.py` → `tool_panel_smart` (`panels.py`) → registered renderer.

The whole span is now typed as `ToolArgs` (`types/base.py`,
`ToolArgs = JsonObject = dict[str, JsonValue]`): `RenderFunc`, the renderer
protocol and base class, all six renderers, `tool_panel` / `tool_panel_smart`,
`ToolDisplayData.arguments`, and `ToolCallPartProtocol.args`.

### Per-tool arg schemas (`types/tool_args.py`)

Each renderer narrows `ToolArgs` to its tool's schema at the top of
`parse_result` (`cast(<Tool>Args, args or {})`), so key typos and wrong value
types are checked by mypy. All schemas are `total=False`: model output is
untrusted, so readers keep defensive `.get()` defaults.

| Renderer | TypedDict | Keys | Output dataclass |
|----------|-----------|------|------------------|
| `bash` | `BashArgs` | `command: str`, `timeout: int` (default 120) | `BashData` |
| `read_file` | `ReadFileArgs` | `filepath: str`, `offset: int` | `ReadFileData` |
| `write_file` | `WriteFileArgs` | `filepath: str`, `content: str` | `WriteFileData` |
| `web_fetch` | `WebFetchArgs` | `url: str`, `timeout: int` (default 60) | `WebFetchData` |
| `hashline_edit` | `HashlineEditArgs` | `filepath: str` (fallback only) | `EditDiffData` |
| `discover` | *(none — parses `result` text only)* | — | `DiscoverData` |

Everything after `parse_result` was already fully typed (`Generic[T]` renderer
protocol, per-tool frozen dataclasses).

**RenderFunc positional contract** (`ui/renderers/tools/base.py`):
`(args: ToolArgs | None, result: str, duration_ms: float | None, max_line_width: int) → tuple[RenderableType, PanelMeta] | None`.

Note for non-agent callers: anything hand-building an args dict for a renderer
must annotate it as `ToolArgs` (see `ui/shell_runner.py`, which reuses the bash
panel for `!` shell commands).

---

## B2 — Session persistence (disk JSON) — open

Written by `StateManager.save_session` → `_write_session_file`
(`core/session/state.py`), read by `load_session`.
File: `{project_id}_{session_id}.json`, dir mode `0o700`.

### Session file schema (version 1)

| Field | Type | Notes |
|-------|------|-------|
| `version` | `int` (literal 1) | not read back on load |
| `session_id` | `str` | UUID4 |
| `project_id` | `str` | save is a no-op when empty |
| `created_at` | `str` | ISO timestamp |
| `last_modified` | `str` | stamped at save; sort key for `list_sessions` |
| `working_directory` | `str` | |
| `selected_skill_names` | `list[str]` | strict: `TypeError` on non-str items |
| `current_model` | `str` | drives `max_tokens` recompute on load |
| `session_total_usage` | `UsageMetrics` dict | `{input, output, cache_read, cache_write, total_tokens, cost:{…}}` |
| `thoughts` | `list[str]` | merged with thoughts extracted from legacy messages |
| `messages` | `list[dict]` | tinyagent `model_dump(exclude_none=True)` per message (B3 shapes) |
| `compaction` | `dict \| null` | `CompactionRecord` schema below |

Legacy quirk: any message dict containing a `"thought"` key is extracted into
`thoughts` and dropped from `messages` (`_split_thought_messages`).

### `CompactionRecord` dict (`core/compaction/types.py`)

`summary: str`, `compacted_message_count: int ≥0`, `tokens_before: int ≥0`,
`tokens_after: int ≥0`, `compaction_count: int >0`,
`previous_summary: str | null`, `last_compacted_at: str`.
The `_coerce_*` helpers validate and narrow — their inputs are semantically
`object` (unknown JSON), not `Any`.

### `list_sessions()` summary entry

`{session_id: str, created_at: str, last_modified: str, message_count: int,
current_model: str, file_path: str}` — consumed by
`ui/screens/session_picker.py` (reads exactly these keys).

---

## B3 — Agent messages (tinyagent boundary) — already typed

The canonical message model **is tinyagent's pydantic models** — there is no
separate tunacode message type.

```
AgentMessage = UserMessage | AssistantMessage | ToolResultMessage | CustomAgentMessage
```

| Model | Fields (after `model_dump(exclude_none=True)`) |
|-------|------------------------------------------------|
| `UserMessage` | `role:"user"`, `content: list[Text\|Image]`, `timestamp?` |
| `AssistantMessage` | `role:"assistant"`, `content: list[Text\|Thinking\|ToolCall]`, `stop_reason?`, `timestamp?`, `api?`, `provider?`, `model?`, `usage?`, `error_message?` |
| `ToolResultMessage` | `role:"tool_result"`, `tool_call_id?`, `tool_name?`, `content: list[Text\|Image]`, `details: JsonObject`, `is_error: bool`, `timestamp?` (`terminate` excluded from dump) |
| `CustomAgentMessage` | `role: str`, `timestamp?`, arbitrary extras (`extra="allow"`) |

Content blocks: `TextContent{type:"text", text?, text_signature?, cache_control?}`,
`ImageContent{type:"image", url?, mime_type?}`,
`ThinkingContent{type:"thinking", thinking?, thinking_signature?, cache_control?}`,
`ToolCallContent{type:"tool_call", id?, name?, arguments: JsonObject, partial_json?}`.

Asymmetry worth knowing: a tool **call** id lives in a content item under `id`;
a tool **result** id lives at message top level under `tool_call_id`.

### Adapter status (`utils/messaging/adapter.py`)

| Function | Status |
|----------|--------|
| `get_content` | live — token counter, UI, session picker, compaction |
| `to_canonical` | one call site, result discarded (role validation side-effect, `resume/sanitize.py`) |
| `to_canonical_list`, `from_canonical`, `from_canonical_list` | **removed** in `5ce24c4` (had zero call sites) |

The resume module (`core/agents/resume/sanitize.py`) defines typed mirrors of
the content blocks (`TextContentItem`, `ThinkingContentItem`,
`ImageContentItem`, `ToolCallContentItem` + message dataclasses). These are the
natural seed for a shared typed message layer if one is ever promoted to
`types/`.

---

## B4 — Runtime state fields (`SessionState`, `core/session/state.py`) — partial

Two live `Any` fields remain; both are isinstance-validated to a single
concrete class at their sole access point:

| Field | Declared | Actual runtime type | Evidence |
|-------|----------|---------------------|----------|
| `agents` | `dict[str, Any]` | `dict[ModelName, tinyagent.agent.Agent]` | isinstance-validated in `agent_config.py` |
| `_compaction_controller` | `Any \| None` | `CompactionController \| None` | isinstance-validated in `compaction/controller.py` |

The five vestigial fields the baseline trace found (`spinner`, `current_task`,
`task_hierarchy`, `recursive_context_stack`, `streaming_panel`) had no
producers anywhere in `src/` and were **removed** in `5ce24c4`, together with
the unwired recursion cluster (depth counters, iteration budgets,
`push/pop_recursive_context`, `can_recurse_deeper`, `reset_recursive_state`)
and the declaration-only `input_sessions` / `undo_initialized`.

`StateManagerProtocol` / `SessionStateProtocol` (`core/types/state.py`) mirror
the two remaining fields — fixing the dataclass fixes the protocol.

---

## B5 — UI display shapes (`ui/renderers/panels.py`, `search.py`) — partial

| Shape | Field | Status |
|-------|-------|--------|
| `ToolDisplayData.arguments` | `ToolArgs` | **typed** in `f0fe551` |
| `ErrorDisplayData.context` | `dict[str, Any] \| None` | open — arbitrary key→value; `error_panel()` never populates it |
| `SearchResultData.results` | `list[dict[str, Any]]` | open — fixed keys: `title`, `snippet` (fallback `content`), `relevance` (fallback `score`), `file`, `name` |

The search dicts are built from already-typed dataclasses
(`FileSearchResult`, `CodeSearchResult`, `search.py`) and immediately downcast
to dicts — the typed → untyped direction is backwards.

---

## Live callback contracts (`types/callbacks.py`)

| Alias | Signature |
|-------|-----------|
| `ToolCallback` | `(ToolCallPartProtocol, StreamResultProtocol) → Awaitable[None]` |
| `ToolResultCallback` | `(ToolName, str, ToolArgs, ToolResult \| None, float \| None) → None` |
| `ToolStartCallback`, `NoticeCallback` | `(str) → None` |
| `StreamingCallback` | `(str) → Awaitable[None]` |
| `ToolCallPartProtocol.args` | `str \| ToolArgs \| None` |

The dead aliases the baseline trace found (`UICallback`, `UIInputCallback`,
`AsyncFunc`, `AsyncToolFunc`, `AsyncVoidFunc`) were removed in `5ce24c4`,
along with the dead `types/base.py` aliases (`AgentConfig`, `ErrorContext`,
`UpdateOperation`, `Validator`, `ValidationResult`, `CommandResult`,
`CommandArgs`, `FileDiff`, `DiffHunk`, `DiffLine`, `InputSessions`) and the
unused `RipgrepExecutor` / `RipgrepMetrics` classes.

---

## Remaining work

| # | Change | Detail |
|---|--------|--------|
| 1 | Session persistence TypedDicts | `SessionFileV1`, `CompactionPayload`, `SessionSummary`; `list_sessions() → list[SessionSummary]` fixes `state.py`, the protocol, and `session_picker.py` in one stroke |
| 2 | Coercion inputs → `object` | `_coerce_*` / `_deserialize_*` in `state.py`, `compaction/types.py`, `adapter.py` — they validate-then-narrow; `object` forces it |
| 3 | Runtime fields → concrete types | `agents: dict[str, "Agent"]` · `_compaction_controller: "CompactionController \| None"` via `TYPE_CHECKING` |
| 4 | Point misc sites at existing types | `configuration/paths.py get_session_dir` → `StateManagerProtocol` · `logging **kwargs` → `object` · `LogRecord.extra` → `dict[str, object]` |
| 5 | B5 leftovers | `SearchResultEntry` TypedDict for search dicts; decide `ErrorDisplayData.context` (unused — candidate for deletion) |

### Legitimate `Any` (whitelist, do not "fix")

- The four PEP 562 lazy `__getattr__(name: str) -> Any` modules
  (`ui/`, `ui/renderers/`, `ui/widgets/`, `core/types/` `__init__.py`).
- `ui/widgets/editor.py` `TextualReplApp = Any` runtime branch of a
  `TYPE_CHECKING` split (standard pattern to avoid importing `ui.app`).

### Enforcement

Extend the `[[tool.mypy.overrides]]` strict-`Any` module list per cleaned
package (the `core.agents` override is the template); align the pre-commit
mypy invocation with `pyproject.toml` — today it runs weaker flags than the
config declares.
