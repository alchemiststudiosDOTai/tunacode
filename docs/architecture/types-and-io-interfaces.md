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

Verification date: 2026-07-11 (master @ `0ae3c8c`). ~111 real `Any`
annotations across 27 files (excluding import lines).

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

| # | Boundary | Untyped today as | Real shape |
|---|----------|------------------|------------|
| B1 | LLM tool-call args → renderers | `dict[str, Any] \| None` (~35 sites) | `JsonObject`; de-facto per-tool key schemas (below) |
| B2 | Session file on disk | `dict[str, Any]` payloads | Fixed v1 schema (below) |
| B3 | Agent messages | `dict[str, Any]` in adapter | tinyagent pydantic models (below) |
| B4 | Runtime state fields | `Any` fields on `SessionState` | 2 concrete classes + 5 vestigial fields |
| B5 | UI display dicts | `dict[str, Any]` in panels/search | 3 small fixed-key dicts |

---

## B1 — Tool-call args: LLM → renderer pipeline

The `args` dict every renderer receives is **the model's JSON-decoded tool-call
arguments, propagated unchanged**:

1. Model emits `ToolCallContent.arguments: JsonObject` (tinyagent `agent_types.py`).
2. Surfaced on `ToolExecutionStart/Update/EndEvent.args: JsonObject | None`.
3. Cached in `_TinyAgentStreamState.tool_args_by_call_id` (`agent_streaming.py:205`), popped at end (`:225`).
4. `tool_result_callback(tool_name, status, tool_args, result, duration_ms)` (`agent_streaming.py:234`).
5. `ToolResultDisplay` Textual message (`widgets/messages.py:31`) → `app.py:513` → `tool_panel_smart` (`panels.py:521`) → registered renderer.

`ToolArgs: TypeAlias = JsonObject` **already exists** (`types/base.py:62`,
`JsonObject = dict[str, JsonValue]`) and `ToolResultCallback`
(`types/callbacks.py:63`) already uses it. The renderers hand-write
`dict[str, Any]` instead — that's the drift.

### De-facto per-tool arg schemas (keys each `parse_result` reads)

| Renderer | args keys read | type / default | Output dataclass |
|----------|----------------|----------------|------------------|
| `bash` | `timeout` | `int` / 120 | `BashData` |
| `read_file` | `filepath`, `offset` | `str` / "unknown", `int` / 0 | `ReadFileData` |
| `write_file` | `filepath`, `content` | `str` / "", `str` / "" | `WriteFileData` |
| `web_fetch` | `url`, `timeout` | `str` / "", `int` / 60 | `WebFetchData` |
| `hashline_edit` | `filepath` (fallback only) | `str` / "unknown" | `EditDiffData` |
| `discover` | *(none — parses `result` only)* | — | `DiscoverData` |

Everything after `parse_result` is already fully typed (`Generic[T]` renderer
protocol, per-tool frozen dataclasses). The untyped span is exactly
model-JSON → `parse_result`.

**RenderFunc positional contract** (`base.py:131`):
`(args: ToolArgs | None, result: str, duration_ms: float | None, max_line_width: int) → tuple[RenderableType, PanelMeta] | None`.

---

## B2 — Session persistence (disk JSON)

Written by `StateManager.save_session` → `_write_session_file`
(`core/session/state.py:318-345`), read by `load_session` (`:347-412`).
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
`thoughts` and dropped from `messages` (`_split_thought_messages`, `:239-263`).

### `CompactionRecord` dict (`core/compaction/types.py:75-131`)

`summary: str`, `compacted_message_count: int ≥0`, `tokens_before: int ≥0`,
`tokens_after: int ≥0`, `compaction_count: int >0`,
`previous_summary: str | null`, `last_compacted_at: str`.
The `_coerce_*` helpers validate and narrow — their inputs are semantically
`object` (unknown JSON), not `Any`.

### `list_sessions()` summary entry (`state.py:428-437`)

`{session_id: str, created_at: str, last_modified: str, message_count: int,
current_model: str, file_path: str}` — consumed by
`ui/screens/session_picker.py` (reads exactly these keys).

---

## B3 — Agent messages (tinyagent boundary)

The canonical message model **is tinyagent's pydantic models** — there is no
separate tunacode message type (docs referring to `CanonicalMessage` are stale).

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

`to_canonical`/`from_canonical` are pass-through validators (validate `role`,
return the same dict) — not a conversion layer.

| Function | Status |
|----------|--------|
| `to_canonical` | one call site, result **discarded** (validation side-effect, `resume/sanitize.py:184`) |
| `to_canonical_list`, `from_canonical`, `from_canonical_list` | **dead** — zero call sites, zero tests |
| `get_content` | live — token counter, UI, session picker, compaction |

The resume module (`core/agents/resume/sanitize.py:31-58`) already defines
typed mirrors of the content blocks (`TextContentItem`, `ThinkingContentItem`,
`ImageContentItem`, `ToolCallContentItem` + message dataclasses). These are the
natural home for a shared typed message layer if one is ever promoted to
`types/`.

---

## B4 — Runtime state fields (`SessionState`, `core/session/state.py`)

| Field | Declared | Actual runtime type | Evidence |
|-------|----------|---------------------|----------|
| `agents` | `dict[str, Any]` | `dict[ModelName, tinyagent.agent.Agent]` | isinstance-validated `agent_config.py:479` |
| `_compaction_controller` | `Any \| None` | `CompactionController \| None` | isinstance-validated `controller.py:468` |
| `spinner` | `Any \| None` | **vestigial** — no producer/consumer in src/ | grep: declaration only |
| `current_task` | `Any \| None` | **vestigial** | declaration only |
| `task_hierarchy` | `dict[str, Any]` | **vestigial** — only ever `.clear()`ed | `:154` |
| `recursive_context_stack` | `list[dict[str, Any]]` | **vestigial** — `push_recursive_context` has no callers | protocol mirrors it |
| `streaming_panel` (`RuntimeState`) | `Any \| None` | **vestigial** | `state_structures.py:59` declaration only |

`StateManagerProtocol` / `SessionStateProtocol` (`core/types/state.py`) mirror
these `Any` fields; fixing the dataclass fixes the protocol.

---

## B5 — UI display shapes (`ui/renderers/panels.py`, `search.py`)

| Shape | Field | Actual keys / type |
|-------|-------|--------------------|
| `ToolDisplayData.arguments` | `dict[str, Any]` | the B1 `ToolArgs` dict, rendered generically as a key→value grid |
| `ErrorDisplayData.context` | `dict[str, Any] \| None` | arbitrary key→value; `error_panel()` never populates it |
| `SearchResultData.results` | `list[dict[str, Any]]` | fixed keys: `title`, `snippet` (fallback `content`), `relevance` (fallback `score`), `file`, `name` |

The search dicts are built from already-typed dataclasses
(`FileSearchResult`, `CodeSearchResult`, `search.py:26-44`) and immediately
downcast to dicts — the typed → untyped direction is backwards.

---

## Live callback contracts (`types/callbacks.py`)

| Alias | Signature | Status |
|-------|-----------|--------|
| `ToolCallback` | `(ToolCallPartProtocol, StreamResultProtocol) → Awaitable[None]` | live |
| `ToolResultCallback` | `(ToolName, str, ToolArgs, ToolResult \| None, float \| None) → None` | live |
| `ToolStartCallback` | `(str) → None` | live |
| `StreamingCallback` | `(str) → Awaitable[None]` | live |
| `NoticeCallback` | `(str) → None` | live |
| `ToolCallPartProtocol.args` | `str \| dict[str, Any] \| None` | live — the `dict[str, Any]` here is `ToolArgs` |
| `UICallback`, `UIInputCallback`, `AsyncFunc`, `AsyncToolFunc`, `AsyncVoidFunc` | — | **dead** (export-only) |

---

## Dead code carrying `Any` (deletion, not typing)

| Location | Dead symbols |
|----------|--------------|
| `types/base.py` | `AgentConfig`, `ErrorContext`, `UpdateOperation`, `Validator` (+`ValidationResult`), `CommandResult`, `CommandArgs`, `FileDiff`, `DiffHunk` (+`DiffLine`) |
| `types/callbacks.py` | `UICallback`, `UIInputCallback`, `AsyncFunc`, `AsyncToolFunc`, `AsyncVoidFunc` |
| `utils/messaging/adapter.py` | `to_canonical_list`, `from_canonical`, `from_canonical_list` |
| `tools/utils/ripgrep.py` | entire `RipgrepExecutor` (incl. the `**kwargs: Any`) — only `get_ripgrep_binary_path()` is live |
| `core/session/state.py` | `spinner`, `current_task`, `task_hierarchy`, `recursive_context_stack` (+ `push/pop_recursive_context`), `streaming_panel` |

---

## Target type design

The types below are the design deliverable of #441. Each row kills a bucket of
`Any` by naming the real contract.

### 1. `ToolArgs` everywhere it already applies (mechanical)

Replace `args: dict[str, Any] | None` with `args: ToolArgs | None`
(`types/base.py` alias, = tinyagent `JsonObject`) across
`ui/renderers/tools/*`, `panels.py`, `search.py`,
`ToolCallPartProtocol.args`. ~35 sites, no behavior change,
alias already exists.

### 2. Per-tool arg TypedDicts (declares the de-facto schemas)

```python
# types/tool_args.py
class BashArgs(TypedDict, total=False):
    command: str
    timeout: int

class ReadFileArgs(TypedDict, total=False):
    filepath: str
    offset: int

class WriteFileArgs(TypedDict, total=False):
    filepath: str
    content: str

class WebFetchArgs(TypedDict, total=False):
    url: str
    timeout: int

class HashlineEditArgs(TypedDict, total=False):
    filepath: str
```

`total=False` because model output is untrusted; renderers keep their
`.get()` defaults. These document the contract even where runtime access
stays defensive.

### 3. Session persistence TypedDicts

```python
# core/session/schema.py (or types/)
class SessionFileV1(TypedDict):
    version: int
    session_id: str
    project_id: str
    created_at: str
    last_modified: str
    working_directory: str
    selected_skill_names: list[str]
    current_model: str
    session_total_usage: dict[str, object]   # UsageMetrics.to_dict()
    thoughts: list[str]
    messages: list[dict[str, object]]        # tinyagent model_dump
    compaction: CompactionPayload | None

class CompactionPayload(TypedDict):
    summary: str
    compacted_message_count: int
    tokens_before: int
    tokens_after: int
    compaction_count: int
    previous_summary: str | None
    last_compacted_at: str

class SessionSummary(TypedDict):
    session_id: str
    created_at: str
    last_modified: str
    message_count: int
    current_model: str
    file_path: str
```

`list_sessions() -> list[SessionSummary]` fixes `state.py`,
`StateManagerProtocol.list_sessions`, and `session_picker.py` in one stroke.

### 4. Coercion/deserialization inputs → `object`

`_coerce_*` / `_deserialize_*` inputs in `state.py`, `compaction/types.py`,
`adapter.py` take unknown JSON and narrow it — the honest type is `object`
(forces the narrowing they already perform). Payload returns use
`JsonObject` / the TypedDicts above.

### 5. Runtime fields → concrete types

```python
if TYPE_CHECKING:
    from tinyagent.agent import Agent
    from tunacode.core.compaction.controller import CompactionController

agents: dict[str, "Agent"]
_compaction_controller: "CompactionController | None"
```

Vestigial fields (`spinner`, `current_task`, `task_hierarchy`,
`recursive_context_stack`, `streaming_panel`): delete rather than type.

### 6. Point misc sites at existing types

- `configuration/paths.py get_session_dir(state_manager)` →
  `StateManagerProtocol` (sole access is `.session.session_id`, already covered).
- `logging/manager.py **kwargs: Any` → `**kwargs: object`
  (observed keys: `request_id: str` inline, `reason: str` → `extra`).
- `LogRecord.extra: dict[str, Any]` → `dict[str, object]`.

### 7. Legitimate `Any` (whitelist, do not "fix")

- The four PEP 562 lazy `__getattr__(name: str) -> Any` modules
  (`ui/`, `ui/renderers/`, `ui/widgets/`, `core/types/` `__init__.py`).
- `ui/widgets/editor.py` `TextualReplApp = Any` runtime branch of a
  `TYPE_CHECKING` split (standard pattern to avoid importing `ui.app`).

## `Any` accounting

| Bucket | ~Sites | Resolution |
|--------|-------:|------------|
| B1 tool-args `dict[str, Any]` | 35 | mechanical: `ToolArgs` alias + per-tool TypedDicts |
| B2 serialization payloads + coercion inputs | 40 | TypedDicts + `object` inputs |
| Logging/ripgrep `**kwargs` | 13 | `object` / delete (ripgrep dead) |
| Dead symbols | ~12 | delete |
| Runtime state fields | 8 | 2 typed via TYPE_CHECKING, 5 deleted |
| Legitimate (PEP 562, TYPE_CHECKING split) | 5 | whitelist |

Enforcement: extend the `[[tool.mypy.overrides]]` strict-`Any` module list per
cleaned package (the `core.agents` override is the template); align the
pre-commit mypy invocation with `pyproject.toml`.
