---
title: "getattr baseline followup research findings"
link: "getattr-baseline-followup-research"
type: research
ontological_relations:
  - relates_to: [[docs/modules/index]]
  - relates_to: [[docs/architecture/dependencies/DEPENDENCY_LAYERS]]
tags: [research, getattr, ast-grep, baseline]
uuid: "ef179613-d3f7-457b-abee-e264a5a1fb6c"
created_at: "2026-04-13T11:26:27-0500"
---

## Structure

- Baseline source: `rules/ast-grep/baseline/no-getattr-in-src.json`
- Baseline entry count: `26`
- Affected files: `15`
- `src/tunacode` structure scan reported `173` Python files under the package tree.

Area grouping present in the baseline:

- Dynamic import/export helpers: `src/tunacode/core/types/__init__.py:25`, `src/tunacode/ui/renderers/__init__.py:30`, `src/tunacode/ui/widgets/__init__.py:29`
- Core/runtime state access: `src/tunacode/core/compaction/controller.py:512`, `src/tunacode/core/logging/manager.py:86`, `src/tunacode/utils/messaging/token_counter.py:50`
- UI state and debug paths: `src/tunacode/ui/app.py:632`, `src/tunacode/ui/request_debug.py:397`, `src/tunacode/ui/request_debug.py:398`, `src/tunacode/ui/request_debug.py:465`, `src/tunacode/ui/request_debug.py:469`, `src/tunacode/ui/request_debug.py:478`, `src/tunacode/ui/thinking_state.py:15`, `src/tunacode/ui/thinking_state.py:16`, `src/tunacode/ui/thinking_state.py:23`, `src/tunacode/ui/widgets/editor.py:83`, `src/tunacode/ui/widgets/editor.py:86`, `src/tunacode/ui/widgets/editor.py:90`, `src/tunacode/ui/context_panel.py:179`
- Renderer and command plumbing: `src/tunacode/ui/clipboard.py:19`, `src/tunacode/ui/command_registry.py:66`, `src/tunacode/ui/renderers/errors.py:42`, `src/tunacode/ui/renderers/errors.py:81`, `src/tunacode/ui/renderers/errors.py:82`, `src/tunacode/ui/renderers/panels.py:377`, `src/tunacode/ui/renderers/panels.py:379`

Per-file baseline counts:

- `1` `src/tunacode/core/compaction/controller.py`
- `1` `src/tunacode/core/logging/manager.py`
- `1` `src/tunacode/core/types/__init__.py`
- `1` `src/tunacode/ui/app.py`
- `1` `src/tunacode/ui/clipboard.py`
- `1` `src/tunacode/ui/command_registry.py`
- `1` `src/tunacode/ui/context_panel.py`
- `1` `src/tunacode/ui/renderers/__init__.py`
- `3` `src/tunacode/ui/renderers/errors.py`
- `2` `src/tunacode/ui/renderers/panels.py`
- `5` `src/tunacode/ui/request_debug.py`
- `3` `src/tunacode/ui/thinking_state.py`
- `1` `src/tunacode/ui/widgets/__init__.py`
- `3` `src/tunacode/ui/widgets/editor.py`
- `1` `src/tunacode/utils/messaging/token_counter.py`

## Key Files

- `src/tunacode/core/types/__init__.py:8` defines `_TYPE_EXPORTS`; `src/tunacode/core/types/__init__.py:21` defines module `__getattr__(name: str) -> Any`; `src/tunacode/core/types/__init__.py:25` resolves the requested symbol with `getattr(importlib.import_module(module_name, __name__), name)`
- `src/tunacode/ui/renderers/__init__.py:8` defines `_RENDERER_EXPORTS`; `src/tunacode/ui/renderers/__init__.py:26` defines module `__getattr__(name: str) -> Any`; `src/tunacode/ui/renderers/__init__.py:30` resolves the requested symbol with `getattr(importlib.import_module(module_name, __name__), name)`
- `src/tunacode/ui/widgets/__init__.py:8` defines `_WIDGET_EXPORTS`; `src/tunacode/ui/widgets/__init__.py:25` defines module `__getattr__(name: str) -> Any`; `src/tunacode/ui/widgets/__init__.py:29` resolves the requested symbol with `getattr(importlib.import_module(module_name, __name__), name)`
- `src/tunacode/core/types/state.py:24` defines `SessionStateProtocol`; `src/tunacode/core/types/state.py:29` includes `debug_mode: bool`; `src/tunacode/core/types/state.py:49` defines `StateManagerProtocol`; `src/tunacode/core/types/state.py:57` defines `session` returning `SessionStateProtocol`
- `src/tunacode/core/compaction/controller.py:91` defines `CompactionController`; `src/tunacode/core/compaction/controller.py:508` defines `_is_compaction_summary_message(message: AgentMessage) -> bool`; `src/tunacode/core/compaction/controller.py:512` probes `message` with `getattr(message, COMPACTION_SUMMARY_KEY, None)`; `src/tunacode/core/compaction/controller.py:531` defines `_build_summary_user_message(summary_text: str) -> AgentMessage`; `src/tunacode/core/compaction/controller.py:537` returns `summary_message.model_copy(update={COMPACTION_SUMMARY_KEY: True})`
- `src/tunacode/core/logging/manager.py:22` defines `LogManager`; `src/tunacode/core/logging/manager.py:34` stores `_state_manager: StateManagerProtocol | None`; `src/tunacode/core/logging/manager.py:82` defines `debug_mode`; `src/tunacode/core/logging/manager.py:86` probes `self._state_manager.session` with `getattr(..., "debug_mode", False)`
- `src/tunacode/utils/messaging/token_counter.py:25` defines `MessageInput = CanonicalMessage | AgentMessage | JsonObject`; `src/tunacode/utils/messaging/token_counter.py:35` defines `estimate_message_tokens(message: MessageInput) -> int`; `src/tunacode/utils/messaging/token_counter.py:42` normalizes non-canonical input with `to_canonical`; `src/tunacode/utils/messaging/token_counter.py:50` probes each canonical part with `getattr(part, "content", None)`
- `src/tunacode/ui/app.py:90` defines `TextualReplApp(App[None])`; `src/tunacode/ui/app.py:118` defines `__init__(self, *, state_manager: StateManager, show_setup: bool = False)`; `src/tunacode/ui/app.py:128` annotates `self.request_queue: asyncio.Queue[str]`; `src/tunacode/ui/app.py:133` annotates `self._shell_runner: ShellRunner | None`; `src/tunacode/ui/app.py:135` annotates `self.editor: Editor`; `src/tunacode/ui/app.py:155` annotates `self._last_editor_keypress_at: float`; `src/tunacode/ui/app.py:156` constructs `RequestDebugTracer(self)`; `src/tunacode/ui/app.py:203` defines `shell_runner(self) -> ShellRunner`; `src/tunacode/ui/app.py:626` defines `action_cancel_request(self) -> None`; `src/tunacode/ui/app.py:632` probes `self` for `_shell_runner`
- `src/tunacode/ui/request_debug.py:113` defines `RequestDebugTracer`; `src/tunacode/ui/request_debug.py:116` defines `__init__(self, app: TextualReplApp) -> None`; `src/tunacode/ui/request_debug.py:395` defines `_enabled`; `src/tunacode/ui/request_debug.py:397` probes `self._app.state_manager` for `session`; `src/tunacode/ui/request_debug.py:398` probes `session` for `debug_mode`; `src/tunacode/ui/request_debug.py:464` defines `_queue_size(self) -> int`; `src/tunacode/ui/request_debug.py:465` probes `self._app` for `request_queue`; `src/tunacode/ui/request_debug.py:469` probes `queue` for `qsize`; `src/tunacode/ui/request_debug.py:478` probes `queue` for `items`
- `src/tunacode/ui/thinking_state.py:14` defines `_editor_has_draft(app: TextualReplApp) -> bool`; `src/tunacode/ui/thinking_state.py:15` probes `app` for `editor`; `src/tunacode/ui/thinking_state.py:16` probes `editor` for `value`; `src/tunacode/ui/thinking_state.py:20` defines `_has_recent_editor_keypress(app: TextualReplApp) -> bool`; `src/tunacode/ui/thinking_state.py:23` probes `app` for `_last_editor_keypress_at`
- `src/tunacode/ui/widgets/editor.py:39` defines `Editor(Input)`; `src/tunacode/ui/widgets/editor.py:65` defines property `has_paste_buffer(self) -> bool`; `src/tunacode/ui/widgets/editor.py:80` defines `on_key(self, event: events.Key) -> None`; `src/tunacode/ui/widgets/editor.py:83` probes `self` for `app`; `src/tunacode/ui/widgets/editor.py:86` probes `app` for `_request_debug`; `src/tunacode/ui/widgets/editor.py:90` probes `self` for `has_paste_buffer`
- `src/tunacode/ui/context_panel.py:176` defines `is_widget_within_field(widget: DOMNode | None, root: DOMNode, *, field_id: str) -> bool`; `src/tunacode/ui/context_panel.py:179` probes `current` for `id`
- `src/tunacode/ui/clipboard.py:18` defines `_callable_name(callback: Callable[..., object]) -> str`; `src/tunacode/ui/clipboard.py:19` probes `callback` for `__name__`
- `src/tunacode/ui/command_registry.py:15` defines `CommandSpec`; `src/tunacode/ui/command_registry.py:49` defines `LazyCommandRegistry(Mapping[str, "Command"])`; `src/tunacode/ui/command_registry.py:56` defines `__getitem__(self, name: str) -> Command`; `src/tunacode/ui/command_registry.py:65` imports `tunacode.ui.commands.{spec.module_name}`; `src/tunacode/ui/command_registry.py:66` probes the imported module for `spec.class_name`
- `src/tunacode/ui/renderers/errors.py:27` defines `EXCEPTION_CONTEXT_ATTRS`; `src/tunacode/ui/renderers/errors.py:38` defines `_extract_exception_context(exc: Exception) -> dict[str, str]`; `src/tunacode/ui/renderers/errors.py:42` probes `exc` for each attribute named in `EXCEPTION_CONTEXT_ATTRS`; `src/tunacode/ui/renderers/errors.py:77` defines `render_exception(exc: Exception) -> tuple[RenderableType, PanelMeta]`; `src/tunacode/ui/renderers/errors.py:81` probes `exc` for `suggested_fix`; `src/tunacode/ui/renderers/errors.py:82` probes `exc` for `recovery_commands`
- `src/tunacode/ui/renderers/panels.py:85` defines `ToolDisplayData`; `src/tunacode/ui/renderers/panels.py:90` types `result: ToolResult | None`; `src/tunacode/ui/renderers/panels.py:371` defines `_extract_tool_result_text(result: ToolResult | None) -> str | None`; `src/tunacode/ui/renderers/panels.py:377` probes each item in `result.content` for `type`; `src/tunacode/ui/renderers/panels.py:379` probes each item for `text`
- `src/tunacode/types/base.py:69` defines `ToolResult: TypeAlias = AgentToolResult`
- `src/tunacode/types/canonical.py:51` defines `TextPart` with `content: str`; `src/tunacode/types/canonical.py:59` defines `ThoughtPart` with `content: str`; `src/tunacode/types/canonical.py:67` defines `SystemPromptPart` with `content: str`; `src/tunacode/types/canonical.py:85` defines `ToolResultTextPart` with `text: str | None`; `src/tunacode/types/canonical.py:94` defines `ToolResultImagePart` with `url: str | None`; `src/tunacode/types/canonical.py:125` defines `ToolReturnPart`; `src/tunacode/types/canonical.py:135` defines `RetryPromptPart` with `content: str`
- `src/tunacode/ui/esc/types.py:17` defines `ShellRunnerProtocol`; `src/tunacode/ui/esc/handler.py:11` defines `handle_escape(..., shell_runner: ShellRunnerProtocol | None) -> None`

## Baseline Inventory

- `src/tunacode/core/compaction/controller.py:512` `getattr(message, COMPACTION_SUMMARY_KEY, None)`
- `src/tunacode/core/logging/manager.py:86` `getattr(self._state_manager.session, "debug_mode", False)`
- `src/tunacode/core/types/__init__.py:25` `getattr(importlib.import_module(module_name, __name__), name)`
- `src/tunacode/ui/app.py:632` `getattr(self, "_shell_runner", None)`
- `src/tunacode/ui/clipboard.py:19` `getattr(callback, "__name__", repr(callback))`
- `src/tunacode/ui/command_registry.py:66` `getattr(module, spec.class_name)`
- `src/tunacode/ui/context_panel.py:179` `getattr(current, "id", None)`
- `src/tunacode/ui/renderers/__init__.py:30` `getattr(importlib.import_module(module_name, __name__), name)`
- `src/tunacode/ui/renderers/errors.py:42` `getattr(exc, attr)`
- `src/tunacode/ui/renderers/errors.py:81` `getattr(exc, "suggested_fix", None)`
- `src/tunacode/ui/renderers/errors.py:82` `getattr(exc, "recovery_commands", None)`
- `src/tunacode/ui/renderers/panels.py:377` `getattr(item, "type", None)`
- `src/tunacode/ui/renderers/panels.py:379` `getattr(item, "text", None)`
- `src/tunacode/ui/request_debug.py:397` `getattr(self._app.state_manager, "session", None)`
- `src/tunacode/ui/request_debug.py:398` `getattr(session, "debug_mode", False)`
- `src/tunacode/ui/request_debug.py:465` `getattr(self._app, "request_queue", None)`
- `src/tunacode/ui/request_debug.py:469` `getattr(queue, "qsize", None)`
- `src/tunacode/ui/request_debug.py:478` `getattr(queue, "items", None)`
- `src/tunacode/ui/thinking_state.py:15` `getattr(app, "editor", None)`
- `src/tunacode/ui/thinking_state.py:16` `getattr(editor, "value", "")`
- `src/tunacode/ui/thinking_state.py:23` `getattr(app, "_last_editor_keypress_at", 0.0)`
- `src/tunacode/ui/widgets/__init__.py:29` `getattr(importlib.import_module(module_name, __name__), name)`
- `src/tunacode/ui/widgets/editor.py:83` `getattr(self, "app", None)`
- `src/tunacode/ui/widgets/editor.py:86` `getattr(app, "_request_debug", None)`
- `src/tunacode/ui/widgets/editor.py:90` `getattr(self, "has_paste_buffer", False)`
- `src/tunacode/utils/messaging/token_counter.py:50` `getattr(part, "content", None)`

## Patterns Found

- Module export indirection through mapping tables and module `__getattr__`:
  - `src/tunacode/core/types/__init__.py:8`
  - `src/tunacode/core/types/__init__.py:21`
  - `src/tunacode/ui/renderers/__init__.py:8`
  - `src/tunacode/ui/renderers/__init__.py:26`
  - `src/tunacode/ui/widgets/__init__.py:8`
  - `src/tunacode/ui/widgets/__init__.py:25`

- Runtime state probing against app/session/editor objects:
  - `src/tunacode/core/logging/manager.py:86`
  - `src/tunacode/ui/app.py:632`
  - `src/tunacode/ui/request_debug.py:397`
  - `src/tunacode/ui/request_debug.py:398`
  - `src/tunacode/ui/request_debug.py:465`
  - `src/tunacode/ui/request_debug.py:469`
  - `src/tunacode/ui/request_debug.py:478`
  - `src/tunacode/ui/thinking_state.py:15`
  - `src/tunacode/ui/thinking_state.py:16`
  - `src/tunacode/ui/thinking_state.py:23`
  - `src/tunacode/ui/widgets/editor.py:83`
  - `src/tunacode/ui/widgets/editor.py:86`
  - `src/tunacode/ui/widgets/editor.py:90`
  - `src/tunacode/ui/context_panel.py:179`

- Exception metadata probing:
  - `src/tunacode/ui/renderers/errors.py:27`
  - `src/tunacode/ui/renderers/errors.py:42`
  - `src/tunacode/ui/renderers/errors.py:81`
  - `src/tunacode/ui/renderers/errors.py:82`

- Message and tool payload probing:
  - `src/tunacode/core/compaction/controller.py:512`
  - `src/tunacode/utils/messaging/token_counter.py:50`
  - `src/tunacode/ui/renderers/panels.py:377`
  - `src/tunacode/ui/renderers/panels.py:379`

- Callable and module/class-name probing:
  - `src/tunacode/ui/clipboard.py:19`
  - `src/tunacode/ui/command_registry.py:66`

## Dependencies

- `src/tunacode/core/compaction/controller.py:47` imports `StateManagerProtocol` from `tunacode.core.types`; `src/tunacode/core/types/__init__.py:12` maps `StateManagerProtocol` to `.state`; `src/tunacode/core/types/state.py:49` defines the protocol
- `src/tunacode/core/logging/manager.py:13` imports `StateManagerProtocol` from `tunacode.core.types`; `src/tunacode/core/types/state.py:57` defines `session`; `src/tunacode/core/types/state.py:29` includes `debug_mode: bool`
- `src/tunacode/ui/app.py:39` imports context-panel helpers from `tunacode.ui.context_panel`; `src/tunacode/ui/app.py:60` imports `RequestDebugTracer` and `SubmissionTrace` from `tunacode.ui.request_debug`; `src/tunacode/ui/app.py:68` imports widgets from `tunacode.ui.widgets`
- `src/tunacode/ui/request_debug.py:12` opens the `TYPE_CHECKING` block and `src/tunacode/ui/request_debug.py:13` imports `TextualReplApp`; `src/tunacode/ui/app.py:156` constructs `RequestDebugTracer(self)`; `src/tunacode/ui/commands/debug.py:23` imports `build_request_debug_thresholds_message` from `tunacode.ui.request_debug`; `src/tunacode/ui/request_bridge.py:9` imports `BridgeDrainBatch` from `tunacode.ui.request_debug`
- `src/tunacode/ui/thinking_state.py:11` imports `TextualReplApp` only under `TYPE_CHECKING`; `src/tunacode/ui/app.py:771`, `src/tunacode/ui/app.py:776`, `src/tunacode/ui/app.py:781`, and `src/tunacode/ui/app.py:786` lazily import thinking-state helpers
- `src/tunacode/ui/widgets/editor.py:18` imports `EditorSubmitRequested` from `.messages`; `src/tunacode/ui/app.py:165` constructs `Editor()` and stores it on `self.editor`
- `src/tunacode/ui/command_registry.py:65` imports per-command modules under `tunacode.ui.commands`; `src/tunacode/ui/commands/__init__.py:7` imports `COMMANDS`; `src/tunacode/ui/commands/__init__.py:28` indexes `COMMANDS[cmd_name]`; `src/tunacode/ui/commands/help.py:23` and `src/tunacode/ui/widgets/command_autocomplete.py:8` import `COMMAND_DESCRIPTIONS`
- `src/tunacode/ui/renderers/errors.py:7` imports `ErrorDisplayData` and `RichPanelRenderer` from `tunacode.ui.renderers.panels`; `src/tunacode/ui/renderers/search.py:13` imports `RichPanelRenderer` and `SearchResultData` from the same module
- `src/tunacode/ui/renderers/panels.py:20` imports `ToolResult` from `tunacode.types`; `src/tunacode/types/base.py:69` aliases `ToolResult` to `AgentToolResult`
- `src/tunacode/core/compaction/summarizer.py:18` imports `estimate_message_tokens` from `tunacode.utils.messaging`; `src/tunacode/utils/messaging/__init__.py:15` re-exports `estimate_message_tokens`

## Symbol Index

- `src/tunacode/core/compaction/controller.py:91` `CompactionController`
- `src/tunacode/core/compaction/controller.py:508` `_is_compaction_summary_message`
- `src/tunacode/core/logging/manager.py:22` `LogManager`
- `src/tunacode/core/types/__init__.py:21` `__getattr__`
- `src/tunacode/core/types/state.py:24` `SessionStateProtocol`
- `src/tunacode/core/types/state.py:49` `StateManagerProtocol`
- `src/tunacode/utils/messaging/token_counter.py:35` `estimate_message_tokens`
- `src/tunacode/ui/app.py:90` `TextualReplApp`
- `src/tunacode/ui/clipboard.py:18` `_callable_name`
- `src/tunacode/ui/command_registry.py:15` `CommandSpec`
- `src/tunacode/ui/command_registry.py:49` `LazyCommandRegistry`
- `src/tunacode/ui/context_panel.py:176` `is_widget_within_field`
- `src/tunacode/ui/renderers/__init__.py:26` `__getattr__`
- `src/tunacode/ui/renderers/errors.py:38` `_extract_exception_context`
- `src/tunacode/ui/renderers/errors.py:77` `render_exception`
- `src/tunacode/ui/renderers/panels.py:85` `ToolDisplayData`
- `src/tunacode/ui/renderers/panels.py:96` `ErrorDisplayData`
- `src/tunacode/ui/renderers/panels.py:106` `SearchResultData`
- `src/tunacode/ui/renderers/panels.py:116` `RichPanelRenderer`
- `src/tunacode/ui/renderers/panels.py:371` `_extract_tool_result_text`
- `src/tunacode/ui/request_debug.py:28` `BridgeDrainBatch`
- `src/tunacode/ui/request_debug.py:42` `SubmissionTrace`
- `src/tunacode/ui/request_debug.py:113` `RequestDebugTracer`
- `src/tunacode/ui/thinking_state.py:14` `_editor_has_draft`
- `src/tunacode/ui/thinking_state.py:20` `_has_recent_editor_keypress`
- `src/tunacode/ui/widgets/__init__.py:25` `__getattr__`
- `src/tunacode/ui/widgets/editor.py:39` `Editor`

## Script Output Notes

- `research-phase/scripts/structure-map.sh src/tunacode --with-stats` returned the package tree and reported `173` Python files and `173` total code files
- `research-phase/scripts/ast-scan.sh all src/tunacode` returned the function, class, export, import, type, and API-route section headers with no matches listed under them
- `research-phase/scripts/symbol-index.sh src/tunacode` returned the exported-function, exported-class, exported-type/interface, exported-constant, and Python-public-symbol section headers with no matches listed under them
- `research-phase/scripts/dependency-graph.sh ./ --file src/tunacode/ui/request_debug.py` reported `src/tunacode/ui/commands/debug.py` under "Files that import src/tunacode/ui/request_debug.py"
